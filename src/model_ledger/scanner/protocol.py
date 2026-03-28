"""Scanner protocol — the interface all platform scanners implement."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ModelCandidate(BaseModel):
    """Raw discovery result from a scanner — not yet a ModelRef."""

    name: str
    owner: str | None = None
    model_type: str
    platform: str
    platform_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class Scanner(Protocol):
    """Discovers models/rules on a deployment platform (Phase A)."""

    name: str
    platform_type: str

    def scan(self) -> list[ModelCandidate]: ...
    def has_changed(self, last_scan: datetime) -> bool: ...


@runtime_checkable
class EnrichableScanner(Scanner, Protocol):
    """Scanner that can also fetch richer metadata (Phase B)."""

    def enrich(self, candidate: ModelCandidate) -> dict: ...
