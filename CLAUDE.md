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

- `src/model_ledger/core/` — Pydantic data models, enums, exceptions
- `src/model_ledger/sdk/` — Inventory, DraftVersion (context manager API)
- `src/model_ledger/backends/` — InventoryBackend protocol + SQLite/InMemory implementations
- `src/model_ledger/validate/` — SR 11-7 validation engine with profile system
- `src/model_ledger/introspect/` — Plugin-based model introspection (v0.2.0)
- `src/model_ledger/cli/` — Typer CLI (v0.2.0)
- `src/model_ledger/export/` — Audit pack export (v0.2.0)

## Boundary Rules

This is an Apache-2.0 open-source project.

- **NO** Block-specific code, imports, or references
- **NO** dependencies on internal systems (Snowflake auth, sq-pysnowflake, Prefect, Jira, GCS)
- Block-specific introspectors and backends go in `forge-block-mrm/projects/model_ledger_block`
- **Rule: "If it needs a Block import, it goes in forge. If it's useful to any org, it goes in OSS."**

## Key Patterns

- Version-centric fluent API: `with inv.new_version("model") as v:`
- Append-only audit trail on every mutation
- Backend-level immutability for published versions
- Case-insensitive enums for developer convenience
- Plugin discovery via `importlib.metadata.entry_points()`
