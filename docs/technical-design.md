# model-ledger — Technical Design

**Author**: Vignesh Narayanaswamy, Block MRM
**Date**: March 2026
**Status**: Outline — drafting during Hackweek
**Prerequisite**: Read [What & Why](what-and-why.md) for strategic context.

---

## 1. Overview

model-ledger is a Python library that provides a formal, machine-readable inventory for model governance. Four layers:

```
Schema (core/models.py) → SDK (sdk/) → Validation (validate/) → Export (export/)
```

The Block adapter layer (`model-ledger-block`) is a separate internal package.

## 2. Data Model

The core of the library.

- `Model` and `ModelVersion` — identity, ownership, lifecycle states
- `ComponentNode` — the I/P/O tree structure, typed containment rules
- `Finding`, `AuditEvent`, `GovernanceDoc` — governance artifacts
- Enums: `ModelType`, `RiskTier`, `ModelStatus`, `VersionStatus` (case-insensitive)

Structural invariants:

1. Single parent — every component has exactly one parent (strict tree)
2. Three top-level children — every model has exactly one Inputs, Processing, Outputs
3. Typed containment — Inputs can only contain Datasets, Assumptions, FeatureSets, etc.
4. Version isolation — modifying one version cannot affect another

Real Pydantic code from `core/models.py`.

## 3. SDK

How you use the library.

- `Inventory` — the entry point, backend-agnostic
- `DraftVersion` — context manager for building model versions
- Registration flow: create model → draft version → add components → publish
- Assembly flow: read from adapters → normalize → validate → export

Real examples from `sdk/inventory.py` and `sdk/draft_version.py`.

## 4. Validation Engine

How compliance checks work.

- `ValidationProfile` interface — what a profile must implement
- `sr_11_7` profile — 6 rules, what each checks, severity levels
- How to add a new profile (extension point for `eu-ai-act`, `nist-ai-rmf`, etc.)

Real code from `validate/engine.py` and `profiles/sr_11_7.py`.

## 5. Storage Backends

Pluggable persistence.

- `MemoryBackend` — for testing and ephemeral use
- `SQLiteBackend` — immutability enforcement, audit trail, migration strategy
- Backend interface — what you implement to add Postgres, DynamoDB, etc.
- Append-only audit events — every mutation is recorded

## 6. Export

What comes out.

- Audit packs (examiner-ready bundles)
- Gap reports (missing fields, severity, remediation hints)
- AutoValidator configs (`ValidationRunConfig` contract)
- JSON-LD (machine-readable semantic export) — *planned*
- CycloneDX MBOM (supply chain integration) — *planned*

Note: flag which formats are implemented vs. planned when drafting.

## 7. Observations & Feedback Schema

Observations are first-class inventory objects — not tied to any specific tool.

### Observation

A validation finding from any source.

- `id`, `content`, `priority`, `pillar` — what was found
- `source_type`: `human_reviewer` | `ai_agent` | `automated_tool` | `manual_entry`
- `source_detail` — optional (e.g., "AutoValidator run 3", "Dan Smith during annual review")
- `model_version_ref` — which model version this relates to
- `status`: `draft` → `issued` | `removed`
- Append-only lineage: every status change is recorded

### ValidationRun

Groups observations from a single validation effort.

- `run_id`, `timestamp`, `source_type`, `config_snapshot`
- `observations` — list of Observation refs
- `status`: `draft` | `superseded` | `final`
- Multiple runs per model version — full history preserved, only one is `final`

### ValidationReport

The "published" artifact.

- `model_version_ref`, `issued_observations` — the final set
- `issued_at`, `issued_by` — clear audit moment
- Immutable after issuance (mirrors `ModelVersion.publish()`)

### FeedbackEvent

What happened to an observation and why.

- `observation_ref` — which observation
- `verdict`: `keep` | `remove` | `modify`
- `reason_code` — from taxonomy (`refuted_by_code`, `justified_by_design`, `wrong_scope`, `consolidated`, etc.)
- `rationale` — free-text explanation
- `stage` — when in workflow (`pipeline_filter`, `triage`, `stakeholder_review`)
- `actor` — who made the decision (human name or tool identifier)

### FeedbackCorpus

Aggregate query interface over feedback history.

- "Show me all removals for this observation type / model type / pillar"
- Summary stats: acceptance rates, common reason codes
- Any tool can query this to avoid repeating known mistakes

### Schema Extension Points

How the schema evolves without breaking stability.

- Core fields (I/P/O tree, regulatory fields) are fixed and auditable
- `extra_metadata: dict[str, Any]` on Model, ModelVersion, ComponentNode, Observation
- Promotion path: frequently-appearing extensions get formalized in future versions
- Bitter Lesson applied to schema design: agents discover what's useful, humans decide when to formalize

## 8. Block Integration Layer — model-ledger-block

Internal adapter package (lives in `forge-internal-mrm`, not the OSS repo).

- Yields adapter — model metadata and status
- Jira CCM adapter — change history and approvals
- GDrive adapter — governance documents
- Assembly engine — orchestrates adapters into unified Model objects
- Contract boundary: adapters depend on model-ledger, never the reverse

### AutoValidator Integration

Block-specific integration with AutoValidator.

- **Ingest**: Reads `problems_registry.json` → creates Observation objects with `source_type: ai_agent`
- **Context**: Provides model component tree + governance docs + prior feedback history as input
- **Feedback retrieval**: Before generating observations, queries FeedbackCorpus for similar past removals
- **Adaptation metrics**: Tracks whether removal reasons recur (not learning) or decline (improving)
- This is one integration — the OSS schema supports any validation tool

## 9. Design Rationale

### Bitter Lesson Alignment

model-ledger is representation, not reasoning. The schema and validation rules are the minimum structure agents need — the floor, not the ceiling. The design deliberately avoids encoding governance intelligence (what to do about findings, how to prioritize risks, when a model is "good enough") and instead provides the structured data that lets agents discover those answers through computation. Hardcoded rules (SR 11-7 profile) are regulatory minimums — test suites, not decision engines.

### Other Design Decisions

- Why OWL/SHACL-inspired but Pydantic-implemented (rigor without RDF complexity)
- Why strict I/P/O tree (SR 11-7 alignment, agent navigability, examiner expectations)
- Why immutable published versions (audit integrity, regulatory defensibility)
- Why assembler-first over SDK-first (immediate value for 44 existing models)
- Why Apache-2.0 (Block standard, maximum adoption, patent protection)
- Alternatives considered and rejected (ValidMind, custom platform, Yields extension)

## 10. What's Next

Contributor roadmap:

- v0.2: Block adapters (Yields, Jira, GDrive)
- v0.3: CLI tooling, JSON-LD export
- v0.4: Additional compliance profiles

Contributing guide pointer, DCO requirement, conventional commits.
