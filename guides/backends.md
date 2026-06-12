---
title: Choosing a backend
description: Storage is storage-agnostic and one line to change — in-memory, SQLite, JSON files, Snowflake, or a remote HTTP API.
---

# Choosing a backend

Storage is a `LedgerBackend` protocol, so the choice is one line and never leaks into
your code. Start simple; upgrade when you need scale.

| Backend | Use it for | One-liner |
|---------|-----------|-----------|
| **In-memory** | Tests, demos, throwaway exploration | `Ledger()` |
| **SQLite** | Local persistence, single user, zero infra | `Ledger.from_sqlite("inv.db")` |
| **JSON files** | Git-friendly, human-readable, diff-able inventory | `Ledger(JsonFileLedgerBackend("./inv"))` |
| **Snowflake** | Production, org-scale, shared truth | `Ledger.from_snowflake(conn, schema="DB.MODEL_LEDGER")` |
| **HTTP** | Talk to a remote model-ledger REST service | `Ledger(HttpLedgerBackend(url))` |

```python
from model_ledger import Ledger
from model_ledger.backends.json_files import JsonFileLedgerBackend
from model_ledger.backends.http import HttpLedgerBackend

Ledger()                                                  # in-memory
Ledger.from_sqlite("./inventory.db")                      # SQLite
Ledger(JsonFileLedgerBackend("./inventory"))              # JSON files
Ledger.from_snowflake(conn, schema="DB.MODEL_LEDGER")     # Snowflake
Ledger(HttpLedgerBackend("https://model-ledger:8000"))    # remote REST
```

## JSON files are git-friendly

The default JSON layout is meant to be inspected, diffed, and version-controlled —
your inventory as plain text:

```
inventory/
├── models/
│   ├── fraud_scoring.json
│   └── churn_predictor.json
├── snapshots/
│   ├── a1b2c3d4.json
│   └── e5f6g7h8.json
└── tags/
    └── {model_hash}/production.json
```

## Serving and the CLI

The CLI launches either agent or HTTP surfaces over any backend:

```bash
model-ledger serve --backend sqlite --path ./inventory.db --port 8000
model-ledger mcp   --backend snowflake --schema DB.MODEL_LEDGER
```

Snowflake reads credentials from the environment (`SNOWFLAKE_ACCOUNT`,
`SNOWFLAKE_USER`, and either `SNOWFLAKE_PASSWORD` or
`SNOWFLAKE_AUTHENTICATOR=externalbrowser` for SSO). Install the extra first:
`pip install "model-ledger[snowflake]"`.

## Bring your own

Anything that satisfies the `LedgerBackend` protocol works — Postgres, DynamoDB, a
graph DB. Implement the protocol methods and pass an instance to `Ledger(...)`. See the
[API reference](../reference/index.md) for the protocol surface.

To make your backend resolvable by name from the CLI (`--backend <name>`) without any
change to the core, register it under the `model_ledger.backends` **entry point** in your
package — the storage-agnostic extension contract from
[ADR 0005](../adr/0005-storage-agnostic.md):

```toml
# your package's pyproject.toml
[project.entry-points."model_ledger.backends"]
postgres = "my_package:PostgresBackend"
```

model-ledger discovers it and constructs it with the connection string if one is given
(`PostgresBackend(path)`), otherwise with no arguments:

```bash
model-ledger serve --backend postgres --path "postgresql://..."
```
