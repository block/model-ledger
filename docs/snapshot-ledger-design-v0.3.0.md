# model-ledger v0.3.0 — Snapshot Ledger Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the rigid schema + semver versioning with an event-log paradigm: content-addressed snapshots, schema-free payloads, and a watcher protocol for self-sustaining inventories. Design for AI agents as primary consumers.

**Architecture:** A document-store model where models are identities (8 fields) and everything else is timestamped immutable snapshots with arbitrary payloads. The SDK exposes tool-shaped functions suitable for both human developers and AI agents. An MCP server wraps the SDK for direct agent access.

**Tech Stack:** Python 3.10+, Pydantic v2, hashlib (SHA-256), Typer CLI, FastMCP server, SQLite (default backend)

---

## 1. Design Principles

1. **The inventory is an event log, not a table.** Never mutate — always append.
2. **Schema is discovered, not declared.** Introspectors observe and record. The ledger stores what was found.
3. **Agents are first-class consumers.** Every SDK function maps to a tool call with clear JSON input/output.
4. **The stable core is tiny.** Identity + snapshot + tag. Everything else is a plugin or a view.
5. **Future-proof by being opinionless about content.** New model types, new regulations, new deployment patterns — none require core changes. They're just new payloads and new views.

## 2. Core Data Model

### 2.1 ModelRef — Regulatory Identity

The minimum a regulator needs to know about a model's existence.

```python
class ModelRef(BaseModel):
    model_hash: str         # sha256(name + owner + created_at) — stable, immutable
    name: str               # human-readable label (can be renamed)
    owner: str              # accountable person/team [SR 11-7, OCC]
    model_type: str         # free-form: "ml_model", "heuristic", "vendor", "llm", "agent"
    tier: str               # "high" | "medium" | "low" [OCC, PRA, OSFI]
    purpose: str            # what it does, in plain language [SR 11-7, EU AI Act]
    status: str             # "active" | "development" | "deprecated" | "retired"
    created_at: datetime    # when first registered
```

**Design decisions:**
- `model_hash` is the primary key, not `name`. Names are mutable labels. Hashes are stable identifiers that survive renames.
- `model_type` and `tier` are free-form strings, not enums. A new model type shouldn't require a library update. Compliance profiles may validate allowed values (e.g., SR 11-7 profile checks `tier in {"high", "medium", "low"}`), but the core accepts any string.
- `status` is mutable. Changes produce snapshots with `event_type="status_changed"`.
- No `version` field. Versions are tags on snapshots.

### 2.2 Snapshot — Immutable Observation

A timestamped, content-addressed record of something observed or done to a model.

```python
class Snapshot(BaseModel):
    snapshot_hash: str          # sha256(model_hash + timestamp + json(payload))
    model_hash: str             # which model
    parent_hash: str | None     # explicit lineage (user declares, not auto-chained)
    timestamp: datetime         # when this observation was recorded
    actor: str                  # who/what: "vignesh", "ml_platform-watcher", "ci-pipeline"
    event_type: str             # free-form: "registered", "introspected", "validated", etc.
    source: str | None          # where the data came from: "ml_platform", "etl_engine", "manual"
    payload: dict[str, Any]     # schema-free — the actual observation
    tags: dict[str, str]        # labels: {"version": "v3", "env": "production"}
```

**Design decisions:**
- `snapshot_hash` provides content-addressability. Two identical observations at different times produce different hashes (timestamp is included).
- `parent_hash` is user-declared, not automatic. Not every snapshot is a "successor" — a validation snapshot doesn't supersede an introspection snapshot. The user explicitly says "this retrained model descends from that one."
- `event_type` is free-form, not an enum. Common values: `registered`, `introspected`, `validated`, `deployed`, `threshold_changed`, `docs_updated`, `status_changed`, `identity_updated`. But users can invent new ones.
- `payload` has no schema enforcement at the core level. Introspectors MAY ship optional JSON Schema or Pydantic models for validation. The SDK validates if a schema is registered, accepts any dict if not.
- `tags` are key-value pairs on the snapshot itself (immutable with the snapshot). For mutable pointers, use `Tag`.

### 2.3 Tag — Named Pointer

A mutable pointer from a name to a snapshot. Like git branches and tags.

```python
class Tag(BaseModel):
    name: str               # "v3", "active", "last-validated", "prod"
    model_hash: str          # which model
    snapshot_hash: str       # which snapshot this points to
    updated_at: datetime     # when the pointer was last moved
```

**Design decisions:**
- Tags are mutable. `ledger.tag(model, "active")` moves the "active" pointer to the latest snapshot.
- Tag mutations are recorded as snapshots with `event_type="tag_updated"` and `payload={"tag": "active", "from_hash": old, "to_hash": new}`. This means tag history is queryable.
- Convention: `"active"` = currently in production. `"v3"` = human version label. `"last-validated"` = most recent validation. These are conventions, not enforced.

