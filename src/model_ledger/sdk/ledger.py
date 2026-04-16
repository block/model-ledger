"""Ledger SDK — tool-shaped API for v0.3.0 event-log paradigm."""

from __future__ import annotations

import builtins
from datetime import datetime, timezone
from typing import Any

from model_ledger.backends.ledger_memory import InMemoryLedgerBackend
from model_ledger.backends.ledger_protocol import LedgerBackend
from model_ledger.core.exceptions import ModelNotFoundError
from model_ledger.core.ledger_models import ModelRef, Snapshot, Tag

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
                parent_composites = self.groups(model)
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
    ) -> builtins.list[dict[str, Any]]:
        ref = self._resolve_model(model)
        snaps = self._backend.list_snapshots(ref.model_hash)
        result: builtins.list[dict[str, Any]] = []

        if direction in ("upstream", "both"):
            for s in snaps:
                if s.event_type == "depends_on":
                    try:
                        upstream = self.get(s.payload["upstream_hash"])
                    except ModelNotFoundError:
                        continue
                    result.append(
                        {
                            "model": upstream,
                            "relationship": s.payload.get("relationship", "depends_on"),
                            "direction": "upstream",
                        }
                    )

        if direction in ("downstream", "both"):
            for s in snaps:
                if s.event_type == "has_dependent":
                    try:
                        downstream = self.get(s.payload["downstream_hash"])
                    except ModelNotFoundError:
                        continue
                    result.append(
                        {
                            "model": downstream,
                            "relationship": s.payload.get("relationship", "depends_on"),
                            "direction": "downstream",
                        }
                    )

        return result

    # --- Graph methods (v0.4.0) ---

    def add(self, nodes):
        """Register DataNodes. Each becomes a ModelRef + discovered Snapshot.

        Skips writing if the discovered payload is identical to the last snapshot
        (content-hash dedup). Preloads existing models in bulk to avoid per-node queries.
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

    def connect(self):
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

    def trace(self, name):
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

    def upstream(self, name):
        """All models this one depends on (transitive)."""
        path = self.trace(name)
        return [n for n in path if n != name]

    def downstream(self, name):
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
        )
        for member in members or []:
            self.link_dependency(
                upstream=member,
                downstream=name,
                relationship="member_of",
                actor=actor,
                metadata=metadata,
            )
        return ref

    def members(self, group: ModelRef | str) -> builtins.list[ModelRef]:
        """Return current members of this group.

        Replays member_added/member_removed snapshots to determine
        current membership. Falls back to dependency links if no
        membership events exist (backward compatible with register_group).

        Mixed case: groups seeded via register_group() that later have
        add_member()/remove_member() called use dependency links as the
        baseline and overlay the event log on top.
        """
        ref = self._resolve_model(group)
        snaps = self._backend.list_snapshots(ref.model_hash)
        membership_events = [s for s in snaps if s.event_type in ("member_added", "member_removed")]

        # Seed from dependency links (covers register_group() seeded members
        # and is always correct as the initial universe of linked models).
        deps = self.dependencies(group, direction="upstream") or []
        current: dict[str, ModelRef] = {
            d["model"].model_hash: d["model"] for d in deps if d.get("relationship") == "member_of"
        }

        if not membership_events:
            # No events: dependency links are the full picture.
            return list(current.values())

        # Replay events on top of the dep-link baseline.
        for s in sorted(membership_events, key=lambda s: s.timestamp):
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

    def groups(self, model: ModelRef | str) -> builtins.list[ModelRef]:
        """Return all groups this model belongs to."""
        deps = self.dependencies(model, direction="downstream") or []
        return [d["model"] for d in deps if d.get("relationship") == "member_of"]

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
    def _open_observation_count(snapshots: builtins.list[Snapshot]) -> int:
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

    def composite_summary(self) -> builtins.list[dict[str, Any]]:
        """Flat inventory of all composites with derived fields."""
        composites = self._backend.list_models(model_type="composite")
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
                    "member_count": member_count,
                    "last_validated": last_validated,
                    "open_observation_count": self._open_observation_count(snaps),
                }
            )
        return result

    def _load_discovered_nodes(self):
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
            for model in models:
                all_snaps.extend(
                    self._backend.list_snapshots(model.model_hash, event_type="discovered")
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
