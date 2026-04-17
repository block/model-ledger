# Changelog

## Unreleased

- feat: `POST /tag` and `GET /tags/{model_name}` REST endpoints — create, move, and list tags over HTTP
- feat: `tag` and `list_tags` MCP tools — bring the total tool count to 8
- feat: `HttpLedgerBackend.set_tag`, `get_tag`, `list_tags` — replace the previous silent no-op stubs with real implementations that round-trip through the REST API
- feat: `TagInput`, `TagOutput`, `TagListOutput` Pydantic schemas
- fix: `HttpLedgerBackend` caches `model_hash` → `model_name` on successful name lookups so `get_model(model_hash)` resolves correctly for models that were resolved by name (previously returned `None` because `ModelSummary` omits `created_at`)
- feat: `prefect_connector()` — discover deployments from Prefect Cloud with optional tag filtering
- feat: `last_seen` timestamp on `ModelRef` — updated every sync run, even for unchanged models
- feat: dual change timestamps — `change_detected` (UTC, always set) and `change_occurred` (from source, optional via `source_updated_at` metadata)
- feat: `register_group()` — register governed model groups with member linking
- feat: `members()` — list all models that belong to a group
- feat: `groups()` — find all groups a model belongs to
- fix: `rest_connector` preserves URL query params (httpx was stripping them when `params={}`)

## v0.5.0

- feat: `Ledger.from_sqlite(path)` — persistent SQLite backend, zero dependencies
- feat: `Ledger.from_snowflake(conn, schema)` — persistent Snowflake backend
- feat: `sql_connector()` — config-driven SQL-based model discovery
- feat: `rest_connector()` — config-driven REST API model discovery
- feat: `github_connector()` — discover models from config files in GitHub repos
- feat: Connector factories return `SourceConnector` instances for composability

## Unreleased

- fix: deduplicate `ModelNotFoundError` — use canonical class from `core.exceptions`
- test: add coverage for `'value' AS model_name` extraction pattern

## v0.4.8

- fix: exclude volatile timestamps from content hash dedup

## v0.4.7

- perf: cache nodes from `add()`, skip existing edges in `connect()`

## v0.4.6

- perf: skip per-model backend queries when cache is warm, store content hash

## v0.4.5

- perf: content-hash dedup and bulk preload in `add()`

## v0.4.4

- fix: extract `model_name` from SELECT aliases and add pipeline input ports

## v0.4.3

- perf: add name cache to Ledger for zero-cost model lookups

## v0.4.2

- perf: bulk load discovered snapshots in `connect()` — 1 query instead of N

## v0.4.1

- fix: `DataPort` schema matching must require both sides have the key

## v0.4.0

- feat: DataNode graph architecture — `add()`, `connect()`, `trace()`, `upstream()`, `downstream()`
- feat: `DataPort` with schema discriminators for shared table matching
- feat: `SourceConnector` protocol for platform-specific discovery
- feat: SQL adapters — `extract_tables_from_sql`, `extract_write_tables`, `extract_model_name_filters`

## v0.3.0

- feat: event-log paradigm — `ModelRef`, `Snapshot`, `Tag`
- feat: `Ledger` SDK — `register`, `record`, `tag`, `link_dependency`, `dependencies`, `inventory_at`
- feat: `LedgerBackend` protocol with `InMemoryLedgerBackend`
- feat: Scanner architecture — `Scanner` protocol, `ModelCandidate`, `InventoryScanner`
