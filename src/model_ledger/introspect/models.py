"""Typed data models for introspection results."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FeatureInfo(BaseModel):
    name: str
    dtype: str | None = None
    source: str | None = None
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DataSourceInfo(BaseModel):
    name: str
    source_type: str
    fields: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ThresholdInfo(BaseModel):
    name: str
    value: float | str
    segment: str | None = None
    operator: str | None = None
    description: str | None = None


class ComponentInfo(BaseModel):
    """Maps to a ComponentNode in the version's tree."""

    path: str
    node_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class IntrospectionResult(BaseModel):
    """Typed contract returned by all introspectors."""

    introspector: str
    framework: str | None = None
    algorithm: str | None = None
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    features: list[FeatureInfo] = Field(default_factory=list)
    data_sources: list[DataSourceInfo] = Field(default_factory=list)
    thresholds: list[ThresholdInfo] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    output_description: str | None = None
    execution_schedule: str | None = None
    lookback_window: str | None = None
    components: list[ComponentInfo] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
