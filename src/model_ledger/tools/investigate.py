"""Investigate tool — comprehensive deep-dive into a single model."""

from __future__ import annotations

from datetime import datetime, timezone

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
    # 1. Get the model — raises ModelNotFoundError if missing
    model = ledger.get(input.model_name)

    # 2. Get all snapshots (newest first from ledger.history)
    snapshots = ledger.history(model)

    # 3. Filter by as_of if set
    if input.as_of is not None:
        as_of = input.as_of
        # Ensure as_of is timezone-aware for comparison
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
        snapshots = [s for s in snapshots if s.timestamp <= as_of]

    # 4. Merge metadata from all snapshot payloads (oldest first, newest wins)
    metadata: dict = {}
    for snap in reversed(snapshots):  # reversed = oldest first
        metadata.update(snap.payload)

    # 5. Build recent_events list
    events = [_snapshot_to_event(s) for s in snapshots]
    total_events = len(events)
    recent_events = events[:10] if input.detail == "summary" else events

    # 6. Compute days_since_last_event
    days_since_last_event: int | None = None
    if snapshots:
        latest_ts = snapshots[0].timestamp
        if latest_ts.tzinfo is None:
            latest_ts = latest_ts.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        days_since_last_event = (now - latest_ts).days

    # 7. Get upstream/downstream (catch exceptions for models without graph nodes)
    upstream_names: list[str] = []
    try:
        upstream_names = ledger.upstream(input.model_name)
    except (KeyError, ValueError, Exception):
        upstream_names = []

    downstream_names: list[str] = []
    try:
        downstream_names = ledger.downstream(input.model_name)
    except (KeyError, ValueError, Exception):
        downstream_names = []

    upstream_nodes = [DependencyNode(name=n) for n in upstream_names]
    downstream_nodes = [DependencyNode(name=n) for n in downstream_names]

    # 8. Get groups and members (catch exceptions)
    group_names: list[str] = []
    try:
        group_refs = ledger.groups(model)
        group_names = [g.name for g in group_refs]
    except (KeyError, ValueError, Exception):
        group_names = []

    member_names: list[str] = []
    try:
        member_refs = ledger.members(model)
        member_names = [m.name for m in member_refs]
    except (KeyError, ValueError, Exception):
        member_names = []

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
    )
