"""HTTP LedgerBackend — connects to a remote model-ledger REST API.

This backend delegates all operations to a deployed model-ledger server,
enabling a local MCP server to work with a remote inventory without
direct database credentials.

    >>> from model_ledger.backends.http import HttpLedgerBackend
    >>> backend = HttpLedgerBackend("https://model-ledger.internal:8000")
    >>> ledger = Ledger(backend=backend)

The remote server must be running `model-ledger serve` (FastAPI).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from model_ledger.core.exceptions import ModelNotFoundError
from model_ledger.core.ledger_models import ModelRef, Snapshot, Tag


class HttpLedgerBackend:
    """LedgerBackend that delegates to a remote REST API."""

    def __init__(self, base_url: str, headers: dict[str, str] | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self._base_url,
            headers=headers or {},
            timeout=30.0,
        )
        # The REST API exchanges model_name (not model_hash) in every payload.
        # The SDK protocol uses model_hash. Without preserving the mapping we
        # cannot reverse-resolve on writes like set_tag. Populated lazily
        # whenever a name lookup succeeds (get_model_by_name, save_model, etc.).
        self._hash_to_name: dict[str, str] = {}

    # ── Models ──

    def save_model(self, model: ModelRef) -> None:
        self._client.post(
            "/record",
            json={
                "model_name": model.name,
                "event": "registered",
                "owner": model.owner,
                "model_type": model.model_type,
                "purpose": model.purpose,
                "payload": {},
            },
        )
        self._hash_to_name[model.model_hash] = model.name

    def get_model(self, model_hash: str) -> ModelRef | None:
        name = self._hash_to_name.get(model_hash)
        if name is not None:
            return self.get_model_by_name(name)
        # Fallback: iterate. Model identity reconstruction via /query is lossy
        # (ModelSummary omits created_at), so matches only work for models
        # whose name lookup has already populated the cache.
        for m in self.list_models():
            if m.model_hash == model_hash:
                return m
        return None

    def get_model_by_name(self, name: str) -> ModelRef | None:
        resp = self._client.get("/investigate/" + name)
        if resp.status_code == 404:
            return None
        data = resp.json()
        ref = ModelRef(
            name=data["name"],
            owner=data.get("owner") or "unknown",
            model_type=data.get("model_type") or "unknown",
            tier="unclassified",
            purpose=data.get("purpose") or "",
            status=data.get("status") or "active",
            created_at=data.get("created_at", datetime.now().isoformat()),
        )
        self._hash_to_name[ref.model_hash] = ref.name
        return ref

    def list_models(self, **filters: str) -> list[ModelRef]:
        params: dict[str, Any] = {"limit": 10000}
        params.update(filters)
        resp = self._client.get("/query", params=params)
        data = resp.json()
        models = []
        for m in data.get("models", []):
            models.append(
                ModelRef(
                    name=m["name"],
                    owner=m.get("owner") or "unknown",
                    model_type=m.get("model_type") or "unknown",
                    tier="unclassified",
                    purpose="",
                    status=m.get("status") or "active",
                )
            )
        return models

    def update_model(self, model: ModelRef) -> None:
        self._client.post(
            "/record",
            json={
                "model_name": model.name,
                "event": "metadata_updated",
                "payload": {"status": model.status},
            },
        )

    # ── Snapshots ──

    def append_snapshot(self, snapshot: Snapshot) -> None:
        self._client.post(
            "/record",
            json={
                "model_name": "",  # resolved server-side
                "event": snapshot.event_type,
                "payload": snapshot.payload,
                "actor": snapshot.actor,
            },
        )

    def get_snapshot(self, snapshot_hash: str) -> Snapshot | None:
        # Not directly exposed via REST — return None
        return None

    def list_snapshots(self, model_hash: str, **filters: str) -> list[Snapshot]:
        # Get model name from hash, then use changelog
        model = self.get_model(model_hash)
        if not model:
            return []
        params: dict[str, Any] = {"model_name": model.name, "limit": 10000}
        if "event_type" in filters:
            params["event_type"] = filters["event_type"]
        resp = self._client.get("/changelog", params=params)
        data = resp.json()
        return [
            Snapshot(
                model_hash=model_hash,
                actor=e.get("actor", "unknown"),
                event_type=e["event_type"],
                timestamp=e["timestamp"],
                payload=e.get("payload", {}),
            )
            for e in data.get("events", [])
        ]

    def latest_snapshot(
        self,
        model_hash: str,
        tag: str | None = None,
    ) -> Snapshot | None:
        snapshots = self.list_snapshots(model_hash)
        return snapshots[0] if snapshots else None

    def list_snapshots_before(
        self,
        model_hash: str,
        before: datetime,
        event_type: str | None = None,
    ) -> list[Snapshot]:
        snapshots = self.list_snapshots(model_hash)
        result = []
        for s in snapshots:
            ts = s.timestamp
            if ts.tzinfo is None:
                from datetime import timezone

                ts = ts.replace(tzinfo=timezone.utc)
            before_aware = before if before.tzinfo else before.replace(tzinfo=timezone.utc)
            if ts < before_aware and (event_type is None or s.event_type == event_type):
                result.append(s)
        return result

    # ── Tags ──

    def set_tag(self, tag: Tag) -> None:
        model = self.get_model(tag.model_hash)
        if model is None:
            raise ModelNotFoundError(tag.model_hash)
        self._client.post(
            "/tag",
            json={"model_name": model.name, "tag_name": tag.name},
        )

    def get_tag(self, model_hash: str, name: str) -> Tag | None:
        for t in self.list_tags(model_hash):
            if t.name == name:
                return t
        return None

    def list_tags(self, model_hash: str) -> list[Tag]:
        model = self.get_model(model_hash)
        if model is None:
            return []
        resp = self._client.get(f"/tags/{model.name}")
        if resp.status_code == 404:
            return []
        data = resp.json()
        return [
            Tag(
                name=t["tag_name"],
                model_hash=t["model_hash"],
                snapshot_hash=t["snapshot_hash"],
                updated_at=t["updated_at"],
            )
            for t in data.get("tags", [])
        ]

    # ── Cleanup ──

    def close(self) -> None:
        self._client.close()
