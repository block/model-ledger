# Domain Concepts & Terminology

**Project**: model-ledger
**Domain**: Model Risk Management (MRM) — inventory, governance, and compliance for ML models

## Core Business Concepts

### ModelRef
**Definition**: Regulatory identity of a model — the minimum a regulator needs. Content-addressed via SHA-256 hash of name:owner:created_at. Serves as identity for both standalone models and composites.
**Implementation**: [`src/model_ledger/core/ledger_models.py`]
**Key Properties**:
- `model_hash`: SHA-256 content-addressed identity (32 hex chars)
- `name`, `owner`, `model_type`, `tier`, `purpose`, `status`: Core regulatory fields
- `last_seen`: Updated on every connector run, even when content unchanged

### Snapshot
**Definition**: Immutable, content-addressed observation of a model at a point in time. Core of the event-log paradigm — every mutation produces a Snapshot with event_type, actor, payload, and optional parent_hash for chaining.
**Implementation**: [`src/model_ledger/core/ledger_models.py`]
**Business Rules**:
- Append-only: snapshots are never modified or deleted
- Content-addressed: `snapshot_hash` = SHA-256 of model_hash:timestamp:payload (32 hex chars)
- `parent_hash`: Optional chain reference for event ordering

### Tag
**Definition**: Mutable pointer from a human-readable name to a specific snapshot_hash. Used for bookmarks like "latest_validation".
**Implementation**: [`src/model_ledger/core/ledger_models.py`]

### Composite Model
**Definition**: A ModelRef representing a governable business entity that aggregates technical components. Members linked via member_of relationships. Carries its own risk tier, validation cycle, and governance history. The primary inventory entry for regulators (~130 composites vs ~23,000 technical nodes).
**Implementation**: [`src/model_ledger/sdk/ledger.py`]
**Business Rules**:
- Membership tracked via member_added/member_removed snapshot events (not foreign keys)
- Change propagation: record() on any member auto-appends member_changed to parent composites (one level deep)
- Internal/governance events excluded from propagation

### Observation
**Definition**: A validation finding from any source (human reviewer, AI agent, automated tool). Has priority, pillar categorization, and lifecycle: draft -> issued -> removed.
**Implementation**: [`src/model_ledger/core/observations.py`]
**Relationships**:
- Grouped by ValidationRun (a single validation effort)
- Published via ValidationReport (immutable after creation)
- Accumulates FeedbackEvent records (append-only triage decisions)

### Model (v0.2.0)
**Definition**: Rich model identity with full regulatory fields (SR 11-7, EU AI Act, NIST AI RMF). Carries risk rating, jurisdictions, affected populations, vendor info, and a versions list.
**Implementation**: [`src/model_ledger/core/models.py`]
**Relationships**:
- Contains ModelVersion objects (draft -> published -> deprecated)
- Each version has a ComponentNode tree (IPO structure), governance docs, findings, evidence

### DataNode
**Definition**: Graph primitive representing a discoverable entity (model, pipeline, table) on a platform. Has input/output DataPorts for automatic dependency linking.
**Implementation**: [`src/model_ledger/graph/models.py`]
**Relationships**:
- Converted to ModelRef by Ledger.add()
- DataPort matching enables auto-wiring via Ledger.connect()

## Technical Concepts

### Event-Log Paradigm
**Purpose**: Core architectural pattern where models are identities (ModelRef) and everything else is immutable, append-only Snapshots. State is derived by replaying events.
**Implementation**: [`src/model_ledger/sdk/ledger.py`], [`src/model_ledger/core/ledger_models.py`]

### Content-Addressed Hashing
**Purpose**: SHA-256 hashing scheme for ModelRef and Snapshot identities, truncated to 32 hex chars. Enables content-hash dedup during connector ingestion — volatile fields (timestamps) excluded from dedup hash.
**Implementation**: [`src/model_ledger/core/ledger_models.py`]

### Change Propagation
**Purpose**: Automatic mechanism where record() on any model notifies parent composites via member_changed snapshots. One level deep, skips internal/governance events.
**Implementation**: [`src/model_ledger/sdk/ledger.py`] — `_propagating` flag prevents infinite recursion

