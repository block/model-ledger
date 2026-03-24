# model-ledger

A typed, version-controlled model inventory and governance framework.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## What It Does

model-ledger provides a formal, machine-readable inventory for model risk management. It tracks models, governance documents, validation observations, and structured feedback — all as typed Python objects with pluggable storage and executable compliance profiles.

```python
from model_ledger import Inventory

inv = Inventory()

# Register a model
model = inv.register_model(
    name="Fraud Detection Model",
    owner="ML Engineering",
    tier="high",
    intended_purpose="Credit risk scoring for loan applicants",
    developers=["alice", "bob"],
    validator="carol",
)

# Build a version with the I/P/O component tree
with inv.new_version("Fraud Detection Model", version="2.0.0", actor="alice") as v:
    v.add_component("Inputs/credit_features", type="feature_set",
                     metadata={"count": 150, "source": "Feature Store"})
    v.add_component("Processing/xgboost_classifier", type="algorithm",
                     metadata={"library": "xgboost", "features": 200})
    v.add_component("Outputs/risk_score", type="probability_score",
                     metadata={"range": [0, 1]})
    v.add_document(doc_type="system_design", title="Fraud Detection v2 Design Doc")

# Validate against SR 11-7
from model_ledger.validate import validate

result = validate(model, inv.get_version("Fraud Detection Model", "2.0.0"), profile="sr_11_7")
print(result)

# Publish (immutable after this)
inv.publish_version("Fraud Detection Model", "2.0.0", actor="carol")
```

## Install

```bash
pip install model-ledger
```

## Key Concepts

- **Models** — Hierarchical I/P/O component trees per SR 11-7, with versions, ownership, and lifecycle states
- **Observations** — Validation findings from any source (human reviewers, AI agents, automated tools), with full lifecycle tracking (draft → issued/removed)
- **Feedback** — Structured records of what happened to each observation: kept, removed, modified — and why
- **Validation profiles** — Executable compliance checks (SR 11-7 built-in, extensible to EU AI Act, NIST AI RMF, etc.)
- **Immutable versions** — Published model versions cannot be modified. All changes require a new version with an audit event.
- **Pluggable storage** — SQLite by default, extensible via the `InventoryBackend` protocol

## Documentation

- [What & Why](docs/what-and-why.md) — Motivation, architecture, and strategic context
- [Technical Design](docs/technical-design.md) — Data model, SDK, validation engine, and code examples

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and contribution guidelines.

All commits require DCO sign-off (`git commit --signoff`) and PR titles use conventional commit format.

## Project Resources

| Resource | Description |
|----------|-------------|
| [CODEOWNERS](CODEOWNERS) | Project lead(s) |
| [GOVERNANCE.md](GOVERNANCE.md) | Block open source governance |
| [LICENSE](LICENSE) | Apache License, Version 2.0 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute |

## License

Apache-2.0. See [LICENSE](LICENSE).
