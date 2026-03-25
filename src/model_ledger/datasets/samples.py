"""Sample models, versions, and fitted objects for demos and testing.

Provides realistic financial services examples with pre-built component trees,
governance documents, risk ratings, and fitted sklearn/XGBoost models ready
for introspection.
"""

from __future__ import annotations

from typing import Any

from model_ledger import Inventory
from model_ledger.backends.memory import InMemoryBackend


def load_sample_inventory() -> Inventory:
    """Load an inventory pre-populated with 3 sample financial services models.

    Returns an Inventory with:
    - A fraud detection XGBoost model (high tier, fully documented)
    - A credit risk scoring model (medium tier)
    - A transaction monitoring heuristic rule engine (medium tier)

    Example:
        >>> inv = load_sample_inventory()
        >>> for m in inv.list_models():
        ...     print(f"{m.name}: {m.tier.value}")
    """
    inv = Inventory(backend=InMemoryBackend())

    _register_fraud_detector(inv)
    _register_credit_model(inv)
    _register_rule_engine(inv)

    return inv


def make_fraud_detector() -> dict[str, Any]:
    """Create a fitted XGBoost fraud detection model with realistic features.

    Returns a dict with:
    - 'model': fitted XGBClassifier
    - 'feature_names': list of feature names
    - 'metadata': model context info

    Example:
        >>> data = make_fraud_detector()
        >>> from model_ledger import introspect
        >>> result = introspect(data['model'])
        >>> print(result.algorithm)  # 'XGBClassifier'
    """
    try:
        import numpy as np
        import xgboost as xgb
    except ImportError as err:
        raise ImportError(
            "xgboost and numpy are required for make_fraud_detector(). "
            "Install with: pip install model-ledger[introspect-xgboost]"
        ) from err

    feature_names = [
        "txn_amount",
        "txn_count_30d",
        "avg_txn_amount_30d",
        "counterparty_count",
        "cross_border_ratio",
        "velocity_score",
        "roundness_score",
        "time_since_last_txn_hours",
        "account_age_days",
        "prior_sar_count",
        "in_amount_concentration",
        "out_amount_concentration",
        "note_embedding_0",
        "note_embedding_1",
        "note_embedding_2",
        "note_embedding_3",
    ]

    np.random.seed(42)
    n = 500
    X = np.random.randn(n, len(feature_names))
    X[:, 0] = np.abs(X[:, 0]) * 5000  # txn_amount
    X[:, 8] = np.abs(X[:, 8]) * 365  # account_age_days
    y = (X[:, 5] > 0.5).astype(int)  # velocity_score threshold

    import pandas as pd

    X_df = pd.DataFrame(X, columns=feature_names)

    model = xgb.XGBClassifier(
        n_estimators=50,
        max_depth=4,
        learning_rate=0.1,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_df, y)

    return {
        "model": model,
        "feature_names": feature_names,
        "metadata": {
            "name": "fraud-detector-v2",
            "algorithm": "XGBClassifier",
            "training_samples": n,
            "target": "SAR escalation within 90 days",
        },
    }


def make_credit_model() -> dict[str, Any]:
    """Create a fitted sklearn credit risk model with a preprocessing pipeline.

    Returns a dict with:
    - 'model': fitted sklearn Pipeline (StandardScaler -> LogisticRegression)
    - 'feature_names': list of feature names
    - 'metadata': model context info

    Example:
        >>> data = make_credit_model()
        >>> from model_ledger import introspect
        >>> result = introspect(data['model'])
        >>> print(result.algorithm)  # 'LogisticRegression'
    """
    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as err:
        raise ImportError(
            "scikit-learn and numpy are required for make_credit_model(). "
            "Install with: pip install model-ledger[introspect-sklearn]"
        ) from err

    feature_names = [
        "annual_income",
        "debt_to_income_ratio",
        "credit_utilization",
        "num_open_accounts",
        "num_delinquencies",
        "months_since_last_delinq",
        "total_revolving_balance",
        "payment_history_score",
    ]

    np.random.seed(123)
    n = 300
    X = np.random.randn(n, len(feature_names))
    X[:, 0] = np.abs(X[:, 0]) * 80000 + 20000  # income
    y = (X[:, 1] > 0.3).astype(int)  # high DTI = risky

    import pandas as pd

    X_df = pd.DataFrame(X, columns=feature_names)

    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(C=0.5, max_iter=200, random_state=123)),
        ]
    )
    model.fit(X_df, y)

    return {
        "model": model,
        "feature_names": feature_names,
        "metadata": {
            "name": "credit-risk-v1",
            "algorithm": "LogisticRegression",
            "training_samples": n,
            "target": "Default within 12 months",
        },
    }


