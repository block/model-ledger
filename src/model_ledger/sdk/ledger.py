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

    def _resolve_model(self, model: ModelRef | str) -> ModelRef:
        if isinstance(model, ModelRef):
            return model
        result = self._backend.get_model_by_name(model)
        if result is None:
            result = self._backend.get_model(model)
        if result is None:
            raise ModelNotFoundError(f"Model not found: {model}")
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
        existing = self._backend.get_model_by_name(name)
        if existing is not None:
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
