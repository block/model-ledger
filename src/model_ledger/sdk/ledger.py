"""Ledger SDK — tool-shaped API for v0.3.0 event-log paradigm."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from model_ledger.backends.ledger_memory import InMemoryLedgerBackend
from model_ledger.backends.ledger_protocol import LedgerBackend
from model_ledger.core.ledger_models import ModelRef, Snapshot, Tag


class ModelNotFoundError(Exception):
    pass


class Ledger:
    """The main entry point for model-ledger v0.3.0.

    Every public method is designed to work as an agent tool call:
    clear inputs, JSON-serializable outputs, no side effects beyond the ledger.
    """

    def __init__(self, backend: LedgerBackend | None = None) -> None:
        self._backend = backend or InMemoryLedgerBackend()
        self._name_cache: dict[str, ModelRef] = {}

    def _resolve_model(self, model: ModelRef | str) -> ModelRef:
        if isinstance(model, ModelRef):
            return model
        if model in self._name_cache:
            return self._name_cache[model]
        result = self._backend.get_model_by_name(model)
        if result is None:
            result = self._backend.get_model(model)
        if result is None:
            raise ModelNotFoundError(f"Model not found: {model}")
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
        existing = self._backend.get_model_by_name(name)
        if existing is not None:
            self._name_cache[name] = existing
            return existing
        model = ModelRef(
            name=name, owner=owner, model_type=model_type,
            model_origin=model_origin,
            tier=tier, purpose=purpose, status=status,
        )
        self._backend.save_model(model)
        self._backend.append_snapshot(Snapshot(
            model_hash=model.model_hash, actor=actor,
            event_type="registered",
            payload={
                "name": name, "owner": owner,
                "tier": tier, "purpose": purpose,
                "model_origin": model_origin,
            },
        ))
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
        return snapshot

    def tag(self, model: ModelRef | str, name: str) -> Tag:
        ref = self._resolve_model(model)
        latest = self._backend.latest_snapshot(ref.model_hash)
        if latest is None:
            raise ModelNotFoundError(f"No snapshots for model: {ref.name}")
        tag = Tag(
            name=name, model_hash=ref.model_hash,
            snapshot_hash=latest.snapshot_hash,
        )
        self._backend.set_tag(tag)
        return tag

    def get(self, name_or_hash: str) -> ModelRef:
        result = self._backend.get_model_by_name(name_or_hash)
        if result is None:
            result = self._backend.get_model(name_or_hash)
        if result is None:
            raise ModelNotFoundError(f"Model not found: {name_or_hash}")
        return result

    def list(self, **filters: str) -> list[ModelRef]:
        return self._backend.list_models(**filters)

    def history(
        self, model: ModelRef | str, **filters: str,
    ) -> list[Snapshot]:
        ref = self._resolve_model(model)
        snaps = self._backend.list_snapshots(ref.model_hash, **filters)
        return sorted(snaps, key=lambda s: s.timestamp, reverse=True)

    def latest(
        self, model: ModelRef | str, tag: str | None = None,
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
    ) -> list[ModelRef]:
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
    ) -> list[dict[str, Any]]:
        ref = self._resolve_model(model)
        snaps = self._backend.list_snapshots(ref.model_hash)
        result: list[dict[str, Any]] = []

        if direction in ("upstream", "both"):
            for s in snaps:
                if s.event_type == "depends_on":
                    try:
                        upstream = self.get(s.payload["upstream_hash"])
                    except ModelNotFoundError:
                        continue
                    result.append({
                        "model": upstream,
                        "relationship": s.payload.get("relationship", "depends_on"),
                        "direction": "upstream",
                    })

        if direction in ("downstream", "both"):
            for s in snaps:
                if s.event_type == "has_dependent":
                    try:
                        downstream = self.get(s.payload["downstream_hash"])
                    except ModelNotFoundError:
                        continue
                    result.append({
                        "model": downstream,
                        "relationship": s.payload.get("relationship", "depends_on"),
                        "direction": "downstream",
                    })

        return result

    # --- Graph methods (v0.4.0) ---

    def add(self, nodes):
        """Register DataNodes. Each becomes a ModelRef + discovered Snapshot.

        Skips writing if the discovered payload is identical to the last snapshot
        (content-hash dedup). Preloads existing models in bulk to avoid per-node queries.
        """
        import hashlib
        import json
        from model_ledger.graph.models import DataNode, DataPort

        if isinstance(nodes, DataNode):
            nodes = [nodes]

        # Preload name cache if backend supports bulk listing
        if not self._name_cache and hasattr(self._backend, "list_models"):
            for m in self._backend.list_models():
                self._name_cache[m.name] = m

        # Preload last discovered snapshot hashes for dedup
        existing_hashes: dict[str, str] = {}
        if hasattr(self._backend, "list_all_snapshots"):
            for s in self._backend.list_all_snapshots(event_type="discovered"):
                # Keep the latest per model_hash
                existing_hashes[s.model_hash] = hashlib.sha256(
                    json.dumps(s.payload, sort_keys=True, default=str).encode()
                ).hexdigest()

        added = 0
        skipped = 0
        for node in nodes:
            ref = self.register(
                name=node.name,
                owner=node.metadata.get("owner") or "unknown",
                model_type=node.metadata.get("node_type") or "unknown",
                tier=node.metadata.get("tier") or "unclassified",
                purpose=node.metadata.get("purpose") or "",
                model_origin=node.metadata.get("model_origin") or "internal",
                actor=f"connector:{node.platform}" if node.platform else "system",
            )
            payload = {
                "platform": node.platform,
                "inputs": [{"identifier": p.identifier, **p.schema} for p in node.inputs],
                "outputs": [{"identifier": p.identifier, **p.schema} for p in node.outputs],
                **{k: v for k, v in node.metadata.items()
                   if k not in ("owner", "node_type", "tier", "purpose", "model_origin")},
            }

            # Content-hash dedup: skip if payload unchanged
            payload_hash = hashlib.sha256(
                json.dumps(payload, sort_keys=True, default=str).encode()
            ).hexdigest()
            if existing_hashes.get(ref.model_hash) == payload_hash:
                skipped += 1
                continue

            self.record(
                ref,
                event="discovered",
                payload=payload,
                actor=f"connector:{node.platform}" if node.platform else "system",
            )
            added += 1

        return {"added": added, "skipped": skipped}

    def connect(self):
        """Match output ports to input ports. Write dependency links."""
        from collections import defaultdict
        from model_ledger.graph.models import DataNode, DataPort
        nodes = self._load_discovered_nodes()
        output_index = defaultdict(list)
        for node in nodes:
            for port in node.outputs:
                output_index[port.identifier].append((node, port))
        links_created = 0
        seen = set()
        for node in nodes:
            for in_port in node.inputs:
                for upstream_node, out_port in output_index.get(in_port.identifier, []):
                    if upstream_node.name == node.name:
                        continue
                    if not (out_port == in_port):
                        continue
                    key = (upstream_node.name, node.name)
                    if key in seen:
                        continue
                    seen.add(key)
                    try:
                        self.link_dependency(
                            upstream=upstream_node.name,
                            downstream=node.name,
                            relationship="data_flow",
                            actor="graph_builder",
                            metadata={"via": in_port.identifier, "via_schema": in_port.schema if in_port.schema else None},
                        )
                        links_created += 1
                    except ModelNotFoundError:
                        continue
        return {"links_created": links_created}

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
                all_snaps.extend(self._backend.list_snapshots(model.model_hash, event_type="discovered"))

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
            nodes.append(DataNode(
                name=model.name, platform=payload.get("platform", ""),
                inputs=inputs, outputs=outputs,
                metadata={k: v for k, v in payload.items() if k not in ("platform", "inputs", "outputs")},
            ))
        return nodes
