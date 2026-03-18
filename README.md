# model-ledger

The first Apache-2.0-licensed, developer-first Python framework for ML model governance.

90% of banks use spreadsheets for model inventory. We built the alternative.

## Quickstart

```python
from model_ledger import Inventory

inv = Inventory()

inv.register_model(
    name="fraud_detector",
    owner="risk-team",
    tier="high",
    intended_purpose="Score transaction fraud risk in real time",
)

with inv.new_version("fraud_detector", actor="alice") as v:
    v.add_component("inputs/features/transaction_signals", type="FeatureSet")
    v.add_component("processing/algorithm/xgboost", type="Algorithm")
    v.add_component("outputs/scores/fraud_probability", type="ProbabilityScore")
    v.add_document(doc_type="system_design", title="CSD v2")

    result = v.validate(profile="sr_11_7")
    print(result)  # PASS: 9/9 rules satisfied

inv.publish("fraud_detector", "0.1.0", actor="alice")
```

## Install

```bash
pip install model-ledger
```

## What It Does

| Concept | Spreadsheet | MLflow | model-ledger |
|---------|-------------|--------|--------------|
| Model inventory | Ad hoc columns | Not provided | Typed schema with SR 11-7 fields |
| Component tree (I/P/O) | Flat lists | Not supported | First-class hierarchical structure |
| Regulatory validation | Manual checklist | None | Automated compliance profiles |
| Audit trail | None | Run history | Append-only, immutable event log |
| Version control | Manual | Model versions | Immutable published versions |

## Features

- **Typed schema** — Pydantic models covering SR 11-7, EU AI Act, OSFI E-23, PRA SS1/23, NIST AI RMF
- **Component tree** — SR 11-7's Inputs/Processing/Outputs structure as first-class data
- **Compliance profiles** — Validate your inventory against regulatory frameworks
- **Audit trail** — Append-only event log on every mutation
- **Immutable versions** — Published versions cannot be modified (enforced at SDK and storage layer)
- **Pluggable storage** — SQLite by default, extensible via Protocol-based backends
- **CLI** — `model-ledger validate`, `model-ledger export`, `model-ledger tree`

## License

Apache-2.0. See [LICENSE](LICENSE).