### Membership Event Replay
**Purpose**: members() and membership_at() seed from dependency links, then overlay member_added/member_removed events chronologically. Handles both register_group()-seeded and add_member()-managed composites.
**Implementation**: [`src/model_ledger/sdk/ledger.py`]

### Tool-Shaped API
**Purpose**: Design principle where every SDK method has clear inputs, JSON-serializable outputs, and no side effects beyond the ledger — suitable for direct use as an agent tool call.
**Implementation**: [`src/model_ledger/tools/`] — 6 tool functions with Pydantic I/O schemas

### Profile-Based Validation
**Purpose**: Pluggable compliance checking against regulatory frameworks. Profiles registered via @register_profile decorator.
**Implementation**: [`src/model_ledger/validate/engine.py`], [`src/model_ledger/validate/profiles/`]

## Terminology Glossary

### Business Terms
- **MRM**: Model Risk Management — the regulatory discipline of identifying, assessing, and mitigating risks from model use
- **Risk Tier**: Regulatory classification (high/medium/low) determining governance rigor
- **SR 11-7**: Federal Reserve Supervisory Guidance on Model Risk Management
- **EU AI Act**: EU Regulation 2024/1689 for AI systems
- **NIST AI RMF**: NIST AI Risk Management Framework (AI 100-1) with GOVERN/MAP/MEASURE/MANAGE functions
- **IPO Structure**: Input/Processing/Output component tree required by SR 11-7
- **Governed Model**: A business-level composite entity subject to regulatory examination
- **Spine Architecture**: Vision where model-ledger connects all MRM workstreams through a shared append-only event log

### Technical Terms
- **Protocol-First**: Extension pattern using `@runtime_checkable` Protocol classes (not ABCs) for all plugin points
- **Content-Addressed**: Identity derived from content hash, not auto-incremented IDs
- **Member-of Relationship**: Dependency type indicating a component belongs to a composite/group
- **Connector**: Factory function creating DataNodes from external platforms (SQL, REST, GitHub, Prefect)
- **Scanner**: Protocol for discovering ModelCandidates on deployment platforms
- **Introspector**: Protocol for extracting metadata from ML model objects
- **Internal Events**: Ledger bookkeeping events not propagated to parent composites (registered, has_dependent, depends_on, member_added, member_removed, member_changed, observation_issued, observation_resolved, validated)
- **last_seen**: Timestamp distinguishing "still present" from "changed" during connector runs
- **change_detected / change_occurred**: Two timestamps on discovered snapshots — when the ledger noticed vs when the source system updated

## Domain Boundaries

| Context | Scope | Boundary |
|---------|-------|----------|
| Core Domain (Identity & Events) | `src/model_ledger/core/` | All domain models. No I/O, no persistence. Pure data definitions. |
| Graph Layer (Discovery) | `src/model_ledger/graph/` | Graph primitives and connector protocol. DataNodes are transient. |
| SDK Layer (Business Logic) | `src/model_ledger/sdk/` | All business logic and orchestration. Delegates persistence to backends. |
| Backend Layer (Persistence) | `src/model_ledger/backends/` | Storage protocols and implementations. No business logic. |
| Validation Layer (Compliance) | `src/model_ledger/validate/` | Compliance checking. Reads Model+Version, produces violations. |
| Scanner Layer (Platform Discovery) | `src/model_ledger/scanner/` | Platform scanner protocol. Produces ModelCandidates. |
| Agent Protocol (Tools) | `src/model_ledger/tools/` | 6 agent tool I/O schemas. Single source of truth for protocol contracts. |
| Connectors (Integration) | `src/model_ledger/connectors/` | Factory functions for external system discovery. Org-specific connectors go in separate packages. |

## Cross-References
- **Architecture Layers**: See [architecture.md](architecture.md)
- **Module Details**: See [modules.md](modules.md)
- **Implementation Patterns**: See [patterns.md](patterns.md)
