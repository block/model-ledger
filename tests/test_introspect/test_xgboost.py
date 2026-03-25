import pytest

xgb = pytest.importorskip("xgboost")

import numpy as np

from model_ledger.introspect.xgboost import XGBoostIntrospector


@pytest.fixture
def introspector():
    return XGBoostIntrospector()


@pytest.fixture
def fitted_xgb():
    import xgboost as xgb

    X = np.array([[1, 2], [3, 4], [5, 6], [7, 8]])
    y = np.array([0, 1, 0, 1])
    model = xgb.XGBClassifier(n_estimators=10, max_depth=3, eval_metric="logloss")
    model.fit(X, y)
    return model


def test_can_handle(introspector, fitted_xgb):
    assert introspector.can_handle(fitted_xgb) is True


def test_cannot_handle_non_xgb(introspector):
    assert introspector.can_handle("not xgb") is False


def test_introspect(introspector, fitted_xgb):
    result = introspector.introspect(fitted_xgb)
    assert result.introspector == "xgboost"
    assert result.framework == "xgboost"
    assert result.algorithm == "XGBClassifier"
    assert "n_estimators" in result.hyperparameters
    assert "max_depth" in result.hyperparameters
