# Changelog

## v0.7.13 (Unreleased)

Compatibility notes: this is a patch release — no public surface is removed. The `excel` extra is deprecated (unused since the scanner removal) and the strict full-protocol backend validation considered for this release was softened to a core-method duck check; both removals/tightenings are deferred to 0.8.0.

- fix: `Ledger(HttpLedgerBackend(url))` no longer corrupts the remote ledger. `append_snapshot` sends the real model name instead of `""` (which auto-registered a phantom empty-name model and attached every recorded event to it) and raises `ModelNotFoundError` for unresolvable hashes; registration logs exactly one `registered` event instead of double-firing (re-registration is now idempotent); `get_snapshot()` serves appended snapshots from a client-side cache and reconstructs older ones from `GET /changelog` instead of always returning `None` (hashes rebuilt from the changelog match server-minted identities; hashes of snapshots created client-side by `Ledger.record()` are process-local and resolve via the cache only). Defense in depth: `RecordInput.model_name` requires `min_length=1` and rejects whitespace-only names, so old clients that POST an empty model name get a 422 instead of silently corrupting the inventory. A new integration suite drives the SDK against the real `create_app()` handlers (not mocks).
- fix: `HttpLedgerBackend.list_snapshots` fetches the model's full history. It called `GET /changelog` without a `since` bound, inheriting the changelog tool's 7-day default — so for any model whose events were older than a week, `get_snapshot` reconstruction returned `None`, `latest_snapshot` returned `None` (making `Ledger.tag` raise on healthy old models), re-registration lost its idempotency check, and the `platform` query filter returned zero results. It now passes an explicit all-time `since`. `list_models` also caches name mappings for the hashes it hands out, so they stay resolvable within the process (`batch_platforms`, and with it the platform filter, works from a fresh client).
- fix: registration over `HttpLedgerBackend` carries the caller's payload, tier, and actor to the server. `Ledger.register()` dispatches to an optional backend `register_model` hook (implemented by the HTTP backend as a single `POST /record`); previously the payload was silently dropped, and every remote registration landed as `tier="unclassified"`, `actor="user"`. `RecordInput` gains an optional `tier` field (additive).
- fix: the `query` tool's `platform` filter is actually applied. It was advertised in `QueryInput` and the REST/MCP schemas but never read — any platform value returned the full inventory. Platform is resolved from snapshot data in one batched `batch_platforms` dispatch and filtered/paginated in the tool; a schema-vs-implementation parity test now guards every `QueryInput` filter field.
- fix: the introspector registry dispatches XGBoost sklearn-API models to the xgboost introspector. `SklearnIntrospector.can_handle` now rejects estimators from wrapper frameworks with dedicated introspectors (xgboost, lightgbm) instead of claiming them via `BaseEstimator`, making dispatch independent of entry-point ordering.
- fix: SQL lineage extraction accepts unqualified (bare) table names — `INSERT INTO feature_store SELECT * FROM raw_events` previously parsed to zero reads and zero writes, silently producing no lineage. CTE names (`WITH ... AS`, including nested and `RECURSIVE` forms) and `DELETE FROM` targets are excluded from read tables, so dbt-style SQL does not produce phantom lineage inputs; a keyword blocklist keeps subqueries, table functions, and row sources out of the results (a bare table genuinely named a filtered keyword must be schema-qualified to extract); `INSERT OVERWRITE` is recognized, including the Hive/Spark `INSERT OVERWRITE TABLE t` form.
- fix: the `trace` tool reports real BFS depth instead of fabricating it from list position. `depth` was computed from each node's index in the flat transitive list, so any model with N transitive upstreams rendered as an N-deep linear chain (a rich 8-level fan-out graph showed as "43 nodes at depths 1–43"); downstream had the same bug. Traversal is now a breadth-first walk that records each node's actual level (shortest edge distance, one entry per node at its minimum depth) and terminates at `input.depth` — bounded queries now do bounded work instead of filtering after a full traversal. `total_nodes` counts distinct models (a node reachable both upstream and downstream with `direction="both"` was counted twice).
- fix: `strip_template_vars` strips spaced template variables like `{{ ds }}`; its docstring example now shows the actual output.
- fix: `sql_connector` raises a clear `TypeError` naming the dict-row requirement when the connection yields tuple rows, instead of an opaque indexing error; name-addressable rows without the full dict API (e.g. `sqlite3.Row`, which has `keys()` but no `.get()`) are accepted. The connectors guide documents the requirement with a `row_factory = sqlite3.Row` example.
- fix: `create_app()` / `create_server()` validate the backend at construction and raise a clear `TypeError` (with hints for the common Ledger-instead-of-backend and path-string mistakes) instead of failing deep inside the first request with `AttributeError`. Validation is a core-method duck check, not full-protocol `isinstance`, so partial custom backends that worked on 0.7.12 keep working.
- fix(cli): `export --output` help text now says "Output file path" (the command writes a single file, not a directory) and the success message prints the real artifact path. The default output filename is unchanged (`audit_pack`).
- feat: `Ledger.register()` accepts an optional `payload` dict merged into the registration event's payload (caller keys win) — used by the record tool so the single `registered` event still carries the caller's payload, over local and HTTP backends alike. `Ledger` also gains a public read-only `backend` property.
- chore: deprecate the `excel` extra — nothing has imported openpyxl since the scanner module was removed post-v0.7.7. The extra is kept so `model-ledger[excel]` pins keep resolving within 0.7.x; removal planned for 0.8.0.
- test: pandas-dependent tests skip instead of hard-failing when pandas is absent alongside the ML introspection libs.
- test: introspector dispatch tests execute in every environment via stub sklearn/xgboost/lightgbm modules (the real-library variants still run where the ML extras are installed) — previously all dispatch tests skipped in CI.

