# v0.5.0 — OSS Abstraction Layer

**Date:** 2026-04-06
**Status:** Draft
**Author:** Vignesh + Claude

## Problem

model-ledger has clean protocols (SourceConnector, LedgerBackend, Introspector) but only toy implementations. A user who `pip install model-ledger` gets an in-memory backend and no connectors — no path to production. Meanwhile, the Block-internal repo has rich, battle-tested implementations that are trapped behind Block-specific imports.

The framework needs to ship with enough concrete building blocks that any fintech can go from install to production inventory with minimal boilerplate, while keeping the extension points open for custom use cases.

## Design Principles

1. **OSS carries the core logic, org repos are lightweight config** — Block's repo should shrink from ~1,400 lines to ~500 lines after this change.
2. **Schema-agnostic metadata** — the framework never dictates what fields a model has. `Snapshot.payload` and `DataNode.metadata` are `dict[str, Any]`. Every org's models look different.
3. **Factory for the 80%, protocol for the 20%** — config-driven factories handle the common patterns. The SourceConnector protocol is the escape hatch for anything custom.
4. **Batteries included** — `pip install model-ledger` should get you persistence + discovery + graph + tracing with zero infrastructure.

## Architecture

### 1. Smart Ledger Constructor

Class methods for each backend type:

```python
from model_ledger import Ledger

ledger = Ledger()                                              # in-memory (unchanged)
ledger = Ledger.from_sqlite("./inventory.db")                  # SQLite
ledger = Ledger.from_snowflake(connection, schema="DB.SCHEMA") # Snowflake
ledger = Ledger(my_custom_backend)                             # any LedgerBackend (unchanged)
```

Implementation: each class method creates the appropriate backend and passes it to `__init__`.

### 2. Connector Factories

Three factory functions that return `SourceConnector` instances.

#### `sql_connector()` — the workhorse

Covers any "query a database, map rows to models" case. Three levels of sophistication:

**Level 1 — Simple table discovery:**
```python
from model_ledger.connectors import sql_connector

connector = sql_connector(
    name="my_models",
    connection=conn,
    query="SELECT name, owner, status FROM model_registry WHERE active = true",
    name_column="name",
)
# All non-name columns become metadata automatically
```

**Level 2 — Explicit input/output columns:**
```python
connector = sql_connector(
    name="etl_jobs",
    connection=conn,
    query="SELECT name, input_table, output_table, owner FROM jobs",
    name_column="name",
    input_columns=["input_table"],
    output_columns=["output_table"],
)
# Creates DataPorts for dependency linking via connect()
```

**Level 3 — SQL column parsing:**
```python
connector = sql_connector(
    name="alert_rules",
    connection=conn,
    query="SELECT name, queue_label, query_sql FROM alert_algorithms",
    name_column="name",
    sql_column="query_sql",  # parse SQL for input/output tables automatically
    output_port={"column": "queue_label", "fallback": "name", "kind": "alert_queue"},
)
# Uses extract_tables_from_sql() and extract_write_tables() from model_ledger.adapters.sql
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `str` | yes | Platform name for the connector |
| `connection` | `DBConnection` | yes | Any object with `execute()` |
| `query` | `str` | yes | SQL query to run |
| `name_column` | `str` | yes | Column that contains the model name |
| `name_prefix` | `str` | no | Prefix for model names (e.g., `"queue:"`) |
| `input_columns` | `list[str]` | no | Columns containing input table names |
| `output_columns` | `list[str]` | no | Columns containing output table names |
| `sql_column` | `str` | no | Column containing SQL to parse for dependencies |
| `output_port` | `dict` | no | Config for output port: `column`, `fallback`, `kind` |
| `metadata_columns` | `dict[str, str]` | no | Explicit column-to-metadata mapping. If omitted, all unmapped columns become metadata automatically. |

Returns a `SourceConnector` with a `discover()` method.

#### `rest_connector()` — API-based discovery

For model registries, workflow engines, any REST service.

```python
from model_ledger.connectors import rest_connector

connector = rest_connector(
    name="mlflow",
    url="https://mlflow.internal/api/2.0/mlflow/registered-models/list",
    headers={"Authorization": "Bearer ..."},
    items_path="registered_models",
    name_field="name",
    metadata_fields={"version": "latest_versions[0].version"},
    pagination={"type": "token", "token_field": "next_page_token", "param": "page_token"},
)
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `str` | yes | Platform name |
| `url` | `str` | yes | API endpoint URL |
| `headers` | `dict` | no | HTTP headers (auth goes here) |
| `items_path` | `str` | yes | Dot-path to the array of items in JSON response |
| `name_field` | `str` | yes | Field containing the model name |
| `input_fields` | `list[str]` | no | Dot-paths to input identifiers |
| `output_fields` | `list[str]` | no | Dot-paths to output identifiers |
| `metadata_fields` | `dict[str, str]` | no | Explicit field mapping. If omitted, all unmapped fields become metadata. |
| `pagination` | `dict` | no | Pagination config: `type` (token/offset), `token_field`, `param` |

#### `github_connector()` — pipeline-as-code discovery

For discovering models defined in config files in GitHub repos.

