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

### v0.7.2+ (current — agent protocol + connectors + change tracking)
- `src/model_ledger/connectors/sql.py` — sql_connector() factory
- `src/model_ledger/connectors/rest.py` — rest_connector() factory
- `src/model_ledger/connectors/github.py` — github_connector() factory
- `src/model_ledger/connectors/prefect.py` — prefect_connector() factory (Prefect Cloud API)
- `src/model_ledger/backends/sqlite_ledger.py` — SQLiteLedgerBackend (persistent, zero-dep)
- `src/model_ledger/backends/snowflake.py` — SnowflakeLedgerBackend (production)
- `src/model_ledger/backends/http.py` — HttpLedgerBackend (MCP → REST API pass-through)
- `src/model_ledger/backends/json_files.py` — JsonFileLedgerBackend (git-friendly)
- `src/model_ledger/sdk/ledger.py` — Ledger SDK with last_seen, change_detected/change_occurred
- `src/model_ledger/tools/` — 6 agent tool functions (record, query, investigate, trace, changelog, discover)
- `src/model_ledger/mcp/server.py` — MCP server (FastMCP, 6 tools + 3 resources)
- `src/model_ledger/rest/app.py` — REST API (FastAPI, create_app() factory)

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

This is an Apache-2.0 open-source project. All code must be generic and useful to any organization. Organization-specific connectors, auth, and backends go in separate packages.

**Examples in code, tests, and docstrings must be generic** — use names like "Credit Scorecard", "feature_pipeline", "risk-team", "scoring_model". Never use organization-specific system names, team names, queue names, or person names in OSS code.

## Extension Points

The project is designed to be wrapped by downstream packages that add organization-specific connectors, auth, envelope schemas, or REST wrappers. Changes that affect the public surface require coordinated updates in those packages:

- `LedgerBackend` protocol (`backends/ledger_protocol.py`) — adding a method requires implementing it in every backend and any third-party backend.
- `Snapshot` / `Tag` / `ModelRef` models (`core/ledger_models.py`) — schema changes propagate through all serialization paths.
- REST API schemas (`tools/schemas.py`) and endpoints (`rest/app.py`) — version the API surface when breaking changes land.
- MCP tool signatures (`mcp/server.py`) — downstream agents pin tool names and argument shapes.

## Known Gaps

- `Ledger.record()` accepts arbitrary `payload: dict` — envelope validation is the caller's responsibility. Downstream packages can layer schema validation on top.
- `HttpLedgerBackend.list_models()` can't reconstruct `model_hash` from `/query` responses because `ModelSummary` omits `created_at`. `get_model(model_hash)` falls back to a lazy `name`-to-`hash` cache populated on successful name lookups.

## Key Patterns

- Event-log paradigm: models are identities (ModelRef), everything else is immutable Snapshots
- Protocol-first: all extension points use `@runtime_checkable` Protocol (no ABCs)
- Tool-shaped SDK: every Ledger method works as an agent tool call
- Append-only audit trail on every mutation
- Plugin discovery via `importlib.metadata.entry_points()`

<!-- rp1:start -->
## rp1 Knowledge Base

**Use Progressive Disclosure Pattern**

Location: `.rp1/context/`

Files:
- index.md (always load first)
- architecture.md
- modules.md
- patterns.md
- concept_map.md

Loading rules:
1. Always read index.md first.
2. Then load based on task type:
   - Code review: patterns.md
   - Bug investigation: architecture.md, modules.md
   - Feature work: modules.md, patterns.md
   - Strategic or system-wide analysis: all files
<!-- rp1:end -->
