"""Ledger SDK — tool-shaped API for v0.3.0 event-log paradigm."""

from __future__ import annotations

import builtins
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, TypedDict

from model_ledger.backends import batch_fallbacks
from model_ledger.backends.ledger_memory import InMemoryLedgerBackend
from model_ledger.backends.ledger_protocol import LedgerBackend
from model_ledger.core.enums import ModelStatus
from model_ledger.core.exceptions import ModelNotFoundError
from model_ledger.core.ledger_models import ModelRef, Snapshot, Tag

if TYPE_CHECKING:
    from model_ledger.graph.models import DataNode


class AddResult(TypedDict):
    """Result of ``Ledger.add()`` — nodes newly recorded vs. skipped as unchanged."""

    added: int
    skipped: int


class ConnectResult(TypedDict):
    """Result of ``Ledger.connect()`` — dependency edges created vs. skipped as present."""

    links_created: int
    links_skipped: int


def _normalize_status(raw: object) -> str | None:
    """Coerce a connector-discovered status to its canonical ModelStatus value.

    Returns None for absent or unrecognized values — "no opinion" — so callers
    leave the stored status untouched. A connector that stops reporting status
    must never regress an explicitly set status back to the default.
    """
    if not isinstance(raw, str):
        return None
    try:
        return ModelStatus(raw).value
    except ValueError:
        return None


# Events that are internal ledger bookkeeping or governance actions on the
# composite itself.  These are NOT propagated as member_changed to parent
# composites — only real domain events on member models should surface there.
_INTERNAL_EVENTS: frozenset[str] = frozenset(
    {
        "registered",
        "has_dependent",
        "depends_on",
        "member_added",
        "member_removed",
        "member_changed",
        "observation_issued",
        "observation_resolved",
        "validated",
    }
)


