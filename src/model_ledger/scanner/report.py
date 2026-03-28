"""ScanReport — summary of a scanner run."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from model_ledger.scanner.protocol import ModelCandidate


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ScanReport(BaseModel):
    """Summary of what a scanner found."""

    platform: str
    timestamp: datetime = Field(default_factory=_now)
    total_found: int
    new_models: int
    updated_models: int
    not_found_models: int
    candidates: list[ModelCandidate]
