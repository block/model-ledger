"""Investigate tool — comprehensive deep-dive into a single model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from model_ledger.backends import batch_fallbacks
from model_ledger.core.ledger_models import Snapshot
from model_ledger.sdk.ledger import Ledger
from model_ledger.tools.schemas import (
    DependencyNode,
    EventSummary,
    InvestigateInput,
    InvestigateOutput,
)


def _snapshot_to_event(snapshot: Snapshot) -> EventSummary:
    """Convert a Snapshot to a compact EventSummary."""
    return EventSummary(
        event_type=snapshot.event_type,
        timestamp=snapshot.timestamp,
        actor=snapshot.actor,
        summary=snapshot.payload.get("summary"),
    )


def investigate(input: InvestigateInput, ledger: Ledger) -> InvestigateOutput:
    """Deep-dive into a single model — history, metadata, dependencies.

    Retrieves the model identity, merges metadata from all snapshot
    payloads (oldest-first so newest wins), builds an event timeline,
    and resolves upstream/downstream dependencies from the graph.

    Raises:
        ModelNotFoundError: If the model does not exist.
    """
    model = ledger.get(input.model_name)

    snapshots = ledger.history(model) or []

    if input.as_of is not None:
        as_of = input.as_of
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
        snapshots = [s for s in snapshots if s.timestamp <= as_of]

    _INTERNAL_EVENTS = {"depends_on", "has_dependent", "registered"}
    _INTERNAL_KEYS = {
        "_content_hash",
        "upstream",
        "downstream",
        "upstream_hash",
        "downstream_hash",
        "relationship",
        "via",
        "via_schema",
        "name",
        "owner",
        "tier",
        "purpose",
        "model_origin",
    }
    metadata: dict[str, Any] = {}
    for snap in reversed(snapshots):
        if snap.event_type in _INTERNAL_EVENTS:
            continue
        metadata.update({k: v for k, v in snap.payload.items() if k not in _INTERNAL_KEYS})

    events = [_snapshot_to_event(s) for s in snapshots]
    total_events = len(events)
    recent_events = events[:10] if input.detail == "summary" else events

    days_since_last_event: int | None = None
    if snapshots:
        latest_ts = snapshots[0].timestamp
        if latest_ts.tzinfo is None:
            latest_ts = latest_ts.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        days_since_last_event = (now - latest_ts).days

    backend = ledger._backend
    try:
        if hasattr(backend, "batch_dependencies"):
            deps = backend.batch_dependencies(model.model_hash)
        else:
            deps = batch_fallbacks.batch_dependencies(backend, model.model_hash)
        upstream_nodes = [DependencyNode(name=d["model_name"]) for d in deps["upstream"]]
        downstream_nodes = [DependencyNode(name=d["model_name"]) for d in deps["downstream"]]
    except Exception:
        upstream_nodes = []
        downstream_nodes = []

    group_names: list[str] = []
    try:
        group_refs = ledger.groups(model) or []
        group_names = [g.name for g in group_refs]
    except (KeyError, ValueError, Exception):
        group_names = []

    member_names: list[str] = []
    try:
        member_refs = ledger.members(model) or []
        member_names = [m.name for m in member_refs]
    except (KeyError, ValueError, Exception):
        member_names = []

    last_validated = None
    open_observation_count = None
    if model.model_type == "composite":
        validated_snaps = [s for s in snapshots if s.event_type == "validated"]
        if validated_snaps:
            last_validated = max(s.timestamp for s in validated_snaps)
        open_observation_count = ledger.open_observation_count(snapshots)

    return InvestigateOutput(
        name=model.name,
        owner=model.owner,
        model_type=model.model_type,
        purpose=model.purpose,
        status=model.status,
        created_at=model.created_at,
        metadata=metadata,
        recent_events=recent_events,
        days_since_last_event=days_since_last_event,
        total_events=total_events,
        upstream=upstream_nodes,
        downstream=downstream_nodes,
        groups=group_names,
        members=member_names,
        last_validated=last_validated,
        open_observation_count=open_observation_count,
    )
