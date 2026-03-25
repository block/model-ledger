import pytest

sklearn = pytest.importorskip("sklearn")

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from model_ledger.introspect.sklearn import SklearnIntrospector


@pytest.fixture
def introspector():
    return SklearnIntrospector()


@pytest.fixture
def fitted_lr():
    X = np.array([[1, 2], [3, 4], [5, 6], [7, 8]])
    y = np.array([0, 1, 0, 1])
    model = LogisticRegression(C=0.5, max_iter=200)
    model.fit(X, y)
    return model


@pytest.fixture
def fitted_pipeline():
    X = np.array([[1, 2], [3, 4], [5, 6], [7, 8]])
    y = np.array([0, 1, 0, 1])
    pipe = Pipeline([("scaler", StandardScaler()), ("lr", LogisticRegression())])
    pipe.fit(X, y)
    return pipe


def test_can_handle_sklearn(introspector, fitted_lr):
    assert introspector.can_handle(fitted_lr) is True


def test_cannot_handle_non_sklearn(introspector):
    assert introspector.can_handle({"not": "sklearn"}) is False


def test_introspect_logistic_regression(introspector, fitted_lr):
    result = introspector.introspect(fitted_lr)
    assert result.introspector == "sklearn"
    assert result.framework == "scikit-learn"
    assert result.algorithm == "LogisticRegression"
    assert result.hyperparameters["C"] == 0.5
    assert result.hyperparameters["max_iter"] == 200


def test_introspect_with_feature_names(introspector):
    import pandas as pd

    X = pd.DataFrame({"age": [1, 2, 3, 4], "income": [10, 20, 30, 40]})
    y = [0, 1, 0, 1]
    model = LogisticRegression()
    model.fit(X, y)
    result = introspector.introspect(model)
    feature_names = [f.name for f in result.features]
    assert "age" in feature_names
    assert "income" in feature_names


def test_introspect_pipeline(introspector, fitted_pipeline):
    result = introspector.introspect(fitted_pipeline)
    assert result.algorithm == "LogisticRegression"
    component_types = [c.node_type for c in result.components]
    assert "preprocessor" in component_types
    assert "algorithm" in component_types
