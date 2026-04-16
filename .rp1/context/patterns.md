# Implementation Patterns

**Project**: model-ledger
**Last Updated**: 2026-04-16

## Naming & Organization

**Files**: snake_case throughout: `ledger_models.py`, `sqlite_ledger.py`, `audit_pack.py`. Modules named by concern (`protocol.py`, `registry.py`, `models.py` repeat across packages).
**Functions**: Verb prefixes for actions (`register`, `record`, `trace`, `discover`). Private helpers prefixed with `_` (`_resolve_model`, `_ensure_tables`, `_to_node`). Factory functions use noun form: `sql_connector()`, `rest_connector()`.
**Imports**: Absolute imports everywhere (`from model_ledger.core.ledger_models import ...`). Lazy imports inside methods for heavy/optional deps. `__future__` annotations in every file.

Evidence: `src/model_ledger/sdk/ledger.py`, `src/model_ledger/connectors/sql.py`, `src/model_ledger/backends/sqlite_ledger.py`

## Type & Data Modeling

**Data Representation**: Pydantic `BaseModel` for serializable domain objects (ModelRef, Snapshot, Tag, all tool schemas). `@dataclass` for internal value objects (DataNode, Violation). Plain classes with `__slots__` for lightweight graph primitives (DataPort).
**Type Strictness**: Gradual typing with PEP 604 unions (`str | None`). Strict Pydantic models at API boundaries. Internal code uses `dict[str, Any]` for schemaless payloads. `model_validator(mode='after')` for computed fields like content-addressed hashes.
**Immutability**: `frozen=True` on value objects (Violation). Snapshots are conceptually immutable (append-only). `frozenset` for constant sets (`_INTERNAL_EVENTS`).

Evidence: `src/model_ledger/core/ledger_models.py:27-76`, `src/model_ledger/graph/models.py:8-15`, `src/model_ledger/validate/engine.py:11-16`

## Error Handling

**Strategy**: Custom exception hierarchy rooted at `ModelInventoryError`. Each exception provides actionable messages with suggestions (e.g., `ImmutableVersionError` tells you to create a new version).
**Propagation**: Exceptions raised at SDK layer, caught at boundary (REST converts to `HTTPException`, tools let them propagate). Silent swallowing only for optional features (entry_points discovery, demo data loading).
**Common Types**: `ModelNotFoundError`, `VersionNotFoundError`, `ImmutableVersionError`, `ValidationError`, `StorageError`, `NoIntrospectorError`

Evidence: `src/model_ledger/core/exceptions.py:1-51`, `src/model_ledger/rest/app.py:84-87`

## Validation & Boundaries

**Location**: API boundary via Pydantic schemas (RecordInput, QueryInput, etc). Tools accept typed Pydantic models — MCP/REST wrappers construct them from primitives.
**Method**: Pydantic `BaseModel` with `Field` defaults. `Literal` types for constrained strings (`direction: Literal['upstream', 'downstream', 'both']`). No manual validation code — Pydantic handles construction-time validation.

Evidence: `src/model_ledger/tools/schemas.py:61-79`, `src/model_ledger/core/ledger_models.py:41-45`

## Observability

**Logging**: None detected — no logging framework imported.
**Metrics**: None detected.
**Tracing**: Content-addressed hashing provides built-in audit trail. Every mutation produces an immutable Snapshot with actor, timestamp, and source. `snapshot_hash` and `model_hash` serve as correlation IDs.

Evidence: `src/model_ledger/core/ledger_models.py:17-24`

## Testing Idioms

**Organization**: `tests/` mirrors `src/` structure: `test_sdk/`, `test_tools/`, `test_backends/`, etc. Each test module maps 1:1 to a source module.
**Fixtures**: pytest fixtures creating `Ledger(backend=InMemoryLedgerBackend())` — every test gets a fresh in-memory backend. No shared state.
**Levels**: Unit-dominant against InMemoryLedgerBackend. Backend tests (SQLite, JSON, Snowflake) are integration tests. Test classes group by behavior (TestRegister, TestRecord, TestTag).

Evidence: `tests/test_sdk/test_ledger.py`, `tests/test_tools/test_record.py`

## I/O & Integration

**Database**: Backend abstraction via `@runtime_checkable Protocol` (LedgerBackend). Five implementations: InMemory (tests), SQLite (WAL), Snowflake (production), JsonFile (git-friendly), HTTP (pass-through). All implement identical method signatures. SQLite uses `_row_to_model`/`_model_to_row` converter pattern.
**HTTP Clients**: Connector factory pattern: `sql_connector()`, `rest_connector()`, etc. Config-driven — factory accepts keyword args for connection, query, column mappings. `HttpLedgerBackend` wraps httpx for remote access.

Evidence: `src/model_ledger/backends/ledger_protocol.py:1-32`, `src/model_ledger/connectors/sql.py:14-78`, `src/model_ledger/graph/protocol.py:1-9`

## Extension Mechanisms

**Plugin Pattern**: Three-layer system: (1) `@runtime_checkable Protocol` defines interface (Scanner, Introspector, SourceConnector, LedgerBackend). (2) Registry class with lazy `_ensure_discovered()` loads entry points via `importlib.metadata.entry_points(group=...)`. (3) Module-level `get_registry()`/`reset_registry()` singletons.
**Profile Registration**: Validation profiles use `@register_profile` decorator into a module-level dict.
**Entry Point Groups**: `model_ledger.scanners`, `model_ledger.introspectors`

Evidence: `src/model_ledger/introspect/registry.py:10-58`, `src/model_ledger/scanner/registry.py:1-59`, `src/model_ledger/validate/engine.py:53-74`