```python
from model_ledger.connectors import github_connector

connector = github_connector(
    name="prefect_pipelines",
    repos=["myorg/ml-pipelines"],
    token="ghp_...",
    project_path="projects",
    config_file="deploy.yaml",
    parser=my_yaml_parser,  # function(project_name, file_content) -> DataNode | None
)
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `str` | yes | Platform name |
| `repos` | `list[str]` | yes | GitHub repos (org/repo format) |
| `token` | `str` | no | GitHub personal access token |
| `project_path` | `str` | yes | Directory containing project subdirectories |
| `config_file` | `str` | yes | Filename to read in each project |
| `parser` | `Callable` | yes | `(project_name: str, content: str) -> DataNode | None` |

The factory handles GitHub API calls, directory listing, file reading, and base64 decoding. The user provides a parser function with the org-specific logic.

#### Existing: `discover_pipelines_from_table()`

Already in `model_ledger.adapters.tables`. Stays as-is. This handles the specific pattern of "a shared table where each distinct name is a pipeline."

### 3. Backends

#### SQLiteLedgerBackend — batteries included

New file: `model_ledger/backends/sqlite_ledger.py`

- Zero dependencies (sqlite3 is stdlib)
- Same schema as Snowflake: MODELS, SNAPSHOTS, TAGS tables
- Payload stored as JSON TEXT
- WAL mode for concurrent reads
- Implements full `LedgerBackend` protocol + `list_all_snapshots()` + `list_snapshot_content_hashes()`

```python
ledger = Ledger.from_sqlite("./inventory.db")
# Creates file, creates tables, ready to use
```

#### SnowflakeLedgerBackend — upstreamed from Block

Move from `forge-internal-mrm/projects/model_ledger_block/backends/snowflake.py` to `model-ledger/src/model_ledger/backends/snowflake.py`.

Changes from Block version:
- Remove `snowflake-connector` auto-connection in `__init__`. Accept any connection object with `execute()` method or a raw `snowflake.connector` connection.
- Optional dependency: `pip install model-ledger[snowflake]` adds `snowflake-connector-python` and `pandas`.

Block's repo then imports from OSS and passes its own auth:
```python
from model_ledger.backends.snowflake import SnowflakeLedgerBackend
from pysnowflake.session import Session

session = Session()
session.open()
backend = SnowflakeLedgerBackend(connection=session, schema="ORG_SCHEMA.MODEL_LEDGER")
```

### 4. What Block's Repo Becomes

**Before (~1,400 lines):**
```
model_ledger_block/
  backends/snowflake.py           406 lines
  connectors/ (8 files)           660 lines
  adapters/snowflake.py           240 lines
  introspectors/heuristic.py      126 lines
```

**After (~500 lines):**
```
model_ledger_block/
  connectors.py                   ~120 lines  (factory configs)
  adapters/snowflake.py            240 lines  (Block metadata queries)
  introspectors/heuristic.py       126 lines  (Block deep introspection)
  connection.py                    ~40 lines  (Block Snowflake auth)
```

Components that move:
- `backends/snowflake.py` → OSS `model_ledger/backends/snowflake.py`
- 7 connector classes → replaced by `sql_connector()`, `rest_connector()`, `github_connector()` factory calls
- `RulesEngineConnector` → stays custom (multi-table join too complex for a factory)

## File Map (OSS changes)

```
src/model_ledger/
  sdk/ledger.py                    # Modify: add from_sqlite(), from_snowflake() class methods
  backends/
    sqlite_ledger.py               # Create: SQLiteLedgerBackend
    snowflake.py                   # Create: SnowflakeLedgerBackend (upstream from Block)
  connectors/
    __init__.py                    # Create: export sql_connector, rest_connector, github_connector
    sql.py                         # Create: sql_connector() factory
    rest.py                        # Create: rest_connector() factory
    github.py                      # Create: github_connector() factory
  __init__.py                      # Modify: export new factory functions
```

## Testing Strategy

Each component gets its own test file:

- `tests/test_backends/test_sqlite_ledger.py` — full CRUD, persistence across reopens, concurrent reads
- `tests/test_backends/test_snowflake_ledger.py` — existing Block tests, adapted for OSS (mock session)
- `tests/test_connectors/test_sql_connector.py` — all three levels (simple, columns, SQL parsing)
- `tests/test_connectors/test_rest_connector.py` — mock HTTP responses, pagination, field mapping
- `tests/test_connectors/test_github_connector.py` — mock GitHub API, parser function, error handling

## Dependencies

- Core: no new dependencies (SQLite is stdlib)
- `model-ledger[snowflake]`: adds `snowflake-connector-python`, `pandas`
- `model-ledger[rest]`: adds `httpx` (for rest_connector)
- `model-ledger[github]`: adds `httpx` (for github_connector)
- `model-ledger[all]`: all extras

## Out of Scope

- PostgreSQL/BigQuery backends (future)
- GitLab/Bitbucket connectors (future, use SourceConnector protocol)
- Base classes for connectors (factories are sufficient)
- UI/reporting layer (separate concern)
- Business grouping concept (deferred per Case_Mgmt connector design)

## Migration Path

1. Ship v0.5.0 of OSS with all new components
2. Update Block's forge-internal-mrm to import backends from OSS
3. Refactor Block connectors to use factory functions
4. Delete Block's `backends/` directory
5. Simplify Block's `connectors/` to a single config file
