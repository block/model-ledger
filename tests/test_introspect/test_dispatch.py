# tests/test_introspect/test_dispatch.py
"""Registry dispatch: framework-specific introspectors win over generic sklearn.

Entry points load ``sorted(key=name)`` (lightgbm < sklearn < xgboost) and
``find()`` returns the first ``can_handle`` match. XGBoost/LightGBM
sklearn-API wrappers are ``isinstance`` of ``sklearn.BaseEstimator``, so
without an explicit rejection in ``SklearnIntrospector.can_handle`` the
generic introspector shadows the xgboost one (and lightgbm only escaped by
alphabetical luck).

Two layers of coverage:

- ``TestDispatchWithStubs`` installs minimal stub ``sklearn``/``xgboost``/
  ``lightgbm`` modules, so the dispatch logic EXECUTES in every environment
  (CI installs no ML libraries — importorskip-only tests would never run).
- ``TestDispatchWithRealLibraries`` drives the same assertions against the
  real libraries where they are installed.
"""

from __future__ import annotations

import sys
import types

import pytest

from model_ledger.introspect.registry import get_registry, reset_registry


@pytest.fixture(autouse=True)
def fresh_registry():
    reset_registry()
    yield
    reset_registry()


# ---------------------------------------------------------------------------
# Stub-module layer: executes everywhere, no ML dependencies required.
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_ml_libs(monkeypatch):
    """Minimal sklearn/xgboost/lightgbm stubs with the real inheritance shape:
    wrapper-library estimators subclass sklearn's BaseEstimator."""
    sklearn = types.ModuleType("sklearn")
    sklearn_base = types.ModuleType("sklearn.base")

    class BaseEstimator:
        pass

    sklearn_base.BaseEstimator = BaseEstimator
    sklearn.base = sklearn_base

    xgboost = types.ModuleType("xgboost")

    class XGBModel(BaseEstimator):
        pass

    class XGBoosterStub:
        pass

    xgboost.XGBModel = XGBModel
    xgboost.Booster = XGBoosterStub

    lightgbm = types.ModuleType("lightgbm")

    class LGBMModel(BaseEstimator):
        pass

    class LGBBoosterStub:
        pass

    lightgbm.LGBMModel = LGBMModel
    lightgbm.Booster = LGBBoosterStub

    for name, mod in {
        "sklearn": sklearn,
        "sklearn.base": sklearn_base,
        "xgboost": xgboost,
        "lightgbm": lightgbm,
    }.items():
        monkeypatch.setitem(sys.modules, name, mod)

    return types.SimpleNamespace(sklearn=sklearn, xgboost=xgboost, lightgbm=lightgbm)


def _make_estimator(base, class_name, module):
    """An estimator instance whose class lives in ``module`` (like the real
    xgboost.sklearn.XGBClassifier / sklearn.linear_model.LogisticRegression)."""
    cls = type(class_name, (base,), {"__module__": module})
    return cls()


class TestDispatchWithStubs:
    def test_xgboost_wrapper_dispatches_to_xgboost(self, stub_ml_libs):
        model = _make_estimator(stub_ml_libs.xgboost.XGBModel, "XGBClassifier", "xgboost.sklearn")
        assert get_registry().find(model).name == "xgboost"

    def test_lightgbm_wrapper_dispatches_to_lightgbm(self, stub_ml_libs):
        model = _make_estimator(
            stub_ml_libs.lightgbm.LGBMModel, "LGBMClassifier", "lightgbm.sklearn"
        )
        assert get_registry().find(model).name == "lightgbm"

    def test_plain_estimator_dispatches_to_sklearn(self, stub_ml_libs):
        model = _make_estimator(
            stub_ml_libs.sklearn.base.BaseEstimator,
            "LogisticRegression",
            "sklearn.linear_model",
        )
        assert get_registry().find(model).name == "sklearn"

    def test_sklearn_can_handle_rejects_wrapper_modules_regardless_of_order(self, stub_ml_libs):
        """Order-independence: even if a new introspector name sorted the
        sklearn introspector first, its can_handle must refuse
        wrapper-library objects."""
        from model_ledger.introspect.sklearn import SklearnIntrospector

        model = _make_estimator(stub_ml_libs.xgboost.XGBModel, "XGBClassifier", "xgboost.sklearn")
        assert SklearnIntrospector().can_handle(model) is False

    def test_none_module_is_safe_and_goes_to_sklearn(self, stub_ml_libs):
        """A BaseEstimator subclass with ``__module__ = None`` must not crash
        the module-root check."""
        model = _make_estimator(stub_ml_libs.sklearn.base.BaseEstimator, "Weird", "x")
        type(model).__module__ = None
        assert get_registry().find(model).name == "sklearn"


# ---------------------------------------------------------------------------
# Real-library layer: runs where the ML extras are installed.
# ---------------------------------------------------------------------------


def _training_data():
    np = pytest.importorskip("numpy")
    X = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]])
    y = np.array([0, 1, 0, 1])
    return X, y


class TestDispatchWithRealLibraries:
    def test_xgboost_sklearn_api_dispatches_to_xgboost(self):
        xgb = pytest.importorskip("xgboost")
        pytest.importorskip("sklearn")

        X, y = _training_data()
        model = xgb.XGBClassifier(n_estimators=2, max_depth=2).fit(X, y)

        intro = get_registry().find(model)
        assert intro.name == "xgboost"

        result = intro.introspect(model)
        assert result.introspector == "xgboost"
        assert result.framework == "xgboost"

    def test_lightgbm_sklearn_api_dispatches_to_lightgbm(self):
        lgb = pytest.importorskip("lightgbm")
        pytest.importorskip("sklearn")

        X, y = _training_data()
        model = lgb.LGBMClassifier(n_estimators=2, min_child_samples=1).fit(X, y)

        intro = get_registry().find(model)
        assert intro.name == "lightgbm"

    def test_plain_sklearn_estimator_still_dispatches_to_sklearn(self):
        pytest.importorskip("sklearn")
        from sklearn.linear_model import LogisticRegression

        X, y = _training_data()
        model = LogisticRegression().fit(X, y)

        intro = get_registry().find(model)
        assert intro.name == "sklearn"

    def test_sklearn_can_handle_rejects_wrapper_modules_regardless_of_order(self):
        """Order-independence: even if a new introspector name sorted the sklearn
        introspector first, its can_handle must refuse wrapper-library objects."""
        pytest.importorskip("sklearn")
        xgb = pytest.importorskip("xgboost")

        from model_ledger.introspect.sklearn import SklearnIntrospector

        X, y = _training_data()
        model = xgb.XGBClassifier(n_estimators=2, max_depth=2).fit(X, y)

        assert SklearnIntrospector().can_handle(model) is False
