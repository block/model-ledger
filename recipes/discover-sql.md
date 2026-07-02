---
title: "Recipe: Discover from a SQL registry"
description: Point a connector at a database table and pull models into the ledger on a schedule, idempotently.
---

# <span class="recipe-num">Recipe № 3</span> &nbsp; Discover from a SQL registry

**Problem.** Your models already live in a database table (a registry, a job
scheduler). You want them in the ledger — and kept in sync — without hand-entering
anything.

**Approach.** `sql_connector()` runs a query and turns each row into a
[`DataNode`](../concepts/datanode.md). `add()` is idempotent (it content-hashes nodes),
so re-running on a schedule only records genuine changes.

```python
import sqlite3
from model_ledger import Ledger, sql_connector

ledger = Ledger.from_sqlite("./inventory.db")
source = sqlite3.connect("./ml_platform.db")

models = sql_connector(
    name="model_registry",
    connection=source,
    query="SELECT name, owner, framework FROM ml_models WHERE active = 1",
    name_column="name",
)

added = ledger.add(models.discover())
ledger.connect()
print(f"discovered {len(added)} models")
```

## Extract dependencies from SQL automatically

If a row carries the SQL a job runs, point `sql_column` at it. The connector parses
`FROM`/`JOIN` as inputs and `INSERT`/`CREATE` as outputs — so the graph links your ETL
to the models that consume it:

```python
etl = sql_connector(
    name="etl_scheduler",
    connection=source,
    query="SELECT job_name, raw_sql FROM scheduled_jobs",
    name_column="job_name",
    sql_column="raw_sql",
)
ledger.add(etl.discover())
ledger.connect()      # ETL outputs now link to model inputs across platforms
```

## Run it on a schedule

Wrap the discover-and-connect in your scheduler of choice (cron, Airflow, Prefect):

```python
def sync():
    ledger = Ledger.from_snowflake(conn, schema="DB.MODEL_LEDGER")
    ledger.add(models.discover())
    ledger.connect()
```

Because `add()` skips unchanged nodes and refreshes a `last_seen` timestamp every run,
you get two things for free: a clean changelog (only real changes are recorded) and the
ability to spot models that have **gone silent** — discovered before, but missing from
the latest run.

!!! tip "Other sources"
    The same pattern works for REST APIs (`rest_connector`) and GitHub
    pipelines-as-code (`github_connector`), or write your own with the
    `SourceConnector` protocol — see [Connectors & discovery](../guides/connectors.md).
