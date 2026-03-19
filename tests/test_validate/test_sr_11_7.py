"""Tests for SR 11-7 validation engine."""

import pytest
from datetime import date

from model_ledger.core.enums import RiskTier, VersionStatus
from model_ledger.core.models import Model, ModelVersion, GovernanceDoc
from model_ledger.validate.engine import validate, ValidationResult


def _make_model(**kwargs):
    defaults = dict(
        name="test_model",
        owner="alice",
        tier=RiskTier.HIGH,
        intended_purpose="Detect fraud",
    )
    defaults.update(kwargs)
    return Model(**defaults)


def _make_version(**kwargs):
    defaults = dict(version="1.0.0")
    defaults.update(kwargs)
    return ModelVersion(**defaults)


class TestSR117Profile:
    def test_minimal_model_fails(self):
        model = _make_model()
        version = _make_version()
        result = validate(model, version, profile="sr_11_7")
        assert not result.passed
        assert len(result.errors) > 0

    def test_complete_model_passes(self):
        model = _make_model(
            developers=["bob"],
            validator="carol",
        )
        version = _make_version(
            next_validation_due=date(2027, 1, 1),
            documents=[GovernanceDoc(doc_type="system_design", title="CSD v1")],
        )
        result = validate(model, version, profile="sr_11_7")
        assert result.passed

    def test_missing_validator_is_error(self):
        model = _make_model(developers=["bob"])
        version = _make_version(
            next_validation_due=date(2027, 1, 1),
            documents=[GovernanceDoc(doc_type="system_design", title="CSD v1")],
        )
        result = validate(model, version, profile="sr_11_7")
        errors = [v for v in result.violations if v.severity == "error"]
        rule_ids = [v.rule_id for v in errors]
        assert "has_validator" in rule_ids

    def test_validator_must_not_be_developer(self):
        model = _make_model(
            developers=["alice"],
            validator="alice",  # Same person!
        )
        version = _make_version(
            next_validation_due=date(2027, 1, 1),
            documents=[GovernanceDoc(doc_type="system_design", title="CSD v1")],
        )
        result = validate(model, version, profile="sr_11_7")
        rule_ids = [v.rule_id for v in result.violations if v.severity == "error"]
        assert "validator_independence" in rule_ids

    def test_high_tier_requires_next_validation_due(self):
        model = _make_model(
            tier=RiskTier.HIGH,
            developers=["bob"],
            validator="carol",
        )
        version = _make_version(
            documents=[GovernanceDoc(doc_type="system_design", title="CSD v1")],
            # No next_validation_due!
        )
        result = validate(model, version, profile="sr_11_7")
        rule_ids = [v.rule_id for v in result.violations if v.severity == "error"]
        assert "has_validation_schedule" in rule_ids

    def test_low_tier_validation_due_is_warning(self):
        model = _make_model(
            tier=RiskTier.LOW,
            developers=["bob"],
            validator="carol",
        )
        version = _make_version(
            documents=[GovernanceDoc(doc_type="system_design", title="CSD v1")],
            # No next_validation_due
        )
        result = validate(model, version, profile="sr_11_7")
        # Should be warning, not error, for low tier
        warnings = [v for v in result.violations if v.severity == "warning"]
        warning_ids = [v.rule_id for v in warnings]
        assert "has_validation_schedule" in warning_ids
        # Should still pass (no errors)
        assert result.passed

    def test_missing_documents_is_error(self):
        model = _make_model(developers=["bob"], validator="carol")
        version = _make_version(next_validation_due=date(2027, 1, 1))
        result = validate(model, version, profile="sr_11_7")
        rule_ids = [v.rule_id for v in result.violations if v.severity == "error"]
        assert "has_governance_document" in rule_ids

    def test_missing_developers_is_error(self):
        model = _make_model(validator="carol")
        version = _make_version(
            next_validation_due=date(2027, 1, 1),
            documents=[GovernanceDoc(doc_type="system_design", title="CSD")],
        )
        result = validate(model, version, profile="sr_11_7")
        rule_ids = [v.rule_id for v in result.violations if v.severity == "error"]
        assert "has_developers" in rule_ids

    def test_result_has_model_name(self):
        model = _make_model()
        version = _make_version()
        result = validate(model, version, profile="sr_11_7")
        assert result.model_name == "test_model"

    def test_result_has_profile(self):
        model = _make_model()
        version = _make_version()
        result = validate(model, version, profile="sr_11_7")
        assert result.profile == "sr_11_7"

    def test_result_violations_have_suggestions(self):
        model = _make_model()
        version = _make_version()
        result = validate(model, version, profile="sr_11_7")
        for v in result.violations:
            assert v.suggestion is not None
            assert len(v.suggestion) > 0

    def test_tree_structure_validated(self):
        model = _make_model(developers=["bob"], validator="carol")
        version = _make_version(
            next_validation_due=date(2027, 1, 1),
            documents=[GovernanceDoc(doc_type="system_design", title="CSD")],
        )
        # Default tree has I/P/O — should pass structural check
        result = validate(model, version, profile="sr_11_7")
        structural_errors = [
            v for v in result.violations
            if v.rule_id == "has_ipo_structure" and v.severity == "error"
        ]
        assert len(structural_errors) == 0

    def test_unknown_profile_raises(self):
        model = _make_model()
        version = _make_version()
        with pytest.raises(ValueError, match="Unknown profile"):
            validate(model, version, profile="nonexistent")

    def test_result_str_representation(self):
        model = _make_model(developers=["bob"], validator="carol")
        version = _make_version(
            next_validation_due=date(2027, 1, 1),
            documents=[GovernanceDoc(doc_type="system_design", title="CSD")],
        )
        result = validate(model, version, profile="sr_11_7")
        s = str(result)
        assert "PASS" in s or "FAIL" in s
