# model-ledger

**Open-source model governance framework for financial services. Auto-discover models, trace dependencies, validate compliance.**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![v0.5.0](https://img.shields.io/badge/version-0.5.0-green.svg)](CHANGELOG.md)

---

## Why model-ledger?

Regulators require financial institutions to maintain a complete inventory of their models. Most teams track this in spreadsheets that are outdated the moment they're written. model-ledger automates it:

- **Auto-discover** models from your databases, APIs, and code repos
- **Build dependency graphs** automatically from data flow (no manual linking)
- **Trace lineage** end-to-end: from raw data through scoring to alerting
- **Validate compliance** against SR 11-7, EU AI Act, and NIST AI RMF
- **Persist an audit trail** as an immutable event log

Unlike MLflow or model registries that track ML models only, model-ledger tracks *everything* in the model risk ecosystem: ETL pipelines, heuristic rules, scoring jobs, alert queues, and ML models as a single connected graph.

## Install

```bash
pip install model-ledger                       # Core + SQLite backend
pip install model-ledger[snowflake]            # + Snowflake backend
pip install model-ledger[rest]                 # + REST API connector
pip install model-ledger[github]              # + GitHub connector
pip install model-ledger[all]                 # Everything
```

## Quick Start

```python
from model_ledger import Ledger, DataNode

# Persistent inventory — one line, zero infrastructure
ledger = Ledger.from_sqlite("./inventory.db")

# Define models with inputs and outputs
segmentation = DataNode("segmentation", outputs=["customer_segments"])
scorer = DataNode("fraud_scorer", inputs=["customer_segments"], outputs=["risk_scores"])
alerting = DataNode("fraud_alerts", inputs=["risk_scores"])

# Add and connect — dependencies build automatically from port matching
ledger.add([segmentation, scorer, alerting])
ledger.connect()

# Trace the full pipeline
ledger.trace("fraud_alerts")
# ['segmentation', 'fraud_scorer', 'fraud_alerts']

ledger.upstream("fraud_alerts")
# ['segmentation', 'fraud_scorer']

ledger.downstream("segmentation")
# ['fraud_scorer', 'fraud_alerts']
```

Data persists across sessions. Reopen the same file and your inventory is there.

## Discover Models From Your Systems

Most model discovery is "query a system, map rows to models." Connector factories handle this without writing classes.

### SQL databases

```python
from model_ledger import Ledger, sql_connector

ledger = Ledger.from_sqlite("./inventory.db")

# Simple: discover models from a registry table
models = sql_connector(
    name="model_registry",
    connection=my_db,
    query="SELECT name, owner, status FROM ml_models WHERE active = true",
    name_column="name",
)

# Advanced: parse SQL to auto-extract input/output table dependencies
etl_jobs = sql_connector(
    name="etl_scheduler",
    connection=my_db,
    query="SELECT job_name, raw_sql, cron FROM scheduled_jobs",
    name_column="job_name",
    sql_column="raw_sql",  # extracts FROM/JOIN tables as inputs, INSERT/CREATE as outputs
)

ledger.add(models.discover())
ledger.add(etl_jobs.discover())
ledger.connect()  # auto-links ETL outputs to model inputs
```

### REST APIs

```python
from model_ledger import rest_connector

# Works with MLflow, SageMaker, Vertex AI, or any JSON API
ml_models = rest_connector(
    name="mlflow",
    url="https://mlflow.internal/api/2.0/mlflow/registered-models/list",
    headers={"Authorization": "Bearer ..."},
    items_path="registered_models",
    name_field="name",
)
```

### GitHub repos

```python
from model_ledger import github_connector

# Discover pipeline-as-code: Airflow DAGs, dbt projects, scoring pipelines
pipelines = github_connector(
    name="ml_pipelines",
    repos=["myorg/ml-scoring"],
    token="ghp_...",
    project_path="projects",
    config_file="deploy.yaml",
    parser=my_yaml_parser,  # (project_name, file_content) -> DataNode
)
```

### Custom connectors

For anything the factories don't cover, implement the `SourceConnector` protocol directly:

```python
class SageMakerConnector:
    name = "sagemaker"

    def discover(self) -> list[DataNode]:
        endpoints = boto3.client("sagemaker").list_endpoints()
        return [
            DataNode(ep["EndpointName"], platform="sagemaker",
                     outputs=[ep["EndpointName"]],
                     metadata={"status": ep["EndpointStatus"]})
            for ep in endpoints["Endpoints"]
        ]
```

## Persistent Storage

```python
from model_ledger import Ledger

# SQLite — batteries included, zero infrastructure
ledger = Ledger.from_sqlite("./inventory.db")

# Snowflake — production scale
ledger = Ledger.from_snowflake(connection, schema="ANALYTICS.MODEL_LEDGER")

# In-memory — for testing
ledger = Ledger()

# Custom — implement the LedgerBackend protocol
ledger = Ledger(my_postgres_backend)
```

## Key Capabilities

### Dependency tracing

```python
ledger.trace("fraud_alerts")                              # Full pipeline path
ledger.upstream("fraud_alerts")                           # Everything that feeds this
ledger.downstream("segmentation")                         # Everything that depends on this
ledger.dependencies("fraud_alerts", direction="upstream")  # Detailed with relationship info
```

### Shared table disambiguation

When multiple models write to the same table, `DataPort` handles precision matching:

```python
from model_ledger import DataPort, DataNode

# Two models write to the same alert table with different model_name values
DataNode("check_rules", outputs=[DataPort("alerts", model_name="checks")])
DataNode("card_rules", outputs=[DataPort("alerts", model_name="cards")])

# This reader only connects to check_rules — model_name must match
DataNode("check_queue", inputs=[DataPort("alerts", model_name="checks")])
```

### Point-in-time inventory

```python
from datetime import datetime
inventory = ledger.inventory_at(datetime(2025, 12, 31))
# Returns all models that were active on that date
```

### Compliance validation

Built-in profiles for major model risk regulations:

| Profile | Regulation | Checks |
|---------|-----------|--------|
| `sr_11_7` | US Federal Reserve SR 11-7 | Validator independence, governance docs, validation schedule |
| `eu_ai_act` | EU AI Act (2024/1689) | Risk classification, data governance, human oversight |
| `nist_ai_rmf` | NIST AI RMF 1.0 | GOVERN, MAP, MEASURE, MANAGE functions |

### Model introspection

Extract metadata from fitted ML models automatically:

```python
from model_ledger import introspect

result = introspect(fitted_model)
result.algorithm        # "XGBClassifier"
result.features         # [FeatureInfo(name="velocity_30d", ...), ...]
result.hyperparameters  # {"n_estimators": 50, "max_depth": 4}
```

Ships with sklearn, XGBoost, and LightGBM support. Add your own via the `Introspector` protocol.

## How It Works

Every model, rule, pipeline, and queue is a **DataNode** with typed input and output ports. The Ledger matches ports to build the dependency graph automatically.

Under the hood, the Ledger maintains:
- **ModelRef** — the regulatory identity (name, owner, type, tier)
- **Snapshots** — immutable, timestamped observations (discovered, depends_on, validated)
- **Tags** — mutable pointers to snapshots (e.g., "production", "latest")

Every mutation is an append-only event. Nothing is deleted. This gives you a complete audit trail and point-in-time reconstruction for any date.

## Architecture

```
model-ledger
├── Ledger SDK           register, record, add, connect, trace, upstream, downstream
├── DataNode / DataPort  graph primitives with schema-aware port matching
├── Connector Factories  sql_connector, rest_connector, github_connector
├── Backends             SQLite (built-in), Snowflake (optional), custom (protocol)
├── Adapters             SQL parsing, table-based pipeline discovery
├── Compliance           SR 11-7, EU AI Act, NIST AI RMF validation profiles
└── Introspection        sklearn, XGBoost, LightGBM, custom (protocol)
```

## Design Principles

- **Everything is a DataNode** — ML models, heuristic rules, ETL pipelines, alert queues. One abstraction.
- **The graph builds itself** — declare inputs and outputs. Dependencies follow from port matching.
- **Schema-agnostic metadata** — `Snapshot.payload` is `dict[str, Any]`. The framework stores whatever your connectors discover.
- **Append-only audit trail** — every change is an immutable Snapshot. Full history, point-in-time queries.
- **Factory for the 80%, protocol for the 20%** — config-driven factories for common patterns, open protocols for anything custom.
- **Batteries included** — `pip install model-ledger` gives you persistence, discovery, graph building, and compliance with zero infrastructure.

## For Organizations

model-ledger is designed as a core framework with lightweight organization-specific extensions. The OSS core handles graph building, storage, compliance, and the connector factories. Your internal package provides:

- **Connector configs** — point `sql_connector()` at your tables, `rest_connector()` at your APIs
- **Custom connectors** — for internal platforms the factories don't cover
- **Authentication** — your database/API credentials and auth wrappers
- **Additional compliance profiles** — OSFI E-23, PRA SS1/23, MAS AIRG, or internal policies

Your internal repo should be thin config and credentials, not reimplemented logic.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All commits require DCO sign-off.

## License

Apache-2.0. See [LICENSE](LICENSE).
