"""Tests for EU AI Act validation profile."""

from model_ledger.core.enums import RiskTier
from model_ledger.core.models import (
    Evidence,
    GovernanceDoc,
    Model,
    ModelRiskRating,
    ModelVersion,
    Stakeholder,
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


class TestEUAIActProfile:
    def test_minimal_model_fails(self):
        model = _make_model()
        version = _make_version()
        result = validate(model, version, profile="eu_ai_act")
        assert not result.passed
        rule_ids = [v.rule_id for v in result.violations]
        assert "eu_risk_assessment" in rule_ids
        assert "eu_data_governance" in rule_ids
        assert "eu_transparency_docs" in rule_ids

    def test_complete_model_passes(self):
        model = _make_model(
            description="XGBoost classifier for transaction monitoring fraud detection",
            risk_rating=ModelRiskRating(
                model_exposure="high",
                output_reliance="high",
                model_complexity="medium",
                input_uncertainty="medium",
            ),
            affected_populations=["consumers", "merchants"],
            assumptions_and_limitations=[
                "Performance degrades for new merchant categories",
                "Requires minimum 30 days of transaction history",
            ],
            operating_boundaries="US and CA markets, fiat currency transactions only",
            stakeholders=[
                Stakeholder(role="model_owner", name="alice"),
                Stakeholder(role="compliance_officer", name="eve"),
            ],
        )
        version = _make_version(
            training_data_description="12 months of transaction data, 500K labeled samples, "
            "balanced by fraud/non-fraud, sourced from production pipeline",
            documents=[
                GovernanceDoc(doc_type="system_design", title="TM ARR System Design"),
                GovernanceDoc(doc_type="model_spec", title="TM ARR Model Specification"),
            ],
            evidence=[
                Evidence(evidence_type="performance_report", title="Q4 Performance Report"),
            ],
        )
        result = validate(model, version, profile="eu_ai_act")
        assert result.passed, f"Violations: {[v.rule_id for v in result.violations]}"

    def test_intended_purpose_too_short(self):
        model = _make_model(intended_purpose="Detect fraud")
        version = _make_version()
        result = validate(model, version, profile="eu_ai_act")
        rule_ids = [v.rule_id for v in result.violations]
        assert "eu_intended_purpose" in rule_ids

    def test_intended_purpose_adequate(self):
        model = _make_model(
            intended_purpose="Machine learning model to detect fraudulent transaction patterns "
            "in real-time payment processing for US merchants",
        )
        version = _make_version()
        result = validate(model, version, profile="eu_ai_act")
        rule_ids = [v.rule_id for v in result.violations]
        assert "eu_intended_purpose" not in rule_ids

    def test_missing_risk_rating_is_error(self):
        model = _make_model(risk_rating=None)
        version = _make_version()
        result = validate(model, version, profile="eu_ai_act")
        errors = [v for v in result.violations if v.rule_id == "eu_risk_assessment"]
        assert len(errors) == 1
        assert errors[0].severity == "error"

    def test_affected_populations_severity_by_tier(self):
        # High tier → error
        model_high = _make_model(tier=RiskTier.HIGH, affected_populations=[])
        result_high = validate(model_high, _make_version(), profile="eu_ai_act")
        pop_violations = [
            v for v in result_high.violations if v.rule_id == "eu_affected_populations"
        ]
        assert pop_violations[0].severity == "error"

        # Low tier → warning
        model_low = _make_model(tier=RiskTier.LOW, affected_populations=[])
        result_low = validate(model_low, _make_version(), profile="eu_ai_act")
        pop_violations = [
            v for v in result_low.violations if v.rule_id == "eu_affected_populations"
        ]
        assert pop_violations[0].severity == "warning"

    def test_data_governance_requires_training_data(self):
        model = _make_model()
        version = _make_version(training_data_description=None)
        result = validate(model, version, profile="eu_ai_act")
        rule_ids = [v.rule_id for v in result.violations]
        assert "eu_data_governance" in rule_ids

    def test_transparency_requires_documents(self):
        model = _make_model()
        version = _make_version(documents=[])
        result = validate(model, version, profile="eu_ai_act")
        rule_ids = [v.rule_id for v in result.violations]
        assert "eu_transparency_docs" in rule_ids

    def test_transparency_description_warning(self):
        model = _make_model(description=None)
        version = _make_version()
        result = validate(model, version, profile="eu_ai_act")
        desc_violations = [
            v for v in result.violations if v.rule_id == "eu_transparency_description"
        ]
        assert len(desc_violations) == 1
        assert desc_violations[0].severity == "warning"

    def test_human_oversight_stakeholders(self):
        model = _make_model(stakeholders=[])
        version = _make_version()
        result = validate(model, version, profile="eu_ai_act")
        rule_ids = [v.rule_id for v in result.violations]
        assert "eu_human_oversight" in rule_ids

    def test_limitations_documented(self):
        model = _make_model(assumptions_and_limitations=[])
        version = _make_version()
        result = validate(model, version, profile="eu_ai_act")
        rule_ids = [v.rule_id for v in result.violations]
        assert "eu_limitations" in rule_ids

    def test_operating_boundaries(self):
        model = _make_model(operating_boundaries=None)
        version = _make_version()
        result = validate(model, version, profile="eu_ai_act")
        rule_ids = [v.rule_id for v in result.violations]
        assert "eu_operating_boundaries" in rule_ids

    def test_profile_name(self):
        model = _make_model()
        version = _make_version()
        result = validate(model, version, profile="eu_ai_act")
        assert result.profile == "eu_ai_act"
