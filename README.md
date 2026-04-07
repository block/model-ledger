# model-ledger

**Open-source model governance framework for financial services. Auto-discover models, trace dependencies, validate compliance.**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)

---

## The Problem

Every financial institution under model risk regulation (SR 11-7, EU AI Act, NIST AI RMF) needs a model inventory. Today, most use spreadsheets. model-ledger replaces that with code: auto-discovered models, dependency graphs, compliance validation, and an immutable audit trail.

## Quick Start

```bash
pip install model-ledger
```

```python
from model_ledger import Ledger, DataNode

# Persistent inventory in one line
ledger = Ledger.from_sqlite("./inventory.db")

# Define models with inputs and outputs
segmentation = DataNode("segmentation", outputs=["segments"])
scorer = DataNode("fraud_scorer", inputs=["segments"], outputs=["scores"])
alerting = DataNode("fraud_alerts", inputs=["scores"])

# Add and connect — dependencies build automatically
ledger.add([segmentation, scorer, alerting])
ledger.connect()

# Query the graph
ledger.trace("fraud_alerts")    # ['segmentation', 'fraud_scorer', 'fraud_alerts']
ledger.upstream("fraud_alerts") # ['segmentation', 'fraud_scorer']
```

## Config-Driven Discovery

Most model discovery is "query a system, map rows to models." The connector factories handle this without writing classes:

### From SQL databases

```python
from model_ledger import Ledger, sql_connector

ledger = Ledger.from_sqlite("./inventory.db")

# Discover models from any table
models = sql_connector(
    name="model_registry",
    connection=my_db,
    query="SELECT name, owner, status FROM ml_models WHERE active = true",
    name_column="name",
)

# Discover ETL jobs with dependency parsing
etl_jobs = sql_connector(
    name="etl",
    connection=my_db,
    query="SELECT name, raw_sql, schedule FROM etl_jobs",
    name_column="name",
    sql_column="raw_sql",  # auto-extracts input/output tables from SQL
)

ledger.add(models.discover())
ledger.add(etl_jobs.discover())
ledger.connect()
```

### From REST APIs

```python
from model_ledger import rest_connector

# Discover from MLflow, SageMaker, Vertex AI, or any REST API
mlflow_models = rest_connector(
    name="mlflow",
    url="https://mlflow.internal/api/2.0/mlflow/registered-models/list",
    headers={"Authorization": "Bearer ..."},
    items_path="registered_models",
    name_field="name",
)
```

### From GitHub repos

```python
from model_ledger import github_connector

# Discover pipeline-as-code (Airflow DAGs, dbt models, Prefect flows)
pipelines = github_connector(
    name="ml_pipelines",
    repos=["myorg/ml-scoring"],
    token="ghp_...",
    project_path="projects",
    config_file="config.yaml",
    parser=my_yaml_parser,  # you provide: (name, content) -> DataNode
)
```

### Custom connectors

For anything the factories don't cover, implement the `SourceConnector` protocol:

```python
class MyConnector:
    name = "my_platform"

    def discover(self) -> list[DataNode]:
        # Call your API, parse your configs, query your database
        return [DataNode("model_a", inputs=["features"], outputs=["scores"])]
```

## Persistent Storage

```python
from model_ledger import Ledger

# SQLite — zero infrastructure, batteries included
ledger = Ledger.from_sqlite("./inventory.db")

# Snowflake — for production at scale
# pip install model-ledger[snowflake]
ledger = Ledger.from_snowflake(connection, schema="ANALYTICS.MODEL_LEDGER")

# In-memory — for testing
ledger = Ledger()

# Custom backend — implement the LedgerBackend protocol
ledger = Ledger(my_custom_backend)
```

## How It Works

Everything is a **DataNode** with inputs and outputs. The dependency graph builds itself from port matching.

```
Your Systems                    model-ledger                     Output
-----------                    ------------                     ------

 ETL Scheduler ─┐                                         ┌─ Dependency graph
 Rules Engine  ─┤─ Connectors ─→ Ledger.add() ──────────→├─ Point-in-time inventory
 ML Registry   ─┤               Ledger.connect()          ├─ Compliance reports
 Case Manager  ─┘               Ledger.trace()            └─ Audit trail
```

Each `add()` creates a **ModelRef** (identity) and a **Snapshot** (immutable observation). Each `connect()` matches output ports to input ports and records dependency links. The entire history is an append-only event log.

## Key Features

### Shared tables with discriminators

