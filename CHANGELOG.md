# Changelog

## Unreleased

- feat: `register_group()` — register governed model groups with member linking
- feat: `members()` — list all models that belong to a group
- feat: `groups()` — find all groups a model belongs to

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
