# model-ledger

**The first open-source, developer-first model inventory framework for regulatory compliance.**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-174%20passing-brightgreen.svg)]()

---

## The Problem

Every bank, fintech, and insurer subject to model risk regulation needs a model inventory. Today:

- **56% of financial institutions have NO dedicated MRM technology** (PwC 2022)
- **90% use spreadsheets** for model governance (RMA 2024)
- **No Apache-2.0 tool exists** that bridges Model Cards, Model Registry, and Model Inventory

model-ledger changes this. It's governance as code.

## Quick Start

```bash
pip install model-ledger
```

```python
from model_ledger import Inventory

inv = Inventory()

# Register a model
inv.register_model(
    name="fraud-detector",
    owner="ml-team",
    tier="high",
    intended_purpose="Real-time fraud detection for payment transactions",
    developers=["alice", "bob"],
    validator="carol",
)

# Build a version — introspect, document, validate
with inv.new_version("fraud-detector") as v:
    v.introspect(fitted_model)  # auto-extract algorithm, features, hyperparams
    v.add_document(doc_type="system_design", title="Fraud Detection v2 Design Doc")
    v.set_next_validation_due("2027-01-01")
    result = v.validate(profile="sr_11_7")  # compliance check
    print(result)  # PASS or FAIL with specific violations

# Export audit pack — one self-contained HTML file
from model_ledger.export import export_audit_pack
export_audit_pack(inventory=inv, model_name="fraud-detector",
                  format="html", output_path="audit-pack.html")
```

## Try It Now — Built-in Sample Data

Like `sklearn.datasets`, model-ledger ships with ready-to-use sample models:

```python
from model_ledger.datasets import load_sample_inventory, make_fraud_detector

# Pre-built inventory with 3 financial services models
inv = load_sample_inventory()
for m in inv.list_models():
    print(f"{m.name}: {m.tier.value} tier, {m.model_type.value}")

# Create a real fitted XGBoost model for introspection
data = make_fraud_detector()  # returns fitted XGBClassifier + 16 features
```

## Features

### Introspection — auto-extract metadata from any model

Plugin-based system that extracts algorithm, hyperparameters, features, and structure from fitted models. Ships with sklearn, XGBoost, and LightGBM. Extensible via entry points for any framework.

```python
from model_ledger.datasets import make_fraud_detector
from model_ledger.introspect.registry import get_registry

data = make_fraud_detector()
intro = get_registry().find(data["model"])
result = intro.introspect(data["model"])

print(result.algorithm)        # "XGBClassifier"
print(len(result.features))    # 16
print(result.hyperparameters)  # {"n_estimators": 50, "max_depth": 4, ...}
```

### Three compliance profiles — validate against real regulations

| Profile | Regulation | What It Checks |
|---------|-----------|----------------|
| `sr_11_7` | US Federal Reserve SR 11-7 | Validator independence, I/P/O structure, governance docs, validation schedule |
| `eu_ai_act` | EU AI Act (2024/1689) | Risk assessment, data governance, transparency, human oversight, affected populations |
| `nist_ai_rmf` | NIST AI RMF 1.0 | GOVERN, MAP, MEASURE, MANAGE — accountability, bias, monitoring, incident response |

```python
from model_ledger.validate.engine import validate

result = validate(model, version, profile="eu_ai_act")
print(result)  # FAIL: eu_risk_assessment, eu_data_governance, ...
```

### CLI — governance from the command line

```bash
model-ledger list                                 # List all models
model-ledger show my-model --version 0.1.0        # Model details
model-ledger validate my-model --profile sr_11_7  # Compliance check (exit 1 on fail)
model-ledger validate my-model --format json      # Machine-readable for CI/CD
model-ledger audit-log my-model                   # Full audit trail
model-ledger export my-model --format html        # Audit pack
```

### Audit pack export — self-contained compliance artifacts

Single-file HTML with executive summary, component tree, validation results, and full audit trail. No external dependencies. Share via email, attach to regulatory filings, or embed in wikis.

Formats: **HTML** (primary), **JSON** (machine-readable), **Markdown** (version-controllable).

### Pluggable storage — bring your own backend

SQLite (default), InMemory (testing), or implement `InventoryBackend` for Postgres, Snowflake, DynamoDB, or any database.

```python
inv = Inventory()                              # SQLite, auto-creates inventory.db
inv = Inventory(backend=InMemoryBackend())     # In-memory for testing
inv = Inventory(backend=MyCustomBackend())     # Your own backend
```

## Install

```bash
pip install model-ledger                          # Core
pip install model-ledger[cli]                     # + CLI
pip install model-ledger[introspect-sklearn]      # + sklearn introspector
pip install model-ledger[introspect-xgboost]      # + XGBoost introspector
pip install model-ledger[introspect-lightgbm]     # + LightGBM introspector
```

## Architecture

```
model-ledger
├── Core       — Pydantic data models, enums, typed exceptions
├── SDK        — Inventory, DraftVersion (fluent context manager API)
├── Introspect — Plugin protocol + sklearn/XGBoost/LightGBM
├── Validate   — SR 11-7, EU AI Act, NIST AI RMF profiles
├── Export     — HTML/JSON/Markdown audit packs
├── CLI        — Typer (list, show, validate, introspect, export)
├── Datasets   — Built-in sample models (like sklearn.datasets)
└── Backends   — SQLite, InMemory, protocol for custom
```

## Design Principles

- **Version-centric**: `with inv.new_version("model") as v:` — all mutations happen on a draft
- **Append-only audit trail**: Every mutation records who, what, when, and why
- **Immutable after publish**: Published versions cannot be modified — regulatory requirement
- **Typed contracts**: `IntrospectionResult` is the universal output for all introspectors
- **Plugin discovery**: Register introspectors via entry points — no code changes needed

## For Organizations

model-ledger is designed to be extended with organization-specific integrations:

- **Custom introspectors** for internal ML platforms (SageMaker, Vertex AI, custom serving)
- **Custom backends** for your data warehouse (Snowflake, BigQuery, Postgres)
- **Custom validation profiles** for your regulatory framework (OSFI E-23, PRA SS1/23)
- **Config generators** for your validation pipelines

The OSS core handles the schema, SDK, and compliance logic. Your internal package adds the adapters.

## Documentation

- [What & Why](docs/what-and-why.md) — Motivation, architecture, and strategic context
- [Technical Design](docs/technical-design.md) — Data model, SDK, validation engine

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All commits require DCO sign-off.

## License

Apache-2.0. See [LICENSE](LICENSE).
