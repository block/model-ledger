# model-ledger — Technical Design

A typed, event-sourced model inventory with pluggable storage, multi-platform scanning, dependency tracking, and executable compliance profiles.

**Author**: Vignesh Narayanaswamy
**Version**: 0.3.0
**Prerequisite**: [What & Why](what-and-why.md) covers the motivation and strategic context.

---

## Overview

model-ledger has six layers:

```
┌──────────────────────────────────────────────────────┐
│  Export          audit packs, gap reports             │
├──────────────────────────────────────────────────────┤
│  Validation      SR 11-7, EU AI Act, NIST AI RMF     │
├──────────────────────────────────────────────────────┤
│  Scanner         Scanner protocol, InventoryScanner,  │
│                  ScannerRegistry, DBConnection         │
├──────────────────────────────────────────────────────┤
│  SDK             Ledger (register, record, tag,        │
│                  link_dependency, inventory_at)         │
├──────────────────────────────────────────────────────┤
│  Core            ModelRef, Snapshot, Tag, exceptions   │
├──────────────────────────────────────────────────────┤
│  Storage         LedgerBackend protocol, InMemory      │
└──────────────────────────────────────────────────────┘
```

Organization-specific scanners and backends sit alongside, not above — they depend on `model-ledger`, never the reverse.

---

## Core Data Model

### ModelRef — Regulatory Identity

The minimum a regulator needs to know about a model's existence.

```python
class ModelRef(BaseModel):
    model_hash: str         # sha256(name + owner + created_at)[:32]
    name: str               # human-readable label
    owner: str              # accountable team or individual
    model_type: str         # "ml_model", "heuristic", "signal", "vendor", "llm"
    model_origin: str       # "internal", "vendor", "api", "open_source"
    tier: str               # risk tier
    purpose: str            # what the model does
    status: str             # "active", "retired", "draft"
    created_at: datetime    # when first registered
```

### Snapshot — Immutable Observation

Content-addressed, timestamped record of something that happened to or was observed about a model.

```python
class Snapshot(BaseModel):
    snapshot_hash: str       # sha256(model_hash + timestamp + payload)[:32]
    model_hash: str          # which model this is about
    parent_hash: str | None  # chain snapshots together
    timestamp: datetime      # when this was recorded
    actor: str               # who/what created this (human, scanner, CI)
    event_type: str          # "registered", "discovered", "scan_confirmed",
                             # "not_found", "enriched", "depends_on", etc.
    source: str | None       # which scanner/system provided this
    payload: dict[str, Any]  # schema-free — scanner metadata, enrichment, etc.
    tags: dict[str, str]     # arbitrary key-value metadata
```

### Tag — Mutable Pointer

Like a git tag or branch — a named pointer to a specific Snapshot.

```python
class Tag(BaseModel):
    name: str                # "latest", "v3", "prod"
    model_hash: str
    snapshot_hash: str
    updated_at: datetime
```

---

## Ledger SDK

Every method is tool-shaped: clear inputs, JSON-serializable outputs, no side effects beyond the ledger.

| Method | Purpose |
|---|---|
| `register(name, owner, ...)` | Create a ModelRef + "registered" Snapshot |
| `record(model, event, payload, actor)` | Append an immutable Snapshot |
| `tag(model, name)` | Point a Tag at the latest Snapshot |
| `get(name_or_hash)` | Retrieve a ModelRef |
| `list(**filters)` | Filter models by any field |
| `history(model)` | All Snapshots, newest first |
| `latest(model, tag?)` | Most recent Snapshot (or tagged one) |
| `link_dependency(upstream, downstream)` | Bidirectional dependency Snapshots |
| `dependencies(model, direction)` | Query dependency graph |
| `inventory_at(date, platform?)` | Point-in-time reconstruction |

---

## Scanner Architecture

### Scanner Protocol

```python
class Scanner(Protocol):
    name: str
    platform_type: str
    def scan(self) -> list[ModelCandidate]: ...
    def has_changed(self, last_scan: datetime) -> bool: ...

class EnrichableScanner(Scanner, Protocol):
    def enrich(self, candidate: ModelCandidate) -> dict: ...
```

### ModelCandidate

```python
class ModelCandidate(BaseModel):
    name: str
    owner: str | None
    model_type: str
    platform: str
    platform_id: str | None
    parent_name: str | None          # hierarchy support
    external_ids: dict[str, str]     # cross-platform dedup
    metadata: dict[str, Any]
```

### InventoryScanner

Orchestrates multiple scanners with:
- **filter_fn** — post-scan, pre-registration filtering
- **scan_run_id** — groups all snapshots from one scan run
- **not_found tracking** — records when models disappear from a platform
- **has_changed** — skips scan if platform hasn't changed
- **enrich** — calls EnrichableScanner.enrich() and records results

### ScannerRegistry

Discovers scanners via `importlib.metadata.entry_points(group="model_ledger.scanners")`. Install a scanner package, it auto-registers.

### DBConnection Protocol

```python
class DBConnection(Protocol):
    def execute(self, query: str, params: dict | None = None) -> list[dict]: ...
```

Thin abstraction for SQL-based scanners. Any database client implements this.

---

## Extension Points

All extension points use `@runtime_checkable` Protocol — no abstract base classes.

| Protocol | Purpose | Entry Point Group |
|---|---|---|
| `Scanner` | Discover models on a platform | `model_ledger.scanners` |
| `Introspector` | Extract metadata from fitted models | `model_ledger.introspectors` |
| `LedgerBackend` | Storage for ModelRef/Snapshot/Tag | — |
| `DBConnection` | SQL access for scanners | — |

---

## Design Principles

1. **The inventory is an event log, not a table.** Never mutate — always append.
2. **Schema is discovered, not declared.** Scanners observe and record. The ledger stores what was found.
3. **Agents are first-class consumers.** Every SDK function maps to a tool call.
4. **The stable core is tiny.** Identity + snapshot + tag. Everything else is a plugin.
5. **Protocol-first.** No base classes. Implementations own all complexity.