## 3. SDK — Tool-Shaped API

The SDK is named `Ledger` (not `Inventory`). Every public method is designed to work as an agent tool call: clear inputs, JSON-serializable outputs, no side effects beyond the ledger itself.

### 3.1 Core Operations

```python
from model_ledger import Ledger

ledger = Ledger()  # SQLite default, or pass backend=

# --- Registration ---
model = ledger.register(
    name="arr-v3",
    owner="compliance-ml",
    tier="high",
    model_type="ml_model",
    purpose="Transaction monitoring alert risk rating for Cash App fiat P2P",
)

# --- Recording observations ---
snapshot = ledger.record(
    model,                          # ModelRef or model_hash string
    event="introspected",
    source="ml_platform",
    payload={
        "algorithm": "XGBoost",
        "features": [...],         # whatever the introspector found
        "backend": "triton",
        "config": {...},
    },
    actor="ml_platform-introspector",
)

# --- Tagging ---
ledger.tag(model, "v3")
ledger.tag(model, "active")

# --- Querying ---
model = ledger.get("arr-v3")                  # by name
model = ledger.get("sha256:abc123...")         # by hash
models = ledger.list(tier="high", status="active")
models = ledger.search(payload_contains="XGBoost")  # search inside payloads

# --- History ---
snapshots = ledger.history(model)              # all snapshots, newest first
snapshots = ledger.history(model, event="introspected")  # filtered
latest = ledger.latest(model)                  # most recent snapshot
latest = ledger.latest(model, tag="active")    # snapshot pointed to by tag

# --- Diffing ---
diff = ledger.diff(snapshot_a, snapshot_b)     # structural payload diff

# --- Validation ---
result = ledger.validate(model, profile="sr_11_7")  # validates latest snapshot
```

### 3.2 Design Principles for the API

- **Every function returns Pydantic models or dicts.** No opaque objects. Everything is JSON-serializable.
- **Model references accept name or hash.** `ledger.get("arr-v3")` and `ledger.get("sha256:abc123")` both work.
- **No context managers for writes.** The `with inv.new_version() as v:` pattern implied mutability. `ledger.record()` is a single atomic append. If you have multiple observations, make multiple `record()` calls.
- **No publish/draft lifecycle.** Snapshots are always immutable. "This is the production version" is expressed via `ledger.tag(model, "active")`, not a status change.
- **Errors are clear and actionable.** `ModelNotFoundError("arr-v3 not found. Did you mean: arr-v2, acrr-v2?")`.

## 4. Protocols — Extension Points

### 4.1 Introspector (unchanged conceptually)

```python
class Introspector(Protocol):
    name: str
    def can_handle(self, obj: Any) -> bool: ...
    def introspect(self, obj: Any) -> dict[str, Any]: ...
```

Returns a dict (the payload). No intermediate `IntrospectionResult` class required, though one can be used internally and `.model_dump()`'d.

Discovery: `importlib.metadata.entry_points(group="model_ledger.introspectors")`

### 4.2 Watcher (new)

```python
class Watcher(Protocol):
    name: str
    def poll(self, model: ModelRef, last_snapshot: Snapshot | None) -> dict | None: ...
```

Returns a payload dict if something changed, `None` if not. The SDK handles creating the snapshot.

Discovery: `importlib.metadata.entry_points(group="model_ledger.watchers")`

OSS ships: `GitWatcher` (polls a git repo for changes to files matching a pattern).
Block adds: `ETL_EngineWatcher`, `AlertingWatcher`, `ML_PlatformWatcher`.

### 4.3 Backend

```python
class LedgerBackend(Protocol):
    # Models
    def save_model(self, model: ModelRef) -> None: ...
    def get_model(self, model_hash: str) -> ModelRef | None: ...
    def get_model_by_name(self, name: str) -> ModelRef | None: ...
    def list_models(self, **filters) -> list[ModelRef]: ...
    def update_model(self, model: ModelRef) -> None: ...

    # Snapshots (append-only)
    def append_snapshot(self, snapshot: Snapshot) -> None: ...
    def get_snapshot(self, snapshot_hash: str) -> Snapshot | None: ...
    def list_snapshots(self, model_hash: str, **filters) -> list[Snapshot]: ...
    def latest_snapshot(self, model_hash: str, tag: str | None = None) -> Snapshot | None: ...
    def search_payloads(self, query: str) -> list[Snapshot]: ...

    # Tags
    def set_tag(self, tag: Tag) -> None: ...
    def get_tag(self, model_hash: str, name: str) -> Tag | None: ...
    def list_tags(self, model_hash: str) -> list[Tag]: ...
```

