"""Pydantic I/O schemas for the 6 agent protocol tools.

These schemas are the single source of truth for the protocol contract.
They serialize to JSON Schema for MCP tools, OpenAPI docs, and any language.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------


class ModelSummary(BaseModel):
    """Compact model info returned by query and discover tools."""

    name: str
    owner: str | None = None
    model_type: str | None = None
    platform: str | None = None
    status: str | None = None
    last_event: datetime | None = None
    event_count: int = 0


class EventSummary(BaseModel):
    """Compact event returned in investigation results."""

    event_type: str
    timestamp: datetime | None = None
    actor: str | None = None
    summary: str | None = None


class EventDetail(EventSummary):
    """Full event with model association and payload."""

    model_name: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class DependencyNode(BaseModel):
    """A node in a dependency graph."""

    name: str
    platform: str | None = None
    depth: int = 0
    relationship: str | None = None


# ---------------------------------------------------------------------------
# record tool
# ---------------------------------------------------------------------------


class RecordInput(BaseModel):
    """Input for the record tool — log an event against a model."""

    model_name: str
    event: str
    payload: dict[str, Any] = Field(default_factory=dict)
    actor: str = "user"
    owner: str | None = None
    model_type: str | None = None
    purpose: str | None = None


class RecordOutput(BaseModel):
    """Output from the record tool."""

    model_name: str
    event_id: str
    timestamp: datetime
    is_new_model: bool


# ---------------------------------------------------------------------------
# query tool
# ---------------------------------------------------------------------------


class QueryInput(BaseModel):
    """Input for the query tool — search and filter models."""

    text: str | None = None
    platform: str | None = None
    model_type: str | None = None
    owner: str | None = None
    status: str | None = None
    limit: int = 50
    offset: int = 0


class QueryOutput(BaseModel):
    """Output from the query tool."""

    total: int
    models: list[ModelSummary]
    has_more: bool


# ---------------------------------------------------------------------------
# investigate tool
# ---------------------------------------------------------------------------


class InvestigateInput(BaseModel):
    """Input for the investigate tool — deep-dive into a single model."""

    model_name: str
    detail: Literal["summary", "full"] = "summary"
    as_of: datetime | None = None


class InvestigateOutput(BaseModel):
    """Output from the investigate tool."""

    name: str
    owner: str | None = None
    model_type: str | None = None
    purpose: str | None = None
    status: str | None = None
    created_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    recent_events: list[EventSummary] = Field(default_factory=list)
    days_since_last_event: int | None = None
    total_events: int = 0
    upstream: list[DependencyNode] = Field(default_factory=list)
    downstream: list[DependencyNode] = Field(default_factory=list)
    groups: list[str] = Field(default_factory=list)
    members: list[str] = Field(default_factory=list)
    last_validated: datetime | None = None
    open_observation_count: int | None = None


# ---------------------------------------------------------------------------
# trace tool
# ---------------------------------------------------------------------------


class TraceInput(BaseModel):
    """Input for the trace tool — follow dependency chains."""

    name: str
    direction: Literal["upstream", "downstream", "both"] = "both"
    depth: int | None = None


class TraceOutput(BaseModel):
    """Output from the trace tool."""

    root: str
    upstream: list[DependencyNode] = Field(default_factory=list)
    downstream: list[DependencyNode] = Field(default_factory=list)
    total_nodes: int = 0


# ---------------------------------------------------------------------------
# changelog tool
# ---------------------------------------------------------------------------


class ChangelogInput(BaseModel):
    """Input for the changelog tool — view event history."""

    since: datetime | None = None
    until: datetime | None = None
    model_name: str | None = None
    event_type: str | None = None
    limit: int = 100
    offset: int = 0


class ChangelogOutput(BaseModel):
    """Output from the changelog tool."""

    total: int
    events: list[EventDetail]
    has_more: bool
    period: str | None = None


# ---------------------------------------------------------------------------
# tag tool
# ---------------------------------------------------------------------------


class TagInput(BaseModel):
    """Input for the tag tool — create or move a tag to the latest snapshot."""

    model_name: str
    tag_name: str


class TagOutput(BaseModel):
    """Output from the tag tool — a tag pointing at a snapshot."""

    model_name: str
    tag_name: str
    model_hash: str
    snapshot_hash: str
    updated_at: datetime


class TagListOutput(BaseModel):
    """Output from the list-tags endpoint — all tags for a model."""

    model_name: str
    tags: list[TagOutput] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# discover tool
# ---------------------------------------------------------------------------


class DiscoverInput(BaseModel):
    """Input for the discover tool — import models from external sources."""

    source_type: Literal["connector", "file", "inline"]
    connector_name: str | None = None
    connector_config: dict[str, Any] | None = None
    file_path: str | None = None
    models: list[dict[str, Any]] | None = None
    auto_connect: bool = True


class DiscoverOutput(BaseModel):
    """Output from the discover tool."""

    models_added: int
    models_skipped: int
    links_created: int
    models: list[ModelSummary] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