When multiple models write to the same table, `DataPort` handles precision matching:

```python
from model_ledger import DataPort, DataNode

# Two models write to the same alert table
DataNode("check_rules", outputs=[DataPort("alerts", model_name="checks")])
DataNode("card_rules", outputs=[DataPort("alerts", model_name="cards")])

# This reader only connects to check_rules (matching model_name)
DataNode("check_queue", inputs=[DataPort("alerts", model_name="checks")])
```

### SQL parsing adapters

Extract table references, write targets, and filters from SQL:

```python
from model_ledger.adapters.sql import extract_tables_from_sql, extract_write_tables

extract_tables_from_sql("SELECT * FROM schema.source JOIN schema.dim ON 1=1")
# ['schema.source', 'schema.dim']

extract_write_tables("INSERT INTO schema.output SELECT * FROM source")
# ['schema.output']
```

### Dependency tracing

```python
ledger.trace("fraud_alerts")                              # Full pipeline path
ledger.upstream("fraud_alerts")                           # All upstream models
ledger.downstream("segmentation")                         # All downstream models
ledger.dependencies("fraud_alerts", direction="upstream")  # Detailed dependency info
```

### Point-in-time inventory

```python
# What models existed on a specific date?
inventory = ledger.inventory_at(audit_date)
```

### Compliance validation

| Profile | Regulation | What It Checks |
|---------|-----------|----------------|
| `sr_11_7` | US Federal Reserve SR 11-7 | Validator independence, governance docs, validation schedule |
| `eu_ai_act` | EU AI Act (2024/1689) | Risk assessment, data governance, human oversight |
| `nist_ai_rmf` | NIST AI RMF 1.0 | GOVERN, MAP, MEASURE, MANAGE functions |

### Model introspection

Extract algorithm, features, and hyperparameters from fitted models:

```python
from model_ledger import introspect

result = introspect(fitted_model)
# result.algorithm        -> "XGBClassifier"
# result.features         -> [FeatureInfo(name="velocity_30d", ...), ...]
# result.hyperparameters  -> {"n_estimators": 50, "max_depth": 4}
```

Ships with sklearn, XGBoost, and LightGBM introspectors. Write your own with the `Introspector` protocol.

## Install

```bash
pip install model-ledger                       # Core (SQLite backend included)
pip install model-ledger[snowflake]            # + Snowflake backend
pip install model-ledger[rest]                 # + REST API connector
pip install model-ledger[github]              # + GitHub connector
pip install model-ledger[all]                 # Everything
pip install model-ledger[cli]                  # + CLI
pip install model-ledger[introspect-sklearn]   # + sklearn introspector
```

## Architecture

```
model-ledger (OSS)
├── Ledger SDK          — register, record, add, connect, trace, upstream, downstream
├── DataNode / DataPort — graph primitives with schema-aware port matching
├── Connector Factories — sql_connector, rest_connector, github_connector
├── Backends            — SQLite (built-in), Snowflake (optional), custom (protocol)
├── Adapters            — SQL parsing, table discovery
├── Compliance          — SR 11-7, EU AI Act, NIST AI RMF validation profiles
└── Introspection       — sklearn, XGBoost, LightGBM, custom (protocol)
```

## Design Principles

- **Everything is a DataNode** — models, rules, pipelines, queues. Same abstraction.
- **The graph builds itself** — match output ports to input ports. No manual linking.
- **Schema-agnostic metadata** — `Snapshot.payload` is `dict[str, Any]`. Your models look different from ours. The framework doesn't care.
- **Event log, not a table** — every change is an immutable Snapshot. Full audit history.
- **Factory for the 80%, protocol for the 20%** — config-driven factories for common patterns, protocols for anything custom.
- **Batteries included** — `pip install model-ledger` gets you persistence, discovery, graph, and tracing with zero infrastructure.

## For Organizations

model-ledger is designed as a core framework with organization-specific extensions. The OSS core handles data models, graph building, storage, and compliance. Your internal package adds:

- **Connector configs** — point `sql_connector()` at your tables, `rest_connector()` at your APIs
- **Custom connectors** — for platforms the factories don't cover
- **Auth wrappers** — your Snowflake/database authentication
- **Validation profiles** — for your regulations (OSFI E-23, PRA SS1/23, MAS AIRG)

The goal: your internal package should be lightweight config, not reimplemented logic.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All commits require DCO sign-off.

## License

Apache-2.0. See [LICENSE](LICENSE).
