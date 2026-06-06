---
title: Quickstart
description: Install model-ledger and reach your first dependency trace in under a minute — no infrastructure, no credentials.
---

# Quickstart

Zero infrastructure. Zero credentials. From `pip install` to a working dependency
graph in under a minute.

=== "Python SDK"

    ```bash
    pip install model-ledger
    ```

    ```python
    from model_ledger import Ledger, DataNode

    ledger = Ledger()  # in-memory; swap for Ledger.from_sqlite("inv.db") to persist

    ledger.add([
        DataNode("raw_txns",      platform="warehouse", outputs=["transactions"]),
        DataNode("feature_build", platform="etl",       inputs=["transactions"],  outputs=["features"]),
        DataNode("fraud_model",   platform="ml",         inputs=["features"],      outputs=["risk_scores"]),
        DataNode("review_queue",  platform="alerting",   inputs=["risk_scores"]),
    ])
    ledger.connect()                 # ports match → edges appear

    print(ledger.trace("review_queue"))
    # ['raw_txns', 'feature_build', 'fraud_model', 'review_queue']

    print(ledger.upstream("fraud_model"))
    # ['raw_txns', 'feature_build']
    ```

    That's the whole idea: **declare nodes, the graph connects itself.** Next, give a
    node an identity and a history → [Register a model](#register-a-model).

=== "Talk to it (MCP)"

    ```bash
    pip install "model-ledger[mcp]"

    # Register the server with Claude Code (one time)
    claude mcp add model-ledger -- model-ledger mcp --demo
    ```

    Then just ask:

    > **You:** what models are in my inventory?
    >
    > **Claude:** 7 models across 5 platforms. `fraud_scoring` was retrained and
    > deployed this week. Want me to dig into anything?
    >
    > **You:** if we deprecate `customer_features`, what breaks?
    >
    > **Claude:** 3 models consume it directly, 2 more transitively.

    The `--demo` flag loads a sample inventory so you can explore before connecting
    your own data. See the [Agent guide](guides/agents.md) for the full tool surface.

=== "REST API"

    ```bash
    pip install "model-ledger[rest-api]"
    model-ledger serve --demo --port 8000
    ```

    Open **http://localhost:8000/docs** for live, auto-generated OpenAPI docs, or:

    ```bash
    curl "localhost:8000/query?limit=5"
    curl "localhost:8000/trace/fraud_scoring?direction=upstream"
    curl "localhost:8000/overview"
    ```

## Register a model

A `DataNode` gives you the graph. [`register()`](reference/index.md) gives a model an
**identity** and starts its **history** — the two things a regulator asks for.

```python
from model_ledger import Ledger
ledger = Ledger.from_sqlite("./inventory.db")

ledger.register(
    name="fraud_scoring",
    owner="risk-team",
    model_type="ml_model",
    tier="high",
    purpose="Real-time card fraud detection",
)

# Record an event — any payload you like, no schema to maintain
ledger.record("fraud_scoring", "retrained",
              payload={"accuracy": 0.94, "features_added": ["velocity_24h"]})

for snap in ledger.history("fraud_scoring"):
    print(snap.timestamp, snap.event_type)
# ... registered
# ... retrained
```

Every call appends an immutable [Snapshot](concepts/snapshot.md). Nothing is
overwritten — that's what makes the inventory auditable.

## Choose where it lives

Storage is a one-line decision and never changes your code:

```python
from model_ledger import Ledger
from model_ledger.backends.json_files import JsonFileLedgerBackend

Ledger()                                       # in-memory — tests & demos
Ledger.from_sqlite("./inventory.db")           # zero-infra, single file
Ledger(JsonFileLedgerBackend("./inventory"))   # git-friendly JSON files
Ledger.from_snowflake(conn, schema="DB.MODEL_LEDGER")  # production
```

[More on backends :octicons-arrow-right-24:](guides/backends.md)

## Where to next

<div class="grid cards" markdown>

- :material-cube-outline: &nbsp;__[Concepts](concepts/index.md)__ — DataNode, Snapshot, Composite. The whole model in three ideas.
- :material-robot-outline: &nbsp;__[Agent guide](guides/agents.md)__ — the 8 MCP tools and a worked multi-tool transcript.
- :material-book-open-variant: &nbsp;__[Recipes](recipes/index.md)__ — copy-paste solutions to real tasks.
- :material-api: &nbsp;__[API reference](reference/index.md)__ — generated from source, never out of date.

</div>
