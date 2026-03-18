"""Tests for core enums with case-insensitive coercion."""

from model_ledger.core.enums import ModelType, RiskTier, ModelStatus, VersionStatus


def test_model_type_values():
    assert ModelType.ML_MODEL == "ml_model"
    assert ModelType.HEURISTIC == "heuristic"
    assert ModelType.VENDOR == "vendor"
    assert ModelType.LLM == "llm"
    assert ModelType.SPREADSHEET == "spreadsheet"


def test_risk_tier_values():
    assert RiskTier.HIGH == "high"
    assert RiskTier.MEDIUM == "medium"
    assert RiskTier.LOW == "low"


def test_risk_tier_case_insensitive():
    assert RiskTier("high") == RiskTier.HIGH
    assert RiskTier("High") == RiskTier.HIGH
    assert RiskTier("HIGH") == RiskTier.HIGH


def test_model_status_lifecycle():
    statuses = [s.value for s in ModelStatus]
    assert statuses == ["development", "review", "active", "deprecated", "retired"]


def test_version_status_values():
    assert VersionStatus.DRAFT == "draft"
    assert VersionStatus.PUBLISHED == "published"
    assert VersionStatus.DEPRECATED == "deprecated"


def test_model_type_case_insensitive():
    assert ModelType("ML_MODEL") == ModelType.ML_MODEL
    assert ModelType("ml_model") == ModelType.ML_MODEL
    assert ModelType("Ml_Model") == ModelType.ML_MODEL
