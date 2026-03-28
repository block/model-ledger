"""v0.3.0 data models — event-log paradigm with schema-free payloads."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, model_validator


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _compute_model_hash(name: str, owner: str, created_at: datetime) -> str:
    raw = f"{name}:{owner}:{created_at.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _compute_snapshot_hash(model_hash: str, timestamp: datetime, payload: dict) -> str:
    raw = f"{model_hash}:{timestamp.isoformat()}:{json.dumps(payload, sort_keys=True, default=str)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class ModelRef(BaseModel):
    """Regulatory identity — the minimum a regulator needs."""

    model_hash: str = ""
    name: str
    owner: str
    model_type: str
    tier: str
    purpose: str
    status: str = "active"
    created_at: datetime = Field(default_factory=_now)

    @model_validator(mode="after")
    def _set_hash(self) -> ModelRef:
        if not self.model_hash:
            self.model_hash = _compute_model_hash(self.name, self.owner, self.created_at)
        return self


class Snapshot(BaseModel):
    """Immutable, content-addressed observation of a model."""

    snapshot_hash: str = ""
    model_hash: str
    parent_hash: str | None = None
    timestamp: datetime = Field(default_factory=_now)
    actor: str
    event_type: str
    source: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    tags: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _set_hash(self) -> Snapshot:
        if not self.snapshot_hash:
            self.snapshot_hash = _compute_snapshot_hash(
                self.model_hash, self.timestamp, self.payload
            )
        return self


class Tag(BaseModel):
    """Mutable pointer from a name to a snapshot."""

    name: str
    model_hash: str
    snapshot_hash: str
    updated_at: datetime = Field(default_factory=_now)
