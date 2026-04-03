"""In-memory backend for testing — v0.3.0."""

from __future__ import annotations

from datetime import datetime

from model_ledger.core.ledger_models import ModelRef, Snapshot, Tag


class InMemoryLedgerBackend:
    def __init__(self) -> None:
        self._models: dict[str, ModelRef] = {}
        self._snapshots: list[Snapshot] = []
        self._tags: dict[tuple[str, str], Tag] = {}

    def save_model(self, model: ModelRef) -> None:
        self._models[model.model_hash] = model

    def get_model(self, model_hash: str) -> ModelRef | None:
        return self._models.get(model_hash)

    def get_model_by_name(self, name: str) -> ModelRef | None:
        for m in self._models.values():
            if m.name == name:
                return m
        return None

    def list_models(self, **filters: str) -> list[ModelRef]:
        results = list(self._models.values())
        for key, value in filters.items():
            results = [m for m in results if getattr(m, key, None) == value]
        return results

    def update_model(self, model: ModelRef) -> None:
        self._models[model.model_hash] = model

    def append_snapshot(self, snapshot: Snapshot) -> None:
        self._snapshots.append(snapshot)

    def get_snapshot(self, snapshot_hash: str) -> Snapshot | None:
        for s in self._snapshots:
            if s.snapshot_hash == snapshot_hash:
                return s
        return None

    def list_snapshots(self, model_hash: str, **filters: str) -> list[Snapshot]:
        results = [s for s in self._snapshots if s.model_hash == model_hash]
        for key, value in filters.items():
            results = [s for s in results if getattr(s, key, None) == value]
        return results

    def list_all_snapshots(self, event_type: str | None = None) -> list[Snapshot]:
        if event_type:
            return [s for s in self._snapshots if s.event_type == event_type]
        return list(self._snapshots)

    def latest_snapshot(self, model_hash: str, tag: str | None = None) -> Snapshot | None:
        if tag:
            t = self.get_tag(model_hash, tag)
            if t:
                return self.get_snapshot(t.snapshot_hash)
            return None
        snaps = self.list_snapshots(model_hash)
        if not snaps:
            return None
        return max(snaps, key=lambda s: s.timestamp)

    def list_snapshots_before(
        self, model_hash: str, before: datetime,
        event_type: str | None = None,
    ) -> list[Snapshot]:
        results = [
            s for s in self._snapshots
            if s.model_hash == model_hash and s.timestamp < before
        ]
        if event_type is not None:
            results = [s for s in results if s.event_type == event_type]
        return results

    def set_tag(self, tag: Tag) -> None:
        self._tags[(tag.model_hash, tag.name)] = tag

    def get_tag(self, model_hash: str, name: str) -> Tag | None:
        return self._tags.get((model_hash, name))

    def list_tags(self, model_hash: str) -> list[Tag]:
        return [t for t in self._tags.values() if t.model_hash == model_hash]
