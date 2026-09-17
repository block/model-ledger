"""Tests for core enums with case-insensitive coercion."""

from model_ledger.core.enums import ModelStatus, ModelType, RiskTier, VersionStatus


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
    assert statuses == [
        "development",
        "review",
        "active",
        "shadow",
        "disabled",
        "deprecated",
        "retired",
    ]


def test_model_status_paused_states_case_insensitive():
    assert ModelStatus("shadow") == ModelStatus.SHADOW
    assert ModelStatus("SHADOW") == ModelStatus.SHADOW
    assert ModelStatus("Shadow").value == "shadow"
    assert ModelStatus("disabled") == ModelStatus.DISABLED
    assert ModelStatus("DISABLED") == ModelStatus.DISABLED
    assert ModelStatus("Disabled").value == "disabled"


def test_model_status_paused_states_are_not_terminal():
    """Paused states sit between active and the terminal states, so a
    consumer ordering by lifecycle position keeps them ahead of deprecated."""
    order = [s.value for s in ModelStatus]
    assert order.index("active") < order.index("shadow") < order.index("deprecated")
    assert order.index("active") < order.index("disabled") < order.index("deprecated")


def test_version_status_values():
    assert VersionStatus.DRAFT == "draft"
    assert VersionStatus.PUBLISHED == "published"
    assert VersionStatus.DEPRECATED == "deprecated"


def test_model_type_case_insensitive():
    assert ModelType("ML_MODEL") == ModelType.ML_MODEL
    assert ModelType("ml_model") == ModelType.ML_MODEL
    assert ModelType("Ml_Model") == ModelType.ML_MODEL