def make_rule_engine() -> dict[str, Any]:
    """Create a sample heuristic rule engine config for introspection.

    Returns a dict suitable for a heuristic introspector — represents a
    transaction monitoring rule with thresholds and data sources.

    Example:
        >>> config = make_rule_engine()
        >>> print(config['thresholds'])
    """
    return {
        "name": "velocity-monitoring-v1",
        "algorithm": "heuristic_rule",
        "description": "Detect accounts with rapid inflow-outflow patterns",
        "execution_schedule": "daily",
        "lookback_window": "14 days",
        "thresholds": [
            {"name": "velocity_ratio", "value": 0.85, "operator": "<=", "segment": "standard"},
            {"name": "velocity_ratio", "value": 0.90, "operator": "<=", "segment": "high_risk"},
            {"name": "min_inflow", "value": 2000, "operator": ">="},
        ],
        "data_sources": [
            {"name": "transaction_metrics", "type": "sql_table", "lookback": 14},
        ],
    }


def _register_fraud_detector(inv: Inventory) -> None:
    inv.register_model(
        name="fraud-detector-v2",
        owner="ml-engineering",
        tier="high",
        intended_purpose="Real-time fraud detection for P2P payment transactions",
        developers=["alice", "bob"],
        validator="carol",
        business_unit="Payments",
        model_type="ml_model",
        jurisdictions=["US", "CA"],
        tags=["fraud", "real-time", "xgboost"],
        actor="sample_data",
    )

    with inv.new_version("fraud-detector-v2", actor="sample_data") as v:
        v.add_component(
            "Inputs/features", type="feature_set", metadata={"count": 16, "source": "feature_store"}
        )
        v.add_component(
            "Processing/XGBClassifier",
            type="algorithm",
            metadata={"n_estimators": 50, "max_depth": 4},
        )
        v.add_component("Outputs/risk_score", type="probability_score")
        v.add_document(doc_type="system_design", title="Fraud Detection v2 System Design")
        v.add_document(doc_type="model_spec", title="Fraud Detection v2 Model Specification")
        v.add_evidence(evidence_type="performance_report", title="Q4 2025 Performance Report")
        v.set_training_target("SAR escalation within 90 days")
        v.set_run_frequency("real_time")
        v.set_next_validation_due("2027-01-01")


def _register_credit_model(inv: Inventory) -> None:
    inv.register_model(
        name="credit-risk-v1",
        owner="risk-analytics",
        tier="medium",
        intended_purpose="Credit risk scoring for loan applicants",
        developers=["dave"],
        validator="eve",
        business_unit="Lending",
        model_type="ml_model",
        jurisdictions=["US"],
        tags=["credit", "batch", "sklearn"],
        actor="sample_data",
    )

    with inv.new_version("credit-risk-v1", actor="sample_data") as v:
        v.add_component("Inputs/applicant_features", type="feature_set", metadata={"count": 8})
        v.add_component("Processing/StandardScaler", type="preprocessor")
        v.add_component("Processing/LogisticRegression", type="algorithm")
        v.add_component("Outputs/default_probability", type="probability_score")
        v.add_document(doc_type="model_spec", title="Credit Risk v1 Specification")
        v.set_training_target("Default within 12 months")
        v.set_run_frequency("daily")


def _register_rule_engine(inv: Inventory) -> None:
    inv.register_model(
        name="velocity-monitoring-v1",
        owner="compliance-ops",
        tier="medium",
        intended_purpose="Detect accounts with rapid inflow-outflow patterns for AML monitoring",
        developers=["frank"],
        business_unit="Compliance",
        model_type="heuristic",
        tags=["aml", "heuristic", "velocity"],
        actor="sample_data",
    )

    with inv.new_version("velocity-monitoring-v1", actor="sample_data") as v:
        v.add_component(
            "Inputs/transaction_metrics",
            type="data_source",
            metadata={"table": "transaction_metrics", "lookback": 14},
        )
        v.add_component(
            "Processing/velocity_rule", type="heuristic_rule", metadata={"threshold": 0.85}
        )
        v.add_component("Outputs/alerts", type="alert_queue")
        v.set_run_frequency("daily")
