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

### v0.3.0 (current — event-log paradigm)
- `src/model_ledger/core/ledger_models.py` — ModelRef, Snapshot, Tag
- `src/model_ledger/sdk/ledger.py` — Ledger SDK (register, record, tag, link_dependency, dependencies, inventory_at)
- `src/model_ledger/backends/ledger_protocol.py` — LedgerBackend protocol
- `src/model_ledger/backends/ledger_memory.py` — InMemory backend
- `src/model_ledger/scanner/` — Scanner protocol, ModelCandidate, InventoryScanner orchestrator, ScannerRegistry, DBConnection protocol

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
- **NO** dependencies on internal systems (Snowflake auth, sq-pysnowflake, Prefect, Jira, GCS)
- Organization-specific scanners and backends go in separate packages
- **Rule: "If it needs an internal import, it goes in a separate package. If it's useful to any org, it goes in OSS."**

## Key Patterns

- Event-log paradigm: models are identities (ModelRef), everything else is immutable Snapshots
- Protocol-first: all extension points use `@runtime_checkable` Protocol (no ABCs)
- Tool-shaped SDK: every Ledger method works as an agent tool call
- Append-only audit trail on every mutation
- Plugin discovery via `importlib.metadata.entry_points()`
