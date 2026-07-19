# tests/test_introspect/test_dispatch.py
"""Registry dispatch: framework-specific introspectors win over generic sklearn.

Entry points load ``sorted(key=name)`` (lightgbm < sklearn < xgboost) and
``find()`` returns the first ``can_handle`` match. XGBoost/LightGBM
sklearn-API wrappers are ``isinstance`` of ``sklearn.BaseEstimator``, so
without an explicit rejection in ``SklearnIntrospector.can_handle`` the
generic introspector shadows the xgboost one (and lightgbm only escaped by
alphabetical luck).
"""

from __future__ import annotations

import pytest

from model_ledger.introspect.registry import get_registry, reset_registry

np = pytest.importorskip("numpy")


@pytest.fixture(autouse=True)
def fresh_registry():
    reset_registry()
    yield
    reset_registry()


def _training_data():
    X = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]])
    y = np.array([0, 1, 0, 1])
    return X, y


def test_xgboost_sklearn_api_dispatches_to_xgboost():
    xgb = pytest.importorskip("xgboost")
    pytest.importorskip("sklearn")

    X, y = _training_data()
    model = xgb.XGBClassifier(n_estimators=2, max_depth=2).fit(X, y)

    intro = get_registry().find(model)
    assert intro.name == "xgboost"

    result = intro.introspect(model)
    assert result.introspector == "xgboost"
    assert result.framework == "xgboost"


def test_lightgbm_sklearn_api_dispatches_to_lightgbm():
    lgb = pytest.importorskip("lightgbm")
    pytest.importorskip("sklearn")

    X, y = _training_data()
    model = lgb.LGBMClassifier(n_estimators=2, min_child_samples=1).fit(X, y)

    intro = get_registry().find(model)
    assert intro.name == "lightgbm"


def test_plain_sklearn_estimator_still_dispatches_to_sklearn():
    sklearn = pytest.importorskip("sklearn")  # noqa: F841
    from sklearn.linear_model import LogisticRegression

    X, y = _training_data()
    model = LogisticRegression().fit(X, y)

    intro = get_registry().find(model)
    assert intro.name == "sklearn"


def test_sklearn_can_handle_rejects_wrapper_modules_regardless_of_order():
    """Order-independence: even if a new introspector name sorted the sklearn
    introspector first, its can_handle must refuse wrapper-library objects."""
    pytest.importorskip("sklearn")
    xgb = pytest.importorskip("xgboost")

    from model_ledger.introspect.sklearn import SklearnIntrospector

    X, y = _training_data()
    model = xgb.XGBClassifier(n_estimators=2, max_depth=2).fit(X, y)

    assert SklearnIntrospector().can_handle(model) is False
