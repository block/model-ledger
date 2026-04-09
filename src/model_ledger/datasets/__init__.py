"""Built-in sample models and datasets for demos, tutorials, and testing.

Like sklearn.datasets, these provide ready-to-use examples that showcase
model-ledger's capabilities without requiring external data.

    >>> from model_ledger.datasets import load_sample_inventory
    >>> inv = load_sample_inventory()
    >>> print(len(inv.list_models()))  # 3 models ready to use
"""

from model_ledger.datasets.demo import load_demo_inventory
from model_ledger.datasets.samples import (
    load_sample_inventory,
    make_credit_model,
    make_fraud_detector,
    make_rule_engine,
)

__all__ = [
    "load_demo_inventory",
    "load_sample_inventory",
    "make_credit_model",
    "make_fraud_detector",
    "make_rule_engine",
]