class Ledger:
    """The main entry point for model-ledger v0.3.0.

    Every public method is designed to work as an agent tool call:
    clear inputs, JSON-serializable outputs, no side effects beyond the ledger.
    """

    def __init__(self, backend: LedgerBackend | None = None) -> None:
        self._backend = backend or InMemoryLedgerBackend()
        self._name_cache: dict[str, ModelRef] = {}
        self._cache_complete = False  # True after bulk preload — skip individual lookups
        self._node_cache: list = []  # DataNodes from add() — reused by connect()

    @classmethod
    def from_sqlite(cls, db_path: str) -> Ledger:
        """Create a Ledger backed by a SQLite database.

        Args:
            db_path: Path to the SQLite database file. Created if it doesn't exist.

        Example:
            >>> ledger = Ledger.from_sqlite("./inventory.db")
        """
        from model_ledger.backends.sqlite_ledger import SQLiteLedgerBackend

        return cls(SQLiteLedgerBackend(db_path))

    @classmethod
    def from_snowflake(cls, connection: Any, schema: str = "MODEL_LEDGER") -> Ledger:
        """Create a Ledger backed by Snowflake.

        Args:
            connection: A Snowflake connection (snowflake.connector connection object).
            schema: Fully qualified schema name (e.g., "MY_DB.MODEL_LEDGER").

        Example:
            >>> ledger = Ledger.from_snowflake(conn, schema="ANALYTICS.MODEL_LEDGER")
        """
        from model_ledger.backends.snowflake import SnowflakeLedgerBackend

        return cls(SnowflakeLedgerBackend(connection=connection, schema=schema))

    def _resolve_model(self, model: ModelRef | str) -> ModelRef:
        if isinstance(model, ModelRef):
            return model
        if model in self._name_cache:
            return self._name_cache[model]
        result = self._backend.get_model_by_name(model)
        if result is None:
            result = self._backend.get_model(model)
        if result is None:
            raise ModelNotFoundError(model)
        self._name_cache[model] = result
        return result

    def _resolve_hashes(self, model_hashes: builtins.list[str]) -> dict[str, ModelRef]:
        """Resolve many model hashes to ModelRefs in a single backend round trip.

        Dispatches to the backend's bulk ``get_models`` when available
        (one ``IN (...)`` query) and falls back to the protocol-only
        implementation otherwise. Used by the graph methods to resolve all
        edges of a node at once instead of one ``get()`` per edge.
        """
        if not model_hashes:
            return {}
        if hasattr(self._backend, "get_models"):
            resolved: dict[str, ModelRef] = self._backend.get_models(model_hashes)
            return resolved
        return batch_fallbacks.get_models(self._backend, model_hashes)

    def register(
        self,
        *,
        name: str,
        owner: str,
        model_type: str,
        tier: str,
        purpose: str,
        model_origin: str = "internal",
        status: str = "active",
        actor: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> ModelRef:
        if name in self._name_cache:
            return self._name_cache[name]
        if not self._cache_complete:
            existing = self._backend.get_model_by_name(name)
            if existing is not None:
                self._name_cache[name] = existing
                return existing
        model = ModelRef(
            name=name,
            owner=owner,
            model_type=model_type,
            model_origin=model_origin,
            tier=tier,
            purpose=purpose,
            status=status,
            metadata=metadata or {},
        )
        self._backend.save_model(model)
        self._backend.append_snapshot(
            Snapshot(
                model_hash=model.model_hash,
                actor=actor,
                event_type="registered",
                payload={
                    "name": name,
                    "owner": owner,
                    "tier": tier,
                    "purpose": purpose,
                    "model_origin": model_origin,
                },
            )
        )
        self._name_cache[name] = model
        return model

    def record(
        self,
        model: ModelRef | str,
        *,
        event: str,
        payload: dict[str, Any],
        actor: str,
        source: str | None = None,
        parent: str | None = None,
        tags: dict[str, str] | None = None,
        timestamp: datetime | None = None,
        _propagating: bool = False,
    ) -> Snapshot:
        ref = self._resolve_model(model)
        kwargs: dict[str, Any] = {
            "model_hash": ref.model_hash,
            "actor": actor,
            "event_type": event,
            "source": source,
            "parent_hash": parent,
            "payload": payload,
            "tags": tags or {},
        }
        if timestamp is not None:
            kwargs["timestamp"] = timestamp
        snapshot = Snapshot(**kwargs)
        self._backend.append_snapshot(snapshot)

        # Propagate member_changed to parent composites (one level only).
        # Skip internal ledger bookkeeping and governance events — only
        # propagate domain events on member models.
        if not _propagating and event not in _INTERNAL_EVENTS:
            try:
                parent_composites = self.groups(ref)
            except ModelNotFoundError:
                parent_composites = []
            for composite in parent_composites or []:
                self.record(
                    composite,
                    event="member_changed",
                    payload={
                        "member_name": ref.name,
                        "member_hash": ref.model_hash,
                        "original_event_type": event,
                        "original_snapshot_hash": snapshot.snapshot_hash,
                    },
                    actor=actor,
                    _propagating=True,
                )

        return snapshot

    def tag(self, model: ModelRef | str, name: str) -> Tag:
        ref = self._resolve_model(model)
        latest = self._backend.latest_snapshot(ref.model_hash)
        if latest is None:
            raise ModelNotFoundError(ref.name)
        tag = Tag(
            name=name,
            model_hash=ref.model_hash,
            snapshot_hash=latest.snapshot_hash,
        )
        self._backend.set_tag(tag)
        return tag

    def get(self, name_or_hash: str) -> ModelRef:
        result = self._backend.get_model_by_name(name_or_hash)
        if result is None:
            result = self._backend.get_model(name_or_hash)
        if result is None:
            raise ModelNotFoundError(name_or_hash)
        return result

    def list(self, **filters: str) -> builtins.list[ModelRef]:
        return self._backend.list_models(**filters)

    def history(
        self,
        model: ModelRef | str,
        **filters: str,
    ) -> builtins.list[Snapshot]:
        ref = self._resolve_model(model)
        snaps = self._backend.list_snapshots(ref.model_hash, **filters)
        return sorted(snaps, key=lambda s: s.timestamp, reverse=True)

    def latest(
        self,
        model: ModelRef | str,
        tag: str | None = None,
    ) -> Snapshot | None:
        ref = self._resolve_model(model)
        return self._backend.latest_snapshot(ref.model_hash, tag=tag)

    def link_dependency(
        self,
        upstream: ModelRef | str,
        downstream: ModelRef | str,
        *,
        relationship: str = "depends_on",
        actor: str,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[Snapshot, Snapshot]:
        up_ref = self._resolve_model(upstream)
        down_ref = self._resolve_model(downstream)
        up_snap = self.record(
            up_ref,
            event="has_dependent",
            payload={
                "downstream": down_ref.name,
                "downstream_hash": down_ref.model_hash,
                "relationship": relationship,
                **(metadata or {}),
            },
            actor=actor,
        )
        down_snap = self.record(
            down_ref,
            event="depends_on",
            payload={
                "upstream": up_ref.name,
                "upstream_hash": up_ref.model_hash,
                "relationship": relationship,
                **(metadata or {}),
            },
            actor=actor,
        )
        return up_snap, down_snap

    def inventory_at(
        self,
        date: datetime,
        platform: str | None = None,
    ) -> builtins.list[ModelRef]:
        all_models = self._backend.list_models()
        result = []
        for model in all_models:
            if model.created_at > date:
                continue
            snaps = self._backend.list_snapshots_before(model.model_hash, date)
            if platform is not None:
                snaps = [s for s in snaps if s.source == platform]
            if not snaps:
                continue
            latest = max(snaps, key=lambda s: s.timestamp)
            if latest.event_type == "not_found":
                continue
            result.append(model)
        return result

    def dependencies(
        self,
        model: ModelRef | str,
        direction: str = "both",
        *,
        snapshots: builtins.list[Snapshot] | None = None,
    ) -> builtins.list[dict[str, Any]]:
        """Direct dependency edges for a model.

        Resolves every edge's target model in ONE batched lookup instead of a
        per-edge round trip. Pass ``snapshots`` (the model's full history) to
        reuse an already-fetched list and skip the ``list_snapshots`` call —
        the graph traversal and ``investigate`` use this to avoid refetching.
        """
        ref = self._resolve_model(model)
        snaps = snapshots if snapshots is not None else self._backend.list_snapshots(ref.model_hash)

        # Collect edges first, then resolve all target hashes in one batch.
        # Each edge: (direction, target_hash, relationship)
        edges: builtins.list[tuple[str, str, str]] = []
        if direction in ("upstream", "both"):
            for s in snaps:
                if s.event_type == "depends_on":
                    h = s.payload.get("upstream_hash")
                    if h:
                        edges.append(("upstream", h, s.payload.get("relationship", "depends_on")))
        if direction in ("downstream", "both"):
            for s in snaps:
                if s.event_type == "has_dependent":
                    h = s.payload.get("downstream_hash")
                    if h:
                        edges.append(("downstream", h, s.payload.get("relationship", "depends_on")))

        resolved = self._resolve_hashes([h for _, h, _ in edges])

        result: builtins.list[dict[str, Any]] = []
        for edge_direction, target_hash, relationship in edges:
            target = resolved.get(target_hash)
            if target is None:
                continue
            result.append(
                {
                    "model": target,
                    "relationship": relationship,
                    "direction": edge_direction,
                }
            )
        return result

    # --- Graph methods (v0.4.0) ---

    def add(self, nodes: DataNode | builtins.list[DataNode]) -> AddResult:
        """Register DataNodes. Each becomes a ModelRef + discovered Snapshot.

        Skips writing if the discovered payload is identical to the last snapshot
        (content-hash dedup). Preloads existing models in bulk to avoid per-node queries.

        Recognized ``node.metadata`` keys map onto the model row: ``owner``,
        ``model_type``/``node_type``/``type``, ``tier``, ``purpose``,
        ``model_origin``, and ``status``. A discovered ``status`` (any
        ``ModelStatus`` value, case-insensitive) is propagated to the model —
        including already-registered models — so lifecycle changes detected at
        the source (e.g. ``deprecated`` for an entity deleted upstream) reach
        the model row on the next sync. An absent or unrecognized status leaves
        the stored status unchanged.
        """
        import hashlib
        import json

        from model_ledger.graph.models import DataNode

        if isinstance(nodes, DataNode):
            nodes = [nodes]
        self._node_cache.extend(nodes)

        # Bulk preload — one query for all models, one for all snapshot hashes
        if not self._cache_complete:
            for m in self._backend.list_models():
                self._name_cache[m.name] = m
            self._cache_complete = True

        # Preload last discovered snapshot content hashes for dedup.
        # We store _content_hash in the payload itself, so we can read just that field.
        existing_hashes: dict[str, str] = {}
        if hasattr(self._backend, "list_snapshot_content_hashes"):
            existing_hashes = self._backend.list_snapshot_content_hashes(event_type="discovered")
        elif hasattr(self._backend, "list_all_snapshots"):
            for s in self._backend.list_all_snapshots(event_type="discovered"):
                h = s.payload.get("_content_hash")
                if h:
                    existing_hashes[s.model_hash] = h

        added = 0
        skipped = 0
        for node in nodes:
            node_status = _normalize_status(node.metadata.get("status"))
            ref = self.register(
                name=node.name,
                owner=node.metadata.get("owner") or "unknown",
                model_type=node.metadata.get("model_type")
                or node.metadata.get("node_type")
                or node.metadata.get("type")
                or "unknown",
                tier=node.metadata.get("tier") or "unclassified",
                purpose=node.metadata.get("purpose") or "",
                model_origin=node.metadata.get("model_origin") or "internal",
                status=node_status or "active",
                actor=f"connector:{node.platform}" if node.platform else "system",
            )
            payload = {
                "platform": node.platform,
                "inputs": [{"identifier": p.identifier, **p.schema} for p in node.inputs],
                "outputs": [{"identifier": p.identifier, **p.schema} for p in node.outputs],
                **{
                    k: v
                    for k, v in node.metadata.items()
                    if k
                    not in (
                        "owner",
                        "node_type",
                        "tier",
                        "purpose",
                        "model_origin",
                        "source_updated_at",
                    )
                },
            }

            # Content-hash dedup: skip if payload unchanged.
            # Exclude volatile fields (timestamps change between runs without
            # the model actually changing).
            _VOLATILE = {
                "created_at",
                "updated_at",
                "source_updated_at",
                "_content_hash",
                "change_detected",
                "change_occurred",
            }
            stable_payload = {k: v for k, v in payload.items() if k not in _VOLATILE}
            content_hash = hashlib.sha256(
                json.dumps(stable_payload, sort_keys=True, default=str).encode()
            ).hexdigest()
            # Update last_seen on every run, even if unchanged
            ref.last_seen = datetime.now(timezone.utc)
            # Propagate a discovered status onto the model row. register()
            # returns existing refs unchanged, so a connector-derived status
            # must be applied here for update_model() to persist it. This runs
            # before the dedup check so the row self-corrects even when the
            # snapshot is skipped as unchanged.
            if node_status is not None and node_status != ref.status:
                ref.status = node_status
            self._backend.update_model(ref)

            if existing_hashes.get(ref.model_hash) == content_hash:
                skipped += 1
                continue

            payload["_content_hash"] = content_hash
            payload["change_detected"] = datetime.now(timezone.utc).isoformat()
            if node.metadata.get("source_updated_at"):
                payload["change_occurred"] = node.metadata["source_updated_at"]
            self.record(
                ref,
                event="discovered",
                payload=payload,
                actor=f"connector:{node.platform}" if node.platform else "system",
            )
            added += 1

        return {"added": added, "skipped": skipped}

    def connect(self) -> ConnectResult:
        """Match output ports to input ports. Write only new dependency links.

        Uses cached nodes from add() if available (avoids re-reading from backend).
        Preloads existing edges to skip duplicates.
        """
        from collections import defaultdict

        # Use cached nodes from add() if available, otherwise load from backend
        nodes = self._node_cache if self._node_cache else self._load_discovered_nodes()

        # Build output port index
        output_index = defaultdict(list)
        for node in nodes:
            for port in node.outputs:
                output_index[port.identifier].append((node, port))

        # Preload existing edges to skip duplicates
        existing_edges: set[tuple[str, str]] = set()
        if hasattr(self._backend, "list_all_snapshots"):
            hash_to_name = {ref.model_hash: name for name, ref in self._name_cache.items()}
            for s in self._backend.list_all_snapshots(event_type="depends_on"):
                upstream = s.payload.get("upstream")
                downstream = hash_to_name.get(s.model_hash)
                if upstream and downstream:
                    existing_edges.add((upstream, downstream))

        # Match ports and write only new edges
        links_created = 0
        links_skipped = 0
        seen = set()
        for node in nodes:
            for in_port in node.inputs:
                for upstream_node, out_port in output_index.get(in_port.identifier, []):
                    if upstream_node.name == node.name:
                        continue
                    if out_port != in_port:
                        continue
                    key = (upstream_node.name, node.name)
                    if key in seen:
                        continue
                    seen.add(key)
                    if key in existing_edges:
                        links_skipped += 1
                        continue
                    try:
                        self.link_dependency(
                            upstream=upstream_node.name,
                            downstream=node.name,
                            relationship="data_flow",
                            actor="graph_builder",
                            metadata={
                                "via": in_port.identifier,
                                "via_schema": in_port.schema if in_port.schema else None,
                            },
                        )
                        links_created += 1
                    except ModelNotFoundError:
                        continue
        return {"links_created": links_created, "links_skipped": links_skipped}

    def trace(self, name: str) -> builtins.list[str]:
        """Topological path from sources to this node."""
        self._resolve_model(name)
        visited = set()
        order = []

        def _walk(n):
            if n in visited:
                return
            visited.add(n)
            for dep in self.dependencies(n, direction="upstream"):
                _walk(dep["model"].name)
            order.append(n)

        _walk(name)
        return order

    def upstream(self, name: str) -> builtins.list[str]:
        """All models this one depends on (transitive)."""
        path = self.trace(name)
        return [n for n in path if n != name]

    def downstream(self, name: str) -> builtins.list[str]:
        """All models that depend on this one (transitive)."""
        self._resolve_model(name)
        visited = set()
        result = []

        def _walk(n):
            for dep in self.dependencies(n, direction="downstream"):
                child = dep["model"].name
                if child not in visited:
                    visited.add(child)
                    result.append(child)
                    _walk(child)

        _walk(name)
        return result

    def register_group(
        self,
        *,
        name: str,
        owner: str,
        model_type: str,
        tier: str,
        purpose: str,
        members: builtins.list[str],
        actor: str,
        metadata: dict[str, Any] | None = None,
    ) -> ModelRef:
        """Register a governed model group and link its members.

        A group is a business-level entity that aggregates technical components.
        Members are linked via relationship="member_of".

        Example:
            >>> group = ledger.register_group(
            ...     name="Credit Scorecard", owner="risk-team",
            ...     model_type="ml_model", tier="high",
            ...     purpose="Credit risk scoring pipeline",
            ...     members=["feature_pipeline", "scoring_model", "alert_queue"],
            ...     actor="system",
            ... )
        """
        ref = self.register(
            name=name,
            owner=owner,
            model_type=model_type,
            tier=tier,
            purpose=purpose,
            actor=actor,
            metadata=metadata,
        )
        for member in members or []:
            self.link_dependency(
                upstream=member,
                downstream=name,
                relationship="member_of",
                actor=actor,
            )
        return ref

    def members(
        self,
        group: ModelRef | str,
        *,
        snapshots: builtins.list[Snapshot] | None = None,
    ) -> builtins.list[ModelRef]:
        """Return current members of this group.

        Replays member_added/member_removed snapshots to determine
        current membership. Falls back to dependency links if no
        membership events exist (backward compatible with register_group).

        Mixed case: groups seeded via register_group() that later have
        add_member()/remove_member() called use dependency links as the
        baseline and overlay the event log on top.

        All member_added targets are resolved in a single batched lookup
        instead of one round trip per event. Pass ``snapshots`` (the group's
        full history) to reuse an already-fetched list.
        """
        ref = self._resolve_model(group)
        snaps = snapshots if snapshots is not None else self._backend.list_snapshots(ref.model_hash)
        membership_events = [s for s in snaps if s.event_type in ("member_added", "member_removed")]

        # Seed from dependency links (covers register_group() seeded members
        # and is always correct as the initial universe of linked models).
        # Reuse the snapshots we already have — dependency edges live in the
        # same history.
        deps = self.dependencies(group, direction="upstream", snapshots=snaps) or []
        current: dict[str, ModelRef] = {
            d["model"].model_hash: d["model"] for d in deps if d.get("relationship") == "member_of"
        }

        if not membership_events:
            # No events: dependency links are the full picture.
            return list(current.values())

        ordered_events = sorted(membership_events, key=lambda s: s.timestamp)

        # Batch-resolve every member_added hash not already seeded, in one
        # round trip. The name fallback (for the rare unresolvable hash) stays
        # per-event but only fires when the bulk lookup misses.
        added_hashes = [
            s.payload.get("member_hash", "")
            for s in ordered_events
            if s.event_type == "member_added" and s.payload.get("member_hash", "") not in current
        ]
        resolved = self._resolve_hashes([h for h in added_hashes if h])

        # Replay events on top of the dep-link baseline.
        for s in ordered_events:
            member_hash = s.payload.get("member_hash", "")
            if s.event_type == "member_added":
                if member_hash not in current:
                    ref_for_member = resolved.get(member_hash)
                    if ref_for_member is not None:
                        current[member_hash] = ref_for_member
                    else:
                        member_name = s.payload.get("member_name", "")
                        if member_name:
                            try:
                                current[member_hash] = self.get(member_name)
                            except ModelNotFoundError:
                                continue
            elif s.event_type == "member_removed":
                current.pop(member_hash, None)
        return list(current.values())

    def groups(
        self,
        model: ModelRef | str,
        *,
        snapshots: builtins.list[Snapshot] | None = None,
    ) -> builtins.list[ModelRef]:
        """Return groups this model currently belongs to.

        Replays member_added/member_removed events on each candidate group
        to exclude composites the model has been removed from. The candidate
        composites' membership histories are fetched in a single bulk
        ``list_all_snapshots`` scan when the backend supports it, so the cost
        is one query for the whole fan-out rather than one per candidate.

        Pass ``snapshots`` (this model's full history) to reuse an
        already-fetched list for the downstream-edge discovery.
        """
        deps = self.dependencies(model, direction="downstream", snapshots=snapshots) or []
        candidates = [d["model"] for d in deps if d.get("relationship") == "member_of"]
        if not candidates:
            return []
        ref = self._resolve_model(model)

        # Resolve each candidate's current members. Prefer a single bulk
        # snapshot scan over per-candidate list_snapshots round trips.
        snaps_by_group = self._membership_snapshots({c.model_hash for c in candidates})

        result: builtins.list[ModelRef] = []
        for comp in candidates:
            comp_snaps = snaps_by_group.get(comp.model_hash)
            current_members = self.members(comp, snapshots=comp_snaps)
            if any(m.model_hash == ref.model_hash for m in current_members):
                result.append(comp)
        return result

    def _membership_snapshots(
        self,
        group_hashes: builtins.set[str],
    ) -> dict[str, builtins.list[Snapshot]]:
        """Group the membership-relevant snapshots for several groups at once.

        Returns ``{group_hash: [snapshots]}``. When the backend exposes
        ``list_all_snapshots`` the whole fan-out is one scan; otherwise this
        returns an empty mapping and callers fall back to per-group
        ``list_snapshots`` (preserving the protocol-only contract).
        """
        if not group_hashes or not hasattr(self._backend, "list_all_snapshots"):
            return {}
        by_group: dict[str, builtins.list[Snapshot]] = {h: [] for h in group_hashes}
        for s in self._backend.list_all_snapshots():
            bucket = by_group.get(s.model_hash)
            if bucket is not None:
                bucket.append(s)
        return by_group

    def add_member(
        self,
        composite: ModelRef | str,
        member: ModelRef | str,
        *,
        role: str | None = None,
        actor: str,
    ) -> Snapshot:
        """Add a member to a composite.

        Records a member_added snapshot on the composite and creates
        a member_of dependency link.
        """
        comp_ref = self._resolve_model(composite)
        mem_ref = self._resolve_model(member)
        self.link_dependency(
            upstream=mem_ref,
            downstream=comp_ref,
            relationship="member_of",
            actor=actor,
        )
        payload: dict[str, Any] = {
            "member_name": mem_ref.name,
            "member_hash": mem_ref.model_hash,
        }
        if role is not None:
            payload["role"] = role
        return self.record(
            comp_ref,
            event="member_added",
            payload=payload,
            actor=actor,
        )

    def remove_member(
        self,
        composite: ModelRef | str,
        member: ModelRef | str,
        *,
        reason: str | None = None,
        actor: str,
    ) -> Snapshot:
        """Remove a member from a composite.

        Records a member_removed snapshot. The dependency link is NOT deleted
        (append-only event log). members() will exclude removed members by
        replaying member_added/member_removed events.
        """
        comp_ref = self._resolve_model(composite)
        mem_ref = self._resolve_model(member)
        payload: dict[str, Any] = {
            "member_name": mem_ref.name,
            "member_hash": mem_ref.model_hash,
        }
        if reason is not None:
            payload["reason"] = reason
        return self.record(
            comp_ref,
            event="member_removed",
            payload=payload,
            actor=actor,
        )

    def membership_at(
        self,
        composite: ModelRef | str,
        date: datetime,
    ) -> builtins.list[ModelRef]:
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        """Reconstruct composite membership at a point in time.

        Seeds from dependency links established on or before *date* (so groups
        created with register_group(members=[...]) are covered), then overlays
        member_added/member_removed events up to *date*.  This mirrors the
        strategy used by members() and handles every membership pathway.
        """
        ref = self._resolve_model(composite)
        snaps = self._backend.list_snapshots(ref.model_hash)

        # Seed from dependency links that existed at or before the query date.
        # depends_on snapshots on the composite record when each member_of link
        # was established.
        dep_link_snaps = [
            s
            for s in snaps
            if s.event_type == "depends_on"
            and s.payload.get("relationship") == "member_of"
            and s.timestamp <= date
        ]
        current: dict[str, ModelRef] = {}
        for s in dep_link_snaps:
            upstream_hash = s.payload.get("upstream_hash", "")
            if upstream_hash and upstream_hash not in current:
                try:
                    current[upstream_hash] = self.get(upstream_hash)
                except ModelNotFoundError:
                    upstream_name = s.payload.get("upstream", "")
                    if upstream_name:
                        try:
                            current[upstream_hash] = self.get(upstream_name)
                        except ModelNotFoundError:
                            continue

        # Overlay explicit membership events on top of the dep-link baseline.
        membership_events = sorted(
            [
                s
                for s in snaps
                if s.event_type in ("member_added", "member_removed") and s.timestamp <= date
            ],
            key=lambda s: s.timestamp,
        )
        for s in membership_events:
            member_hash = s.payload.get("member_hash", "")
            if s.event_type == "member_added":
                if member_hash not in current:
                    try:
                        current[member_hash] = self.get(member_hash)
                    except ModelNotFoundError:
                        member_name = s.payload.get("member_name", "")
                        if member_name:
                            try:
                                current[member_hash] = self.get(member_name)
                            except ModelNotFoundError:
                                continue
            elif s.event_type == "member_removed":
                current.pop(member_hash, None)
        return list(current.values())

    def record_observation(
        self,
        composite: ModelRef | str,
        *,
        observation_id: str,
        observation: str,
        status: str,
        severity: str | None = None,
        actor: str,
        metadata: dict[str, Any] | None = None,
    ) -> Snapshot:
        """Record an observation against a composite."""
        payload: dict[str, Any] = {
            "observation_id": observation_id,
            "observation": observation,
            "status": status,
        }
        if severity is not None:
            payload["severity"] = severity
        if metadata:
            payload.update(metadata)
        return self.record(composite, event="observation_issued", payload=payload, actor=actor)

    def resolve_observation(
        self,
        composite: ModelRef | str,
        *,
        observation_id: str,
        resolution: str,
        actor: str,
        metadata: dict[str, Any] | None = None,
    ) -> Snapshot:
        """Record the resolution of an observation."""
        payload: dict[str, Any] = {
            "observation_id": observation_id,
            "resolution": resolution,
        }
        if metadata:
            payload.update(metadata)
        return self.record(composite, event="observation_resolved", payload=payload, actor=actor)

    def record_validation(
        self,
        composite: ModelRef | str,
        *,
        result: str,
        actor: str,
        metadata: dict[str, Any] | None = None,
    ) -> Snapshot:
        """Record a validation result against a composite."""
        payload: dict[str, Any] = {"result": result}
        if metadata:
            payload.update(metadata)
        return self.record(composite, event="validated", payload=payload, actor=actor)

    @staticmethod
    def open_observation_count(snapshots: builtins.list[Snapshot]) -> int:
        """Return the number of observations that have been issued but not resolved.

        Accepts any iterable of Snapshots.  Only observation_issued and
        observation_resolved events that carry an ``observation_id`` payload key
        are considered; all other snapshots are ignored.
        """
        issued_ids: set[str] = set()
        resolved_ids: set[str] = set()
        for s in sorted(snapshots, key=lambda snap: snap.timestamp):
            obs_id = s.payload.get("observation_id")
            if not obs_id:
                continue
            if s.event_type == "observation_issued":
                issued_ids.add(obs_id)
            elif s.event_type == "observation_resolved":
                resolved_ids.add(obs_id)
        return len(issued_ids - resolved_ids)

    def composite_summary(
        self,
        model_types: builtins.list[str] | None = None,
    ) -> builtins.list[dict[str, Any]]:
        """Flat inventory of all composites with derived fields.

        By default, returns models whose ``model_type == "composite"``. Pass
        ``model_types=["composite", "ml_model", "heuristic"]`` (or any subset)
        to include other types the caller treats as composites.
        """
        types_list = model_types or ["composite"]
        if hasattr(self._backend, "composite_summary"):
            result: builtins.list[dict[str, Any]] = self._backend.composite_summary(
                model_types=types_list
            )
            return result

        target_types = set(types_list)
        all_models = self._backend.list_models()
        composites = [m for m in all_models if m.model_type in target_types]
        result = []
        for comp in composites:
            snaps = self._backend.list_snapshots(comp.model_hash)
            member_count = len(self.members(comp))
            validated_snaps = [s for s in snaps if s.event_type == "validated"]
            last_validated = max(s.timestamp for s in validated_snaps) if validated_snaps else None
            result.append(
                {
                    "name": comp.name,
                    "owner": comp.owner,
                    "tier": comp.tier,
                    "status": comp.status,
                    "model_type": comp.model_type,
                    "member_count": member_count,
                    "last_validated": last_validated,
                    "open_observation_count": self.open_observation_count(snaps),
                    "metadata": comp.metadata or {},
                }
            )
        return result

    def _load_discovered_nodes(self) -> builtins.list[DataNode]:
        """Rebuild DataNodes from stored discovery snapshots.

        Uses bulk loading if the backend supports it (1 query instead of N).
        """
        from collections import defaultdict

        from model_ledger.graph.models import DataNode, DataPort

        models = self._backend.list_models()
        model_by_hash = {m.model_hash: m for m in models}

        # Bulk load: one query for all discovered snapshots
        if hasattr(self._backend, "list_all_snapshots"):
            all_snaps = self._backend.list_all_snapshots(event_type="discovered")
        else:
            # Fallback: per-model queries
            all_snaps = []
            for m in models:
                all_snaps.extend(
                    self._backend.list_snapshots(m.model_hash, event_type="discovered")
                )

        # Group by model and take latest
        by_model: dict[str, list] = defaultdict(list)
        for s in all_snaps:
            by_model[s.model_hash].append(s)

        nodes = []
        for model_hash, snaps in by_model.items():
            model = model_by_hash.get(model_hash)
            if not model:
                continue
            latest = max(snaps, key=lambda s: s.timestamp)
            payload = latest.payload
            inputs = [
                DataPort(p["identifier"], **{k: v for k, v in p.items() if k != "identifier"})
                for p in payload.get("inputs", [])
            ]
            outputs = [
                DataPort(p["identifier"], **{k: v for k, v in p.items() if k != "identifier"})
                for p in payload.get("outputs", [])
            ]
            nodes.append(
                DataNode(
                    name=model.name,
                    platform=payload.get("platform", ""),
                    inputs=inputs,
                    outputs=outputs,
                    metadata={
                        k: v
                        for k, v in payload.items()
                        if k not in ("platform", "inputs", "outputs")
                    },
                )
            )
        return nodes
