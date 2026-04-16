"""Changelog tool — cross-model event timeline with time range filtering."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from model_ledger.core.ledger_models import Snapshot
from model_ledger.sdk.ledger import Ledger
from model_ledger.tools.schemas import (
    ChangelogInput,
    ChangelogOutput,
    EventDetail,
)


def _ensure_utc(dt: datetime) -> datetime:
    """Normalize a datetime to UTC. Treats naive datetimes as UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _build_period(since: datetime | None, until: datetime | None) -> str:
    """Build a human-readable period string."""
    if since is not None and until is not None:
        return f"{since.strftime('%Y-%m-%d')} to {until.strftime('%Y-%m-%d')}"
    if since is not None:
        now = datetime.now(timezone.utc)
        days = max((now - _ensure_utc(since)).days, 0)
        return f"last {days} days"
    return "all time"


def _snapshot_to_event(snapshot: Snapshot, model_name: str) -> EventDetail:
    """Convert a Snapshot into an EventDetail with model association."""
    return EventDetail(
        model_name=model_name,
        event_type=snapshot.event_type,
        timestamp=snapshot.timestamp,
        actor=snapshot.actor,
        summary=snapshot.payload.get("summary"),
        payload=snapshot.payload,
    )


def changelog(input: ChangelogInput, ledger: Ledger) -> ChangelogOutput:
    """Cross-model event timeline with time range filtering.

    Iterates all models (or a single model if ``input.model_name`` is set),
    collects snapshots within the time range, and returns them sorted
    newest-first with pagination.
    """
    since = input.since
    until = input.until

    # Default: if both since and until are None, set since = 7 days ago
    if since is None and until is None:
        since = datetime.now(timezone.utc) - timedelta(days=7)

    # Normalize to UTC for comparison
    if since is not None:
        since = _ensure_utc(since)
    if until is not None:
        until = _ensure_utc(until)

    # Get models to iterate
    models = [ledger.get(input.model_name)] if input.model_name is not None else ledger.list()

    # Collect all matching events
    all_events: list[EventDetail] = []
    for model in models:
        snapshots = ledger.history(model) or []
        for snap in snapshots:
            ts = _ensure_utc(snap.timestamp)

            # Filter by time range
            if since is not None and ts < since:
                continue
            if until is not None and ts > until:
                continue

            # Filter by event_type
            if input.event_type is not None and snap.event_type != input.event_type:
                continue

            all_events.append(_snapshot_to_event(snap, model.name))

    # Sort by timestamp descending (newest first)
    _epoch = datetime.min.replace(tzinfo=timezone.utc)
    all_events.sort(
        key=lambda e: _ensure_utc(e.timestamp) if e.timestamp else _epoch,
        reverse=True,
    )

    # Paginate
    total = len(all_events)
    page = all_events[input.offset : input.offset + input.limit]
    has_more = (input.offset + input.limit) < total

    # Build period string
    period = _build_period(since, until)

    return ChangelogOutput(
        total=total,
        events=page,
        has_more=has_more,
        period=period,
    )
