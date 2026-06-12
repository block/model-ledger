---
title: Connectors & discovery
description: Point factory connectors at your SQL databases, REST APIs, and GitHub repos to discover models automatically — or implement the SourceConnector protocol for anything else.
---

# Connectors & discovery

A connector emits `DataNode`s from a source system. Add them to the ledger and call
`connect()` — the cross-platform graph assembles itself from port matching. Three
factory connectors ship in core; anything else is a small protocol implementation.

## SQL databases

```python
from model_ledger import Ledger, sql_connector

ledger = Ledger.from_sqlite("./inventory.db")

# Simple: read a registry table
models = sql_connector(
    name="model_registry",
    connection=my_db,
    query="SELECT name, owner, status FROM ml_models WHERE active = true",
    name_column="name",
)

# Advanced: auto-parse SQL to extract table dependencies
etl_jobs = sql_connector(
    name="etl_scheduler",
    connection=my_db,
    query="SELECT job_name, raw_sql, cron FROM scheduled_jobs",
    name_column="job_name",
    sql_column="raw_sql",   # FROM/JOIN → inputs, INSERT/CREATE → outputs
)

ledger.add(models.discover())
ledger.add(etl_jobs.discover())
ledger.connect()            # links ETL outputs to model inputs automatically
```

## REST APIs

Works with MLflow, SageMaker, Vertex AI, or any JSON API:

```python
from model_ledger import rest_connector

ml_models = rest_connector(
    name="mlflow",
    url="https://mlflow.internal/api/2.0/mlflow/registered-models/list",
    headers={"Authorization": "Bearer ..."},
    items_path="registered_models",
    name_field="name",
)
ledger.add(ml_models.discover())
```

## GitHub repos (pipelines-as-code)

Discover Airflow DAGs, dbt projects, or scoring pipelines from config files:

```python
from model_ledger import github_connector

pipelines = github_connector(
    name="ml_pipelines",
    repos=["myorg/ml-scoring"],
    token="ghp_...",
    project_path="projects",
    config_file="deploy.yaml",
    parser=my_yaml_parser,   # (project_name, file_content) -> DataNode
)
ledger.add(pipelines.discover())
```

## Custom connectors

Implement the `SourceConnector` protocol — a `name` and a `discover()` returning
`DataNode`s — for anything the factories don't cover:

```python
from model_ledger import DataNode

class SageMakerConnector:
    name = "sagemaker"

    def discover(self) -> list[DataNode]:
        endpoints = boto3.client("sagemaker").list_endpoints()["Endpoints"]
        return [
            DataNode(ep["EndpointName"], platform="sagemaker",
                     outputs=[ep["EndpointName"]],
                     metadata={"status": ep["EndpointStatus"]})
            for ep in endpoints
        ]

ledger.add(SageMakerConnector().discover())
ledger.connect()
```

!!! tip "Every connector is a growth event"
    Each new connector extends the discovery surface — a node in your warehouse links
    to a model in MLflow links to a queue in your alerting system, with no shared ID
    scheme. That's how one graph spans every platform.

## Recurring discovery

Run connectors on a schedule (cron, Airflow, Prefect) writing to a shared backend.
`add()` is idempotent — it content-hashes nodes and skips unchanged ones — and a
`last_seen` timestamp is updated every run, so you can detect models that have gone
silent. See the recipe: [Discover from a SQL registry](../recipes/discover-sql.md).
