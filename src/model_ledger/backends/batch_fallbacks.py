"""Fallback implementations for batch backend methods.

These functions use only methods defined in the LedgerBackend protocol,
so they work with any conforming backend. Performance is identical to
the current N+1 behavior -- they exist to preserve correctness, not speed.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from model_ledger.backends.ledger_protocol import LedgerBackend


def _resolve_platform(
    snapshots: list[Any],
) -> str | None:
    """Resolve platform from snapshots using priority rules.

    Priority:
    1. Newest ``discovered`` event with ``payload.platform``
    2. Newest snapshot with a non-empty ``source`` field
    3. ``None``

    Expects snapshots sorted newest-first.
    """
    source_fallback: str | None = None
    for snap in snapshots:
        if snap.event_type == "discovered" and snap.payload.get("platform"):
            return str(snap.payload["platform"])
        if snap.source and source_fallback is None:
            source_fallback = str(snap.source)
    return source_fallback


def count_all_snapshots(backend: LedgerBackend) -> int:
    """Count all snapshots by summing per-model counts."""
    total = 0
    for model in backend.list_models():
        total += len(backend.list_snapshots(model.model_hash))
    return total


def model_summaries(
    backend: LedgerBackend,
    model_hashes: list[str],
) -> dict[str, dict]:
    """Build per-model enrichment data for a list of models.

    Returns ``{model_hash: {"last_event": ..., "event_count": ..., "platform": ...}}``
    using the same platform resolution priority as the existing
    ``_model_to_summary`` helper in ``tools/query.py``.
    """
    result: dict[str, dict] = {}
    for model_hash in model_hashes:
        snapshots = backend.list_snapshots(model_hash)
        event_count = len(snapshots)
        if event_count == 0:
            result[model_hash] = {
                "last_event": None,
                "event_count": 0,
                "platform": None,
            }
            continue

        last_event = max(s.timestamp for s in snapshots)
        newest_first = sorted(snapshots, key=lambda s: s.timestamp, reverse=True)
        platform = _resolve_platform(newest_first)

        result[model_hash] = {
            "last_event": last_event,
            "event_count": event_count,
            "platform": platform,
        }
    return result


def changelog_page(
    backend: LedgerBackend,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    event_type: str | None = None,
    model_hash: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Return (events, total_count) with filtering, sorting, and pagination.

    Each event dict contains: ``model_hash``, ``model_name``, ``event_type``,
    ``timestamp``, ``actor``, ``summary``, ``payload``.

    Sort order: ``timestamp DESC``, ``snapshot_hash DESC`` (tiebreaker).
    """
    if model_hash is not None:
        model_hashes = [model_hash]
    else:
        model_hashes = [m.model_hash for m in backend.list_models()]

    name_lookup: dict[str, str] = {}
    all_events: list[dict[str, Any]] = []

    for mh in model_hashes:
        snapshots = backend.list_snapshots(mh)
        for snap in snapshots:
            if since is not None and snap.timestamp < since:
                continue
            if until is not None and snap.timestamp > until:
                continue
            if event_type is not None and snap.event_type != event_type:
                continue

            if mh not in name_lookup:
                model_ref = backend.get_model(mh)
                name_lookup[mh] = model_ref.name if model_ref else mh

            all_events.append(
                {
                    "model_hash": mh,
                    "model_name": name_lookup[mh],
                    "event_type": snap.event_type,
                    "timestamp": snap.timestamp,
                    "actor": snap.actor,
                    "summary": snap.payload.get("summary"),
                    "payload": snap.payload,
                }
            )

    all_events.sort(
        key=lambda e: (e["timestamp"], e["model_hash"], e["event_type"]),
        reverse=True,
    )

    total = len(all_events)
    page = all_events[offset : offset + limit]
    return page, total


def batch_dependencies(
    backend: LedgerBackend,
    model_hash: str,
) -> dict[str, list[dict]]:
    """Return direct upstream and downstream dependencies for a model.

    Returns ``{"upstream": [...], "downstream": [...]}`` where each entry
    contains ``model_hash``, ``model_name``, and ``relationship``.
    """
    snapshots = backend.list_snapshots(model_hash)
    upstream: list[dict[str, Any]] = []
    downstream: list[dict[str, Any]] = []

    for snap in snapshots:
        if snap.event_type == "depends_on":
            related_hash = snap.payload.get("upstream_hash", "")
            related_name = snap.payload.get("upstream", "")
            relationship = snap.payload.get("relationship", "depends_on")

            related = backend.get_model(related_hash) if related_hash else None
            if related is None and related_name:
                related = backend.get_model_by_name(related_name)
            if related is None:
                continue

            upstream.append(
                {
                    "model_hash": related.model_hash,
                    "model_name": related.name,
                    "relationship": relationship,
                }
            )

        elif snap.event_type == "has_dependent":
            related_hash = snap.payload.get("downstream_hash", "")
            related_name = snap.payload.get("downstream", "")
            relationship = snap.payload.get("relationship", "depends_on")

            related = backend.get_model(related_hash) if related_hash else None
            if related is None and related_name:
                related = backend.get_model_by_name(related_name)
            if related is None:
                continue

            downstream.append(
                {
                    "model_hash": related.model_hash,
                    "model_name": related.name,
                    "relationship": relationship,
                }
            )

    return {"upstream": upstream, "downstream": downstream}


def batch_platforms(
    backend: LedgerBackend,
    model_hashes: list[str],
) -> dict[str, str | None]:
    """Return platform for each model hash.

    Uses the same platform resolution priority as ``model_summaries``:
    discovered event ``payload.platform`` > snapshot ``source`` > ``None``.
    """
    result: dict[str, str | None] = {}
    for model_hash in model_hashes:
        snapshots = backend.list_snapshots(model_hash)
        if not snapshots:
            result[model_hash] = None
            continue
        newest_first = sorted(snapshots, key=lambda s: s.timestamp, reverse=True)
        result[model_hash] = _resolve_platform(newest_first)
    return result
