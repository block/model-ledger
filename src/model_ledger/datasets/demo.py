"""Demo inventory with sample models, events, and dependency connections.

Provides a realistic multi-platform inventory for first-time users,
tutorials, and integration testing. Includes lifecycle events (retrained,
deployed, metadata_updated) and data-flow dependencies between nodes.

    >>> from model_ledger import Ledger
    >>> from model_ledger.datasets.demo import load_demo_inventory
    >>> ledger = Ledger()
    >>> load_demo_inventory(ledger)
    >>> print(len(ledger.list()))  # 7 models
"""

from __future__ import annotations

from model_ledger.graph.models import DataNode
from model_ledger.sdk.ledger import Ledger


def load_demo_inventory(ledger: Ledger) -> None:
    """Populate *ledger* with 7 sample models across different platforms.

    Creates:
    - 2 data nodes (feature store, ETL pipeline)
    - 3 ML models (fraud scoring, churn predictor, credit risk)
    - 1 alerting engine
    - 1 rules engine

    Dependency edges are inferred via matching input/output ports, and
    lifecycle events are recorded against selected models.
    """
    ledger.add(
        [
            DataNode(
                "customer_features",
                platform="database",
                outputs=["customer_data"],
                metadata={"owner": "data-team", "model_type": "data_source", "description": "Core customer feature store"},
            ),
            DataNode(
                "transaction_pipeline",
                platform="etl",
                inputs=["raw_transactions"],
                outputs=["processed_transactions", "customer_data"],
                metadata={"owner": "data-team", "model_type": "etl_pipeline", "schedule": "hourly"},
            ),
            DataNode(
                "fraud_scoring",
                platform="ml",
                inputs=["customer_data", "processed_transactions"],
                outputs=["fraud_scores"],
                metadata={
                    "owner": "risk-team",
                    "model_type": "ml_model",
                    "algorithm": "gradient_boosted_trees",
                },
            ),
            DataNode(
                "churn_predictor",
                platform="ml",
                inputs=["customer_data"],
                outputs=["churn_probabilities"],
                metadata={"owner": "growth-team", "model_type": "ml_model", "algorithm": "logistic_regression"},
            ),
            DataNode(
                "alert_engine",
                platform="alerting",
                inputs=["fraud_scores"],
                metadata={"owner": "ops-team", "model_type": "alerting"},
            ),
            DataNode(
                "credit_risk",
                platform="ml",
                inputs=["customer_data", "processed_transactions"],
                outputs=["credit_scores"],
                metadata={"owner": "risk-team", "model_type": "ml_model", "algorithm": "neural_network"},
            ),
            DataNode(
                "pricing_rules",
                platform="rules",
                inputs=["credit_scores", "churn_probabilities"],
                metadata={"owner": "pricing-team", "model_type": "heuristic"},
            ),
        ]
    )
    ledger.connect()

    # -- Lifecycle events --

    fraud = ledger.get("fraud_scoring")
    ledger.record(
        fraud,
        event="retrained",
        payload={
            "accuracy": 0.94,
            "features_added": ["device_fingerprint", "velocity_24h"],
            "training_samples": 1_200_000,
        },
        actor="ml-pipeline",
    )
    ledger.record(
        fraud,
        event="deployed",
        payload={"environment": "production", "version": "v3.2"},
        actor="ci-pipeline",
    )
    ledger.record(
        fraud,
        event="metadata_updated",
        payload={
            "model_card_url": "https://docs.example.com/fraud-scoring",
            "training_data": "Customer transactions, 2024-2026",
        },
        actor="data-scientist",
    )

    churn = ledger.get("churn_predictor")
    ledger.record(
        churn,
        event="retrained",
        payload={"accuracy": 0.87, "auc": 0.91},
        actor="ml-pipeline",
    )

    credit = ledger.get("credit_risk")
    ledger.record(
        credit,
        event="metadata_updated",
        payload={
            "regulatory_framework": "Basel III",
            "last_validated": "2026-03-15",
        },
        actor="compliance-team",
    )
