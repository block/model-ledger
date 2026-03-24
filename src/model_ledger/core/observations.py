"""Observation and feedback models for validation lifecycle tracking."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Observation(BaseModel):
    """A validation finding from any source."""

    observation_id: str = Field(default_factory=_uuid)
    content: str
    priority: str | None = None
    pillar: str | None = None

    source_type: str  # human_reviewer, ai_agent, automated_tool, manual_entry
    source_detail: str | None = None
    model_version_ref: str

    status: str = "draft"  # draft, issued, removed

    extra_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)


class ValidationRun(BaseModel):
    """Groups observations from a single validation effort."""

    run_id: str = Field(default_factory=_uuid)
    timestamp: datetime = Field(default_factory=_now)
    source_type: str
    model_version_ref: str
    config_snapshot: dict[str, Any] = Field(default_factory=dict)

    observations: list[str] = Field(default_factory=list)  # observation IDs
    status: str = "draft"  # draft, superseded, final


class ValidationReport(BaseModel):
    """The published set of issued observations. Immutable after creation."""

    report_id: str = Field(default_factory=_uuid)
    model_version_ref: str
    issued_observations: list[str]  # observation IDs
    issued_at: datetime = Field(default_factory=_now)
    issued_by: str


class FeedbackEvent(BaseModel):
    """What happened to an observation and why. Append-only."""

    event_id: str = Field(default_factory=_uuid)
    observation_ref: str
    verdict: str  # keep, remove, modify
    reason_code: str
    rationale: str
    stage: str  # pipeline_filter, triage, stakeholder_review
    actor: str
    timestamp: datetime = Field(default_factory=_now)
