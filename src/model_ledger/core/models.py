"""Core Pydantic data models for model-ledger.

Covers SR 11-7, OCC 2021, PRA SS1/23, OSFI E-23, EU AI Act, and NIST AI RMF fields.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from model_ledger.core.enums import (
    ModelStatus,
    ModelType,
    RiskTier,
    VersionStatus,
)


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Supporting models ---


class Stakeholder(BaseModel):
    role: str
    name: str
    email: str | None = None


class GovernanceDoc(BaseModel):
    doc_type: str
    title: str
    url: str | None = None


class Reference(BaseModel):
    ref_type: str
    identifier: str
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Evidence(BaseModel):
    evidence_type: str
    title: str
    artifact_uri: str | None = None


class Finding(BaseModel):
    finding_id: str
    severity: str
    title: str
    status: str
    source: str | None = None
    description: str | None = None
    remediation_plan: str | None = None
    remediation_owner: str | None = None
    due_date: date | None = None
    closed_date: date | None = None
    closure_evidence: str | None = None
    impacted_nodes: list[str] = Field(default_factory=list)


class Exception_(BaseModel):
    exception_id: str
    description: str
    justification: str
    approved_by: str
    approved_date: date
    expiration_date: date | None = None
    status: str


class Overlay(BaseModel):
    description: str
    justification: str
    calculation_method: str | None = None
    applied_by: str
    applied_date: date


class ModelArtifact(BaseModel):
    artifact_type: str
    uri: str
    checksum: str | None = None
    storage_backend: str | None = None


class DeploymentRecord(BaseModel):
    environment: str
    endpoint: str | None = None
    deployment_strategy: str
    traffic_percentage: float | None = None
    deployed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelRiskRating(BaseModel):
    """4-factor Model Risk Rating calculator."""

    model_exposure: str
    output_reliance: str
    model_complexity: str
    input_uncertainty: str

    @staticmethod
    def _level(value: str) -> int:
        return {"low": 1, "medium": 2, "high": 3}[value.lower()]

    @property
    def impact(self) -> str:
        score = self._level(self.model_exposure) + self._level(self.output_reliance)
        if score >= 5:
            return "high"
        if score >= 3:
            return "medium"
        return "low"

    @property
    def likelihood(self) -> str:
        score = self._level(self.model_complexity) + self._level(self.input_uncertainty)
        if score >= 5:
            return "high"
        if score >= 3:
            return "medium"
        return "low"

    @property
    def overall_rating(self) -> str:
        total = self.score
        if total >= 10:
            return "high"
        if total >= 6:
            return "medium"
        return "low"

    @property
    def score(self) -> int:
        return (
            self._level(self.model_exposure)
            + self._level(self.output_reliance)
            + self._level(self.model_complexity)
            + self._level(self.input_uncertainty)
        )


# --- Component tree ---


class ComponentNode(BaseModel):
    node_id: str = Field(default_factory=_uuid)
    name: str
    node_type: str
    path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    children: list[ComponentNode] = Field(default_factory=list)


def _default_tree() -> ComponentNode:
    return ComponentNode(
        name="root",
        node_type="root",
        children=[
            ComponentNode(name="Inputs", node_type="category"),
            ComponentNode(name="Processing", node_type="category"),
            ComponentNode(name="Outputs", node_type="category"),
        ],
    )


# --- Audit event ---


class AuditEvent(BaseModel):
    event_id: str = Field(default_factory=_uuid)
    timestamp: datetime = Field(default_factory=_now)
    actor: str
    action: str
    model_name: str
    version: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None


# --- Model version ---


class ModelVersion(BaseModel):
    version: str
    status: VersionStatus = VersionStatus.DRAFT

    run_frequency: str | None = None
    deployment_mode: str | None = None
    deployment_date: date | None = None

    training_target: str | None = None
    training_data_description: str | None = None
    methodology_approach: str | None = None

    release_date: date | None = None
    last_validation_date: date | None = None
    last_validation_outcome: str | None = None
    next_validation_due: date | None = None
    monitoring_frequency: str | None = None
    monitoring_status: str | None = None
    last_updated: datetime | None = None

    tree: ComponentNode = Field(default_factory=_default_tree)

    upstream_models: list[str] = Field(default_factory=list)
    downstream_models: list[str] = Field(default_factory=list)

    documents: list[GovernanceDoc] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    exceptions: list[Exception_] = Field(default_factory=list)
    overlays: list[Overlay] = Field(default_factory=list)
    artifacts: list[ModelArtifact] = Field(default_factory=list)
    deployments: list[DeploymentRecord] = Field(default_factory=list)


# --- Top-level model ---


class Model(BaseModel):
    model_id: str = Field(default_factory=_uuid)
    name: str
    description: str | None = None
    model_type: ModelType = ModelType.ML_MODEL

    owner: str
    developers: list[str] = Field(default_factory=list)
    validator: str | None = None
    approver: str | None = None
    user_roles: list[str] = Field(default_factory=list)
    stakeholders: list[Stakeholder] = Field(default_factory=list)

    intended_purpose: str
    actual_use: str | None = None
    approved_uses: list[str] = Field(default_factory=list)
    restrictions_on_use: list[str] = Field(default_factory=list)
    operating_boundaries: str | None = None
    risk_type: str | None = None
    program: str | None = None
    business_unit: str | None = None

    tier: RiskTier
    risk_rating: ModelRiskRating | None = None
    materiality: str | None = None

    jurisdictions: list[str] = Field(default_factory=list)
    affected_populations: list[str] = Field(default_factory=list)
    potential_harms: list[str] = Field(default_factory=list)
    assumptions_and_limitations: list[str] = Field(default_factory=list)

    status: ModelStatus = ModelStatus.DEVELOPMENT
    created_at: datetime = Field(default_factory=_now)
    approval_date: date | None = None
    expected_valid_until: date | None = None
    functioning_properly: bool | None = None

    vendor: str | None = None
    vendor_documentation_url: str | None = None
    third_party_due_diligence: str | None = None

    versions: list[ModelVersion] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    def __repr__(self) -> str:
        return f"Model(name='{self.name}', tier='{self.tier.value}', status='{self.status.value}')"
