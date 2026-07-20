"""Query tool — search and filter the model inventory with pagination."""

from __future__ import annotations

from model_ledger.backends import batch_fallbacks
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
    snapshots = ledger.history(model) or []
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


def _summarize(models: list[ModelRef], ledger: Ledger) -> list[ModelSummary]:
    """Build enriched ModelSummary rows via one batched backend dispatch."""
    backend = ledger.backend
    model_hashes = [m.model_hash for m in models]
    if hasattr(backend, "model_summaries"):
        enrichment = backend.model_summaries(model_hashes)
    else:
        enrichment = batch_fallbacks.model_summaries(backend, model_hashes)
    return [
        ModelSummary(
            name=m.name,
            owner=m.owner,
            model_type=m.model_type,
            status=m.status,
            platform=enrichment.get(m.model_hash, {}).get("platform"),
            last_event=enrichment.get(m.model_hash, {}).get("last_event"),
            event_count=enrichment.get(m.model_hash, {}).get("event_count", 0),
        )
        for m in models
    ]


def query(input: QueryInput, ledger: Ledger) -> QueryOutput:
    """Search and filter the model inventory with pagination.

    Pushes limit, offset, and text filters to the backend when supported
    (e.g., Snowflake SQL) to avoid fetching all rows. The ``platform``
    filter is derived from snapshot data (``discovered`` payload, then
    snapshot source), so it is resolved in batch and applied here.
    """
    filters: dict[str, str] = {}
    if input.model_type is not None:
        filters["model_type"] = input.model_type
    if input.owner is not None:
        filters["owner"] = input.owner
    if input.status is not None:
        filters["status"] = input.status

    if input.platform is not None:
        return _query_by_platform(input, ledger, filters)

    count_filters = dict(filters)
    if input.text:
        count_filters["text"] = input.text
    backend = ledger.backend
    if hasattr(backend, "count_models"):
        total = backend.count_models(**count_filters)
    else:
        models_all = ledger.list(**filters)
        if input.text:
            text_lower = input.text.lower()
            models_all = [
                m
                for m in models_all
                if text_lower in m.name.lower() or text_lower in (m.purpose or "").lower()
            ]
        total = len(models_all)

    page_filters = dict(filters)
    if input.text:
        page_filters["text"] = input.text
    page_filters["limit"] = str(input.limit)
    page_filters["offset"] = str(input.offset)

    models = ledger.list(**page_filters)

    has_more = (input.offset + input.limit) < total

    return QueryOutput(total=total, models=_summarize(models, ledger), has_more=has_more)


def _query_by_platform(input: QueryInput, ledger: Ledger, filters: dict[str, str]) -> QueryOutput:
    """Apply the platform filter over structurally-matched models.

    Platform is not a column on the model row — it is resolved from each
    model's snapshots (``batch_platforms`` pushes this down in SQL-backed
    backends) — so filtering and pagination happen here rather than in
    ``list_models``.
    """
    backend = ledger.backend

    models_all = ledger.list(**filters)
    if input.text:
        text_lower = input.text.lower()
        models_all = [
            m
            for m in models_all
            if text_lower in m.name.lower() or text_lower in (m.purpose or "").lower()
        ]

    model_hashes = [m.model_hash for m in models_all]
    if hasattr(backend, "batch_platforms"):
        platforms = backend.batch_platforms(model_hashes)
    else:
        platforms = batch_fallbacks.batch_platforms(backend, model_hashes)

    matched = [m for m in models_all if platforms.get(m.model_hash) == input.platform]
    total = len(matched)
    page = matched[input.offset : input.offset + input.limit]
    has_more = (input.offset + input.limit) < total

    return QueryOutput(total=total, models=_summarize(page, ledger), has_more=has_more)
