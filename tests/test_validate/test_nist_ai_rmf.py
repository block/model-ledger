"""Tests for NIST AI RMF validation profile."""

from datetime import date

from model_ledger.core.enums import RiskTier
from model_ledger.core.models import (
    Evidence,
    GovernanceDoc,
    Model,
    ModelRiskRating,
    ModelVersion,
)
from model_ledger.validate.engine import validate


def _make_model(**kwargs):
    defaults = dict(
        name="test_model",
        owner="alice",
        tier=RiskTier.HIGH,
        intended_purpose="Detect fraud in financial transactions",
    )
    defaults.update(kwargs)
    return Model(**defaults)


def _make_version(**kwargs):
    defaults = dict(version="1.0.0")
    defaults.update(kwargs)
    return ModelVersion(**defaults)


class TestNISTAIRMFProfile:
    def test_minimal_model_fails(self):
        model = _make_model()
        version = _make_version()
        result = validate(model, version, profile="nist_ai_rmf")
        assert not result.passed
        rule_ids = [v.rule_id for v in result.violations]
        assert "nist_govern_developers" in rule_ids
        assert "nist_govern_documentation" in rule_ids

    def test_complete_model_passes(self):
        model = _make_model(
            developers=["bob"],
            restrictions_on_use=["Not for credit decisioning"],
            risk_rating=ModelRiskRating(
                model_exposure="high",
                output_reliance="high",
                model_complexity="medium",
                input_uncertainty="medium",
            ),
            potential_harms=["False positives may freeze legitimate accounts"],
            affected_populations=["consumers", "merchants"],
        )
        version = _make_version(
            documents=[
                GovernanceDoc(doc_type="system_design", title="System Design"),
                GovernanceDoc(doc_type="incident_response", title="Incident Runbook"),
                GovernanceDoc(doc_type="fair_lending", title="Fairness Assessment"),
            ],
            evidence=[
                Evidence(evidence_type="performance_report", title="Performance Report"),
                Evidence(evidence_type="bias_assessment", title="Bias Report"),
            ],
            monitoring_frequency="monthly",
            monitoring_status="active",
            next_validation_due=date(2027, 1, 1),
        )
        result = validate(model, version, profile="nist_ai_rmf")
        assert result.passed, f"Violations: {[v.rule_id for v in result.violations]}"

    def test_govern_accountability(self):
        model = _make_model(owner="", developers=[])
        result = validate(model, _make_version(), profile="nist_ai_rmf")
        rule_ids = [v.rule_id for v in result.violations]
        assert "nist_govern_accountability" in rule_ids
        assert "nist_govern_developers" in rule_ids

    def test_map_restrictions_warning(self):
        model = _make_model(restrictions_on_use=[])
        result = validate(model, _make_version(), profile="nist_ai_rmf")
        restrictions = [v for v in result.violations if v.rule_id == "nist_map_restrictions"]
        assert len(restrictions) == 1
        assert restrictions[0].severity == "warning"

    def test_map_risk_identification_high_tier(self):
        model = _make_model(tier=RiskTier.HIGH, risk_rating=None)
        result = validate(model, _make_version(), profile="nist_ai_rmf")
        rule_ids = [v.rule_id for v in result.violations]
        assert "nist_map_risk_id" in rule_ids

    def test_map_risk_identification_low_tier_no_error(self):
        model = _make_model(tier=RiskTier.LOW, risk_rating=None)
        result = validate(model, _make_version(), profile="nist_ai_rmf")
        risk_errors = [v for v in result.violations if v.rule_id == "nist_map_risk_id"]
        assert len(risk_errors) == 0

    def test_measure_performance_with_evidence(self):
        model = _make_model(developers=["bob"])
        version = _make_version(
            documents=[GovernanceDoc(doc_type="spec", title="Spec")],
            evidence=[Evidence(evidence_type="performance_report", title="Perf")],
        )
        result = validate(model, version, profile="nist_ai_rmf")
        rule_ids = [v.rule_id for v in result.violations]
        assert "nist_measure_performance" not in rule_ids

    def test_measure_bias_high_tier(self):
        model = _make_model(tier=RiskTier.HIGH, developers=["bob"])
        version = _make_version(
            documents=[GovernanceDoc(doc_type="spec", title="Spec")],
            evidence=[Evidence(evidence_type="performance_report", title="Perf")],
        )
        result = validate(model, version, profile="nist_ai_rmf")
        rule_ids = [v.rule_id for v in result.violations]
        assert "nist_measure_bias" in rule_ids

    def test_manage_monitoring(self):
        model = _make_model(developers=["bob"])
        version = _make_version(monitoring_frequency=None, monitoring_status=None)
        result = validate(model, version, profile="nist_ai_rmf")
        rule_ids = [v.rule_id for v in result.violations]
        assert "nist_manage_monitoring" in rule_ids

    def test_manage_incident_response_high_tier(self):
        model = _make_model(tier=RiskTier.HIGH, developers=["bob"])
        version = _make_version(
            documents=[GovernanceDoc(doc_type="spec", title="Spec")],
        )
        result = validate(model, version, profile="nist_ai_rmf")
        rule_ids = [v.rule_id for v in result.violations]
        assert "nist_manage_incident_response" in rule_ids

    def test_profile_name(self):
        model = _make_model()
        version = _make_version()
        result = validate(model, version, profile="nist_ai_rmf")
        assert result.profile == "nist_ai_rmf"
