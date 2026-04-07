# model-ledger

Open-source model inventory and governance framework. Apache-2.0.

## Build & Test

```bash
.venv/bin/python -m pytest tests/ -v
.venv/bin/python -m pytest tests/test_file.py::test_name -v  # single test
.venv/bin/python -m ruff check src/ tests/
.venv/bin/python -m ruff format src/ tests/
.venv/bin/python -m mypy src/
```

## Architecture

### v0.5.0 (current — production backends + connector factories)
- `src/model_ledger/backends/sqlite_ledger.py` — SQLiteLedgerBackend (persistent, zero-dep)
- `src/model_ledger/backends/snowflake.py` — SnowflakeLedgerBackend (upstreamed from Block)
- `src/model_ledger/connectors/sql.py` — sql_connector() factory
- `src/model_ledger/connectors/rest.py` — rest_connector() factory
- `src/model_ledger/connectors/github.py` — github_connector() factory
- `src/model_ledger/sdk/ledger.py` — Ledger.from_sqlite(), Ledger.from_snowflake()

### v0.4.x (DataNode graph)
- `src/model_ledger/core/ledger_models.py` — ModelRef, Snapshot, Tag
- `src/model_ledger/sdk/ledger.py` — Ledger SDK (register, record, tag, add, connect, trace, upstream, downstream)
- `src/model_ledger/graph/models.py` — DataNode, DataPort (with schema discriminators)
- `src/model_ledger/graph/protocol.py` — SourceConnector protocol
- `src/model_ledger/backends/ledger_protocol.py` — LedgerBackend protocol
- `src/model_ledger/backends/ledger_memory.py` — InMemory backend
- `src/model_ledger/adapters/sql.py` — SQL parsing (extract_tables, write_tables, model_name_filters)
- `src/model_ledger/adapters/tables.py` — Table-based pipeline discovery
- `src/model_ledger/adapters/cron.py` — Cron expression translation

### v0.3.0 (event-log paradigm)
- `src/model_ledger/scanner/` — Scanner protocol, ModelCandidate, InventoryScanner, ScannerRegistry

### v0.2.0 (legacy — retained for reference)
- `src/model_ledger/core/models.py` — Model, ModelVersion, ComponentNode
- `src/model_ledger/sdk/inventory.py` — Inventory, DraftVersion (context manager API)
- `src/model_ledger/backends/` — InventoryBackend protocol + SQLite/InMemory
- `src/model_ledger/validate/` — SR 11-7, EU AI Act, NIST AI RMF validation profiles
- `src/model_ledger/introspect/` — Plugin-based model introspection
- `src/model_ledger/cli/` — Typer CLI
- `src/model_ledger/export/` — Audit pack export

## Boundary Rules

This is an Apache-2.0 open-source project.

- **NO** Block-specific code, imports, or references
- **NO** dependencies on internal systems (Snowflake auth, snowflake-connector, Prefect, Jira, GCS)
- Organization-specific scanners and backends go in separate packages
- **Rule: "If it needs an internal import, it goes in a separate package. If it's useful to any org, it goes in OSS."**

## Key Patterns

- Event-log paradigm: models are identities (ModelRef), everything else is immutable Snapshots
- Protocol-first: all extension points use `@runtime_checkable` Protocol (no ABCs)
- Tool-shaped SDK: every Ledger method works as an agent tool call
- Append-only audit trail on every mutation
- Plugin discovery via `importlib.metadata.entry_points()`
