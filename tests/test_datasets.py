"""Tests for built-in sample datasets."""

import pytest

from model_ledger.datasets import load_sample_inventory, make_rule_engine


def test_load_sample_inventory():
    inv = load_sample_inventory()
    models = inv.list_models()
    assert len(models) == 3
    names = {m.name for m in models}
    assert "fraud-detector-v2" in names
    assert "credit-risk-v1" in names
    assert "velocity-monitoring-v1" in names


def test_sample_fraud_detector_has_version():
    inv = load_sample_inventory()
    versions = inv._backend.list_versions("fraud-detector-v2")
    assert len(versions) >= 1
    v = versions[0]
    assert v.run_frequency == "real_time"
    assert len(v.documents) >= 2


def test_sample_credit_model_has_pipeline():
    inv = load_sample_inventory()
    versions = inv._backend.list_versions("credit-risk-v1")
    v = versions[0]
    tree_names = [c.name for c in v.tree.children]
    assert "Inputs" in tree_names
    assert "Processing" in tree_names


def test_make_rule_engine():
    config = make_rule_engine()
    assert config["algorithm"] == "heuristic_rule"
    assert len(config["thresholds"]) == 3
    assert config["execution_schedule"] == "daily"


xgboost = pytest.importorskip("xgboost")


def test_make_fraud_detector():
    from model_ledger.datasets import make_fraud_detector

    data = make_fraud_detector()
    assert hasattr(data["model"], "predict")
    assert len(data["feature_names"]) == 16


def test_introspect_fraud_detector():
    from model_ledger.datasets import make_fraud_detector
    from model_ledger.introspect.registry import get_registry

    data = make_fraud_detector()
    intro = get_registry().find(data["model"])
    result = intro.introspect(data["model"])
    assert result.algorithm == "XGBClassifier"
    assert len(result.features) == 16


sklearn = pytest.importorskip("sklearn")


def test_make_credit_model():
    from model_ledger.datasets import make_credit_model

    data = make_credit_model()
    assert hasattr(data["model"], "predict")
    assert len(data["feature_names"]) == 8


def test_introspect_credit_pipeline():
    from model_ledger.datasets import make_credit_model
    from model_ledger.introspect.registry import get_registry

    data = make_credit_model()
    intro = get_registry().find(data["model"])
    result = intro.introspect(data["model"])
    assert result.algorithm == "LogisticRegression"
    assert len(result.components) >= 2  # scaler + classifier