OSS ships: `SQLiteBackend` (default), `InMemoryBackend` (testing).
`search_payloads` uses SQLite JSON1 extension for payload queries.

### 4.4 Validator

```python
class ComplianceProfile(Protocol):
    name: str
    def validate(self, model: ModelRef, snapshot: Snapshot) -> ValidationResult: ...
```

Validators check concepts, not field names. "Does the model document its inputs?" checks for `payload.get("features") or payload.get("data_sources") or payload.get("sql")` — adapts to model type.

## 5. MCP Server

Ships with the package. Wraps the SDK as MCP tools.

```bash
model-ledger serve                    # start MCP server
model-ledger serve --backend sqlite   # explicit backend
model-ledger serve --port 8080        # custom port
```

Tools exposed:
- `register_model` — register a new model
- `record_observation` — record a snapshot
- `tag_model` — set/move a tag
- `get_model` — retrieve model identity
- `list_models` — list models with filters
- `get_history` — snapshot history for a model
- `get_latest` — latest snapshot (optionally by tag)
- `diff_snapshots` — structural diff between two snapshots
- `validate_model` — run compliance validation
- `search` — search across model payloads

Each tool has clear JSON Schema input/output. An agent can discover and use these tools without documentation.

## 6. CLI

```bash
model-ledger register "arr-v3" --owner compliance-ml --tier high --purpose "TM ARR"
model-ledger record "arr-v3" --event introspected --source ml_platform --payload '{"algorithm": "XGBoost"}'
model-ledger tag "arr-v3" v3
model-ledger tag "arr-v3" active
model-ledger history "arr-v3"
model-ledger history "arr-v3" --event introspected
model-ledger latest "arr-v3"
model-ledger diff <hash-a> <hash-b>
model-ledger validate "arr-v3" --profile sr_11_7
model-ledger search "XGBoost"
model-ledger export audit-pack "arr-v3"
model-ledger serve                     # start MCP server
model-ledger watch --interval 1h       # run registered watchers
```

## 7. Views & Exports

Views are computed from snapshots, not stored. They're functions, not data models.

- `export_audit_pack(ledger, model)` — walks snapshot chain, builds HTML/JSON/Markdown audit pack
- `export_model_card(ledger, model)` — latest snapshot + identity → model card format
- `export_inventory_json(ledger)` — all models with latest snapshots, flattened for dashboards
- `build_sr117_tree(snapshot.payload)` — constructs Inputs/Processing/Outputs tree from whatever the payload contains. Returns `None` for model types that don't decompose this way.
- `diff_report(ledger, hash_a, hash_b)` — human-readable or structured diff

New regulatory frameworks = new view functions. No core changes required.

## 8. Migration Path from v0.2.0

This is an incremental migration, not a rewrite:

1. **ModelRef from Model:** Extract 8 fields from `Model`. Compute `model_hash`.
2. **Snapshots from ModelVersion:** Each version → `Snapshot(event_type="migrated", payload=version.model_dump())`.
3. **Snapshots from AuditEvent:** Each event → `Snapshot(event_type=event.action, payload=event.details)`.
4. **Tags from version strings:** `Tag("v3", model_hash, snapshot_hash)` for each version.
5. **Backend protocol update:** `InventoryBackend` → `LedgerBackend`. Method renames, not conceptual changes.
6. **Test migration:** 176 tests update incrementally. Most test SDK behavior, not internal schema.
7. **Deprecation wrappers:** v0.3.0 ships `Inventory` as an alias for `Ledger` with deprecation warnings. `new_version()` wraps `record()`. Clean removal in v0.4.0.

## 9. What This Does NOT Include (YAGNI)

- **Full-text search / vector search on payloads.** SQLite JSON1 is sufficient for v0.3.0. Semantic search is a future plugin.
- **Real-time event streaming.** Watchers poll. Event-driven (webhooks) is a future protocol extension.
- **Multi-tenancy / RBAC.** Single-tenant for now. Access control is the backend's responsibility.
- **UI / web dashboard.** The MCP server IS the agent interface. Human dashboards are downstream consumers (like Isha's Blockcell page).
- **Automatic payload schema inference.** Introspectors can ship schemas. The core doesn't infer.

## 10. Success Criteria

1. A developer can `pip install model-ledger`, register a model, record an observation, and query it in under 10 lines of Python.
2. An AI agent can discover and use the MCP tools with zero documentation.
3. The same ledger stores an XGBoost model, a SQL heuristic, and a vendor API model without schema conflicts.
4. `ledger.diff(a, b)` produces a meaningful structural comparison for any two snapshots.
5. A compliance validator can check SR 11-7 requirements across all model types.
6. All 176+ existing tests pass after migration (via deprecation wrappers).
7. The Block forge repo (`model-ledger-block`) needs minimal changes — introspectors and watchers only.
