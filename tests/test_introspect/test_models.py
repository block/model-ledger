from model_ledger.introspect.models import (
    ComponentInfo,
    DataSourceInfo,
    FeatureInfo,
    IntrospectionResult,
    ThresholdInfo,
)


def test_feature_info_minimal():
    f = FeatureInfo(name="age")
    assert f.name == "age"
    assert f.dtype is None
    assert f.metadata == {}


def test_feature_info_full():
    f = FeatureInfo(
        name="amount", dtype="float64", source="data_warehouse", description="Total amount"
    )
    assert f.source == "data_warehouse"


def test_data_source_info():
    ds = DataSourceInfo(
        name="analytics.public.transaction_metrics",
        source_type="sql_table",
        fields=["amount", "count"],
        filters={"lookback": 30},
    )
    assert ds.source_type == "sql_table"
    assert ds.filters["lookback"] == 30


def test_threshold_info():
    t = ThresholdInfo(name="model_score", value=0.83, operator=">=", segment="high_risk")
    assert t.value == 0.83
    assert t.segment == "high_risk"


def test_threshold_info_string_value():
    t = ThresholdInfo(name="category", value="blocked")
    assert t.value == "blocked"


def test_component_info():
    c = ComponentInfo(path="Inputs/features", node_type="feature_set")
    assert c.path == "Inputs/features"


def test_introspection_result_minimal():
    r = IntrospectionResult(introspector="test")
    assert r.introspector == "test"
    assert r.features == []
    assert r.thresholds == []
    assert r.metadata == {}


def test_introspection_result_ml_model():
    r = IntrospectionResult(
        introspector="sklearn",
        framework="scikit-learn",
        algorithm="LogisticRegression",
        hyperparameters={"C": 1.0, "max_iter": 100},
        features=[FeatureInfo(name="age"), FeatureInfo(name="income")],
        metrics={"accuracy": 0.95, "precision": 0.92},
    )
    assert r.algorithm == "LogisticRegression"
    assert len(r.features) == 2
    assert r.metrics["accuracy"] == 0.95


def test_introspection_result_heuristic():
    r = IntrospectionResult(
        introspector="custom_rules",
        framework="custom_rules",
        algorithm="heuristic_rule",
        data_sources=[DataSourceInfo(name="metrics_table", source_type="sql_table")],
        thresholds=[ThresholdInfo(name="total_in_amount", value=2000, operator=">=")],
        execution_schedule="twice_monthly",
        lookback_window="30 days",
    )
    assert r.execution_schedule == "twice_monthly"
    assert len(r.data_sources) == 1


def test_introspection_result_serialization():
    r = IntrospectionResult(
        introspector="test",
        algorithm="XGBClassifier",
        features=[FeatureInfo(name="f1", dtype="float64")],
    )
    data = r.model_dump()
    restored = IntrospectionResult.model_validate(data)
    assert restored.algorithm == "XGBClassifier"
    assert restored.features[0].name == "f1"
