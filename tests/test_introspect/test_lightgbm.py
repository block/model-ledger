import pytest

lgb = pytest.importorskip("lightgbm")

import numpy as np

from model_ledger.introspect.lightgbm import LightGBMIntrospector


@pytest.fixture
def introspector():
    return LightGBMIntrospector()


@pytest.fixture
def fitted_lgb():
    import lightgbm as lgb

    X = np.array([[1, 2], [3, 4], [5, 6], [7, 8]])
    y = np.array([0, 1, 0, 1])
    model = lgb.LGBMClassifier(n_estimators=10, max_depth=3, verbosity=-1)
    model.fit(X, y)
    return model


def test_can_handle(introspector, fitted_lgb):
    assert introspector.can_handle(fitted_lgb) is True


def test_cannot_handle_non_lgb(introspector):
    assert introspector.can_handle("not lgb") is False


def test_introspect(introspector, fitted_lgb):
    result = introspector.introspect(fitted_lgb)
    assert result.introspector == "lightgbm"
    assert result.framework == "lightgbm"
    assert result.algorithm == "LGBMClassifier"
    assert "n_estimators" in result.hyperparameters


def test_introspect_feature_names(introspector):
    import lightgbm as lgb
    import pandas as pd

    X = pd.DataFrame({"feat_a": [1, 2, 3, 4], "feat_b": [5, 6, 7, 8]})
    y = [0, 1, 0, 1]
    model = lgb.LGBMClassifier(n_estimators=5, verbosity=-1)
    model.fit(X, y)
    result = introspector.introspect(model)
    names = [f.name for f in result.features]
    assert "feat_a" in names
    assert "feat_b" in names
