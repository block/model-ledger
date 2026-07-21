---
title: CLI
description: The model-ledger command line — launch the MCP server or REST API over any backend, and work with a local inventory.
---

# CLI

Install the CLI extra, then `model-ledger --help` lists everything:

```bash
pip install "model-ledger[cli]"
model-ledger --help
```

The CLI has two jobs: **launch the agent and HTTP surfaces** (the bridge to the rest of
this documentation), and **work with a local inventory** from the terminal.

## Launch a surface

These serve the [Ledger](../reference/index.md) over any [backend](backends.md) — in-memory,
SQLite, JSON, Snowflake, or a remote HTTP service.

=== "MCP (for agents)"

    ```bash
    model-ledger mcp                                       # in-memory
    model-ledger mcp --demo                                # sample inventory
    model-ledger mcp --backend sqlite --path ./inv.db      # persistent
    model-ledger mcp --backend snowflake --schema DB.MODEL_LEDGER
    model-ledger mcp --backend http --path https://model-ledger.internal:8000
    ```

=== "REST API"

    ```bash
    model-ledger serve --demo --port 8000
    # → OpenAPI docs at http://localhost:8000/docs
    ```

`--backend` accepts `memory` · `sqlite` · `json` · `snowflake` · `http`; `--path` is the
file path (sqlite/json) or URL (http); Snowflake reads credentials from the environment
(see [Choosing a backend](backends.md)).

## Work with a local inventory

These commands operate on a local file-based inventory (`--db`, default `inventory.db`
or `$MODEL_LEDGER_DB`) and render as a table or `--format json`.

| Command | What it does |
|---|---|
| `model-ledger list` | List registered models |
| `model-ledger show <name>` | Show one model's details and versions |
| `model-ledger validate <name> --profile <p>` | Check a model against a compliance profile (`sr_11_7`, `eu_ai_act`, `nist_ai_rmf`) |
| `model-ledger audit-log <name>` | Print the model's audit trail |
| `model-ledger export <name> --output <dir>` | Export an audit pack |
| `model-ledger introspect <artifact> --allow-pickle` | Extract algorithm/features from a fitted model file |

```bash
model-ledger list --format json
model-ledger validate credit_scorecard --profile sr_11_7
model-ledger audit-log credit_scorecard
```

!!! info "Which command for which surface"
    `mcp` and `serve` expose the full [event-log Ledger](../concepts/snapshot.md) — the one
    the [SDK](../quickstart.md), [agents](agents.md), and [REST API](backends.md) all share.
    Use them to point Claude or a dashboard at your inventory. The `validate` profiles map
    to the frameworks in the [Governance guide](../governance.md).
