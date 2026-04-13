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
        # Prefer platform from discovered payload, fall back to source
        if snap.event_type == "discovered" and snap.payload.get("platform"):
            platform = snap.payload["platform"]
            break
        if snap.source and not platform:
            platform = snap.source

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

    Pushes limit, offset, and text filters to the backend when supported
    (e.g., Snowflake SQL) to avoid fetching all rows.
    """
    # Build filter dict — only include non-None values
    filters: dict[str, str] = {}
    if input.model_type is not None:
        filters["model_type"] = input.model_type
    if input.owner is not None:
        filters["owner"] = input.owner
    if input.status is not None:
        filters["status"] = input.status

    # Get total count (uses SQL COUNT when supported)
    count_filters = dict(filters)
    if input.text:
        count_filters["text"] = input.text
    backend = ledger._backend
    if hasattr(backend, "count_models"):
        total = backend.count_models(**count_filters)
    else:
        models_all = ledger.list(**filters)
        if input.text:
            text_lower = input.text.lower()
            models_all = [
                m for m in models_all
                if text_lower in m.name.lower() or text_lower in (m.purpose or "").lower()
            ]
        total = len(models_all)

    # Fetch paginated results (uses SQL LIMIT/OFFSET when supported)
    page_filters = dict(filters)
    if input.text:
        page_filters["text"] = input.text
    page_filters["limit"] = str(input.limit)
    page_filters["offset"] = str(input.offset)

    models = ledger.list(**page_filters)

    has_more = (input.offset + input.limit) < total
    summaries = [_model_to_summary(m, ledger) for m in models]

    return QueryOutput(total=total, models=summaries, has_more=has_more)
