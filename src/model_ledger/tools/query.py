"""Query tool — search and filter the model inventory with pagination."""

from __future__ import annotations

from model_ledger.core.ledger_models import ModelRef
from model_ledger.sdk.ledger import Ledger
from model_ledger.tools.schemas import ModelSummary, QueryInput, QueryOutput


def _model_to_summary(model: ModelRef, ledger: Ledger) -> ModelSummary:
    """Convert a ModelRef to a ModelSummary.

    Enriches the static ModelRef identity with dynamic event data:
    - ``last_event``: timestamp of the most recent snapshot
    - ``event_count``: total number of snapshots
    - ``platform``: source field from the first snapshot that has one
    """
    snapshots = ledger.history(model)
    event_count = len(snapshots)
    last_event = snapshots[0].timestamp if snapshots else None

    platform: str | None = None
    for snap in snapshots:
        if snap.source:
            platform = snap.source
            break

    return ModelSummary(
        name=model.name,
        owner=model.owner,
        model_type=model.model_type,
        status=model.status,
        platform=platform,
        last_event=last_event,
        event_count=event_count,
    )


def query(input: QueryInput, ledger: Ledger) -> QueryOutput:
    """Search and filter the model inventory with pagination.

    Applies structured filters (model_type, owner, status) via the
    ledger backend, then optionally fuzzy-filters on name and purpose
    using case-insensitive substring matching. Results are paginated
    via offset/limit.
    """
    # Build filter dict — only include non-None values
    filters: dict[str, str] = {}
    if input.model_type is not None:
        filters["model_type"] = input.model_type
    if input.owner is not None:
        filters["owner"] = input.owner
    if input.status is not None:
        filters["status"] = input.status

    # Get all matching models from the backend
    models = ledger.list(**filters)

    # Fuzzy-filter on name and purpose (case-insensitive contains)
    if input.text:
        text_lower = input.text.lower()
        models = [
            m
            for m in models
            if text_lower in m.name.lower() or text_lower in (m.purpose or "").lower()
        ]

    total = len(models)

    # Paginate
    page = models[input.offset : input.offset + input.limit]
    has_more = (input.offset + input.limit) < total

    # Convert each ModelRef to a ModelSummary
    summaries = [_model_to_summary(m, ledger) for m in page]

    return QueryOutput(total=total, models=summaries, has_more=has_more)
