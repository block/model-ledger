"""Changelog tool — cross-model event timeline with time range filtering."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from model_ledger.backends import batch_fallbacks
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


def changelog(input: ChangelogInput, ledger: Ledger) -> ChangelogOutput:
    """Cross-model event timeline with time range filtering.

    Dispatches to the backend's ``changelog_page`` method if available,
    otherwise falls back to ``batch_fallbacks.changelog_page``.
    """
    since = input.since
    until = input.until

    if since is None and until is None:
        since = datetime.now(timezone.utc) - timedelta(days=7)

    if since is not None:
        since = _ensure_utc(since)
    if until is not None:
        until = _ensure_utc(until)

    model_hash = None
    if input.model_name is not None:
        model = ledger.get(input.model_name)
        model_hash = model.model_hash

    backend = ledger._backend
    if hasattr(backend, "changelog_page"):
        events_dicts, total = backend.changelog_page(
            since=since,
            until=until,
            event_type=input.event_type,
            model_hash=model_hash,
            limit=input.limit,
            offset=input.offset,
        )
    else:
        events_dicts, total = batch_fallbacks.changelog_page(
            backend,
            since=since,
            until=until,
            event_type=input.event_type,
            model_hash=model_hash,
            limit=input.limit,
            offset=input.offset,
        )

    events = [
        EventDetail(
            model_name=d["model_name"],
            event_type=d["event_type"],
            timestamp=d["timestamp"],
            actor=d.get("actor"),
            summary=d.get("summary"),
            payload=d.get("payload", {}),
        )
        for d in events_dicts
    ]

    has_more = (input.offset + input.limit) < total
    period = _build_period(since, until)

    return ChangelogOutput(
        total=total,
        events=events,
        has_more=has_more,
        period=period,
    )