## v0.7.12

- fix: escape backslashes in single-quoted SQL literals — JSON payloads containing escaped double quotes (`\"`) or backslashes reached `PARSE_JSON` mangled on the SQL fallback write path, which re-introduced the poisoned-buffer failure (INSERT fails, buffer never clears, every subsequent flush-before-read 500s) on common data. Also from the post-merge review of #33/#34: privilege denials short-circuit quietly again instead of warning per flush, unexpected pandas-path failures log with `exc_info`, and the failure-path staging-table DROP is gone. (#35)

## v0.7.11

- fix: the pandas bulk write path falls back to the DDL-free SQL path on ANY failure, not just privilege errors. Observed in production: `write_pandas` failing inside the file-transfer agent (not a privilege error) propagated, left the snapshot buffer poisoned, and 500'd every subsequent read on the process. Any pandas-path failure now logs a warning, best-effort drops the staging table, clears cleanly, and falls back. (#34)

## v0.7.10

- fix: the SQL fallback snapshot flush carries PAYLOAD and TAGS — the DDL-free path taken by least-privilege deployments previously inserted only the 7 scalar columns, silently persisting every snapshot with NULL payload and tags. (#33)
- ci: publish to the official MCP Registry via GitHub OIDC on each release. (#32)

## v0.7.9

- chore: publish to the official MCP Registry as `io.github.block/model-ledger` — adds `server.json` and the PyPI ownership marker in the README (#31)

## v0.7.8

- docs: README credibility pass — CI/downloads badges, production-scale benchmark callout, architecture diagram, maintainer credit; "For organizations" now states that the SR 11-7/SR 26-2, EU AI Act Annex IV, and NIST AI RMF validation profiles ship in the OSS core (#29)
- docs: quickstart and all Ledger examples persist to `./ledger.db` (the previous `./inventory.db` name collided with the CLI's legacy Inventory-format default and crashed `model-ledger list`); quickstart `history()` example now shows (and CI-asserts) newest-first ordering (#29)
- fix(cli): bare installs get a one-line install hint from `model-ledger --help` instead of a `ModuleNotFoundError` traceback (typer/rich live in the `[cli]` extra) (#29)
- fix(cli): inventory commands detect a Ledger event-log database and exit with guidance instead of an sqlite traceback (#29)
- fix(cli): `model-ledger validate` with an unknown profile exits with the available profile names instead of a `ValueError` traceback (#29)
- refactor!: remove the `scanner` module (`Scanner`, `InventoryScanner`, `ModelCandidate`, `ScanReport`), deprecated since v0.4.0 — use `SourceConnector` + `DataNode` + `Ledger.add()/connect()` (#29)
- chore: PyPI metadata — Development Status classifier to Beta; add `mcp`, `model-context-protocol`, `ai-governance`, `eu-ai-act`, `nist-ai-rmf`, `sr-26-2` keywords (#29)
- docs: add SECURITY.md (private vulnerability reporting) (#29)
- chore: stale-reference sweep — MCP tool count 6→8 in docstrings and CLAUDE.md, `v0.3.0` markers out of SDK docstrings, "Task 11" comments out of rest/app.py; fold two stale Unreleased changelog blocks into the releases that shipped them (v0.7.3, v0.4.8) (#29)

## v0.7.7

- feat: `SnowflakeLedgerBackend` accepts a `connection_factory` and self-heals on auth-token expiry (Snowflake errno 390114) — on a detected expiry it obtains a fresh connection, swaps it in, and retries the same statement exactly once. Composes with `client_session_keep_alive` heartbeats as the backstop for residual expiries. Backward compatible: with only `connection`, behavior is unchanged. (#24)
- perf: batch edge resolution in the investigate/graph hot path — `get_models` batch lookup replaces per-edge round trips. (#25)

## v0.7.6

- fix: `SnowflakeLedgerBackend` skips schema DDL (`CREATE SCHEMA`/`CREATE TABLE`/`ALTER`) on write-mode init when the schema + tables already exist (probed via `SELECT`-only `INFORMATION_SCHEMA`). Snowflake checks the `CREATE` privilege even for `IF NOT EXISTS`, so this lets a least-privilege deployment with only `INSERT/UPDATE/SELECT` write without holding schema-ownership-level DDL grants. Fresh deployments still auto-provision; introspection failure falls back to the `CREATE` path. (#26)
- fix: the bulk write path (`_flush_models_pandas`/`_flush_snapshots_pandas`) falls back to the DDL-free SQL `MERGE`/`INSERT` path when the role can't create the temporary staging table (SQLSTATE 42501), instead of failing the write. The entire write path now requires only `INSERT/UPDATE/SELECT`. (#26)
- fix: connector-discovered `status` propagates to the model row on `Ledger.add()` (`metadata['status']` contract, `ModelStatus` enum validation, dedup-skip self-correction). (#23)

## v0.7.4

- perf: `SnowflakeLedgerBackend.composite_summary()` computes the full composite inventory in ONE self-contained SQL statement over MODELS + SNAPSHOTS (CTE-based event replay), replacing the previous delegation to an externally-managed `V_COMPOSITES` view. Removes the undocumented requirement that deployments create that view, and replicates the SDK fallback semantics exactly (membership baseline from `member_of` dependency links + `member_added`/`member_removed` replay with latest-op-wins; distinct-id open-observation set semantics). Measured against a production-scale ledger (28.8k models / 212k snapshots): 92.6s sequential fallback → sub-second warm (~0.3-0.6s).

## v0.7.3

- Add `metadata: dict` field to `ModelRef`. Thread through `register()` and `register_group()`. Replaces the unintended per-link broadcast of `register_group(metadata=...)` to member links; metadata now lives on the composite ModelRef itself. Backward compatible: existing data loads with `metadata={}`.
- Add optional `model_types` parameter to `composite_summary()` so callers can include custom composite-shaped types (e.g., `ml_model`, `heuristic`) beyond the default `"composite"`. Backward compatible.
- feat: `RecordOutput.model_hash` — the `/record` response now carries the server's canonical model hash so HTTP clients can reconcile their local `ModelRef` with authoritative server state
- fix: `HttpLedgerBackend.save_model` adopts the server's canonical hash (reassigns `model.model_hash` on the incoming `ModelRef` and caches only the server hash) so follow-up hash-based flows like `Ledger.tag()` round-trip correctly even from a fresh backend instance
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

## v0.4.8

- fix: exclude volatile timestamps from content hash dedup
- fix: deduplicate `ModelNotFoundError` — use canonical class from `core.exceptions`
- test: add coverage for `'value' AS model_name` extraction pattern

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
