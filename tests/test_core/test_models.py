"""Tests for core Pydantic data models."""

import pytest
from datetime import datetime, date

from model_ledger.core.models import (
    Model,
    ModelVersion,
    ComponentNode,
    Stakeholder,
    GovernanceDoc,
    Reference,
    Evidence,
    Finding,
    Exception_,
    Overlay,
    ModelRiskRating,
    AuditEvent,
    ModelArtifact,
    DeploymentRecord,
)
from model_ledger.core.enums import ModelType, RiskTier, ModelStatus, VersionStatus


def test_create_minimal_model():
    model = Model(
        name="test_model",
        owner="alice",
        tier=RiskTier.HIGH,
        intended_purpose="Detect fraud",
    )
    assert model.name == "test_model"
    assert model.model_id
    assert model.status == ModelStatus.DEVELOPMENT
    assert model.model_type == ModelType.ML_MODEL
    assert model.versions == []


def test_create_model_with_all_fields():
    model = Model(
        name="fraud_detection",
        owner="team_lead",
        developers=["dev_a", "dev_b"],
        validator="validator_1",
        tier=RiskTier.HIGH,
        business_unit="Lending",
        intended_purpose="Score transaction risk",
        jurisdictions=["US", "CA", "AU"],
    )
    assert model.developers == ["dev_a", "dev_b"]
    assert model.jurisdictions == ["US", "CA", "AU"]


def test_model_version_default_tree():
    version = ModelVersion(version="1.0.0")
    assert version.status == VersionStatus.DRAFT
    assert version.tree is not None
    assert version.tree.name == "root"
    assert len(version.tree.children) == 3
    assert version.tree.children[0].name == "Inputs"
    assert version.tree.children[1].name == "Processing"
    assert version.tree.children[2].name == "Outputs"


def test_model_risk_rating_high():
    mrr = ModelRiskRating(
        model_exposure="high",
        output_reliance="medium",
        model_complexity="medium",
        input_uncertainty="high",
    )
    assert mrr.impact == "high"
    assert mrr.likelihood == "high"
    assert mrr.overall_rating == "high"
    assert mrr.score >= 10


def test_model_risk_rating_low():
    mrr = ModelRiskRating(
        model_exposure="low",
        output_reliance="low",
        model_complexity="low",
        input_uncertainty="low",
    )
    assert mrr.overall_rating == "low"
    assert mrr.score == 4


def test_audit_event():
    event = AuditEvent(
        actor="vignesh",
        action="published_version",
        model_name="fraud_detection",
        version="1.0.0",
        details={"profile": "sr_11_7"},
    )
    assert event.event_id
    assert event.timestamp
    assert event.actor == "vignesh"


def test_model_artifact():
    artifact = ModelArtifact(
        artifact_type="pickle",
        uri="gs://ml-models/fraud-detection/model.pkl",
        checksum="sha256:abc123",
    )
    assert artifact.uri.startswith("gs://")


def test_deployment_record():
    record = DeploymentRecord(
        environment="prod",
        endpoint="scoring-service/fraud-detection-v1",
        deployment_strategy="full",
    )
    assert record.environment == "prod"


def test_component_node_tree():
    root = ComponentNode(name="root", node_type="root")
    inputs = ComponentNode(name="Inputs", node_type="category")
    root.children.append(inputs)
    feature = ComponentNode(
        name="customer_risk_score",
        node_type="Feature",
        metadata={"source": "feature_store"},
    )
    inputs.children.append(feature)
    assert root.children[0].children[0].name == "customer_risk_score"


def test_model_serialization_roundtrip():
    model = Model(
        name="test",
        owner="alice",
        tier=RiskTier.LOW,
        intended_purpose="Testing",
    )
    json_str = model.model_dump_json()
    loaded = Model.model_validate_json(json_str)
    assert loaded.name == model.name
    assert loaded.model_id == model.model_id


def test_version_with_artifacts():
    version = ModelVersion(
        version="1.0.0",
        artifacts=[ModelArtifact(artifact_type="pickle", uri="gs://bucket/model.pkl")],
        deployments=[DeploymentRecord(environment="prod", deployment_strategy="full")],
    )
    assert len(version.artifacts) == 1
    assert len(version.deployments) == 1


def test_finding():
    finding = Finding(
        finding_id="F-001",
        severity="high",
        title="Missing validation for input drift",
        status="open",
        source="validation",
    )
    assert finding.severity == "high"
    assert finding.status == "open"


def test_governance_doc():
    doc = GovernanceDoc(
        doc_type="system_design",
        title="CSD v2",
        url="https://docs.google.com/document/d/abc",
    )
    assert doc.doc_type == "system_design"


def test_reference():
    ref = Reference(
        ref_type="jira",
        identifier="CHG-1234",
        metadata={"project": "MODEL_CHANGES"},
    )
    assert ref.ref_type == "jira"


def test_exception():
    exc = Exception_(
        exception_id="EX-001",
        description="Deferred annual validation",
        justification="Model retiring in Q2",
        approved_by="manager",
        approved_date=date(2026, 1, 15),
        expiration_date=date(2026, 6, 30),
        status="active",
    )
    assert exc.status == "active"


def test_overlay():
    overlay = Overlay(
        description="Manual score adjustment for new market",
        justification="Model not trained on this segment",
        applied_by="analyst",
        applied_date=date(2026, 2, 1),
    )
    assert overlay.applied_by == "analyst"
