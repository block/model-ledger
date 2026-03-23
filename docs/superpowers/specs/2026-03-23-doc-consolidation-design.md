# model-ledger Doc Consolidation — Design Spec

**Date**: 2026-03-23
**Author**: Vignesh Narayanaswamy
**Status**: Draft
**Timeline**: Hackweek (week of 2026-03-23)

---

## Context

model-ledger has ~15 overlapping docs accumulated across design iterations, strategy explorations, and research. v0.1.0 is built (81 tests, 7 commits). Hackweek is this week — the goal is to file the OSPO Prototype issue, push the code to `github.com/block/model-ledger`, and produce two consolidated docs that replace the existing pile.

### Source Material

- `2026-02-16-model-ledger-design-DEFINITIVE.md` (canonical design)
- `2026-03-17-model-ledger-executive-summary.md`
- `2026-03-17-model-ledger-open-source-proposal.md`
- `2026-03-17-model-ledger-technical-appendix.md`
- `2026-03-17-model-ledger-deep-research.md`
- Yields PRD (GDoc `1GwW14jegof4J7Q-MSIkMuFMkKej-iE8ZzI0JC6V9Cko`)
- 9 additional earlier-iteration docs in `~/docs/plans/`
- Actual code at `~/model-ledger/src/model_ledger/`

### Internal Resources Leveraged

- Block OSPO process: `go/new-open-source`, Prototype track (immediate repo creation)
- Block OSS maturity model: `go/open-source-maturity` (Prototype → Incubation → Core)
- Template repo: `block/oss-project-template` (Apache-2.0, GOVERNANCE.md, renovate.json)
- OSPO contacts: Manik Surtani (Head of OSPO), Nidhi Nahar (Head of Patents & OSS)
- Slack: `#opensource`
- No rigid proposal template exists — OSPO issue forms serve that purpose

---

## Approach

**Parallel with shared skeleton.** Both docs share source material but have zero audience overlap. Design outlines together, write in parallel, share both with Isha/Krish for a single feedback round.

### Deliverables

| Doc | File (source of truth) | Google Doc (approval circuit) |
|-----|------------------------|-------------------------------|
| What & Why | `~/model-ledger/docs/what-and-why.md` | Create after markdown finalized |
| Technical Design | `~/model-ledger/docs/technical-design.md` | Create after markdown finalized |

### Skills to Use

- `generating-prds` — deep internal research for What & Why (Glean, codesearch, Slack, GDrive)
- `block-writing` — Block content standards enforcement
- `docs-builder` — styled HTML if needed for external sharing

---

## Doc 1: "model-ledger — What & Why"

**Audience**: Isha, Krish, OSPO, potential external adopters
**Tone**: Confident, concise, no code. Diagrams welcome, jargon minimal.
**Structure**: Industry pitch → Block context → Decision request

### Outline

#### 1. The Problem Everyone Has (~200 words)
Every bank's model inventory is a spreadsheet. SR 11-7 requires comprehensive model inventories; the industry responds with Excel and SharePoint. Commercial tools (Yields.io, ValidMind, SAS) exist but are expensive, proprietary, and not developer-friendly. No open standard exists.

#### 2. Why Now: The Agent Era Changes Everything (~200 words)
AI agents are governing models — AutoValidator proves it. But agents can't consume spreadsheets or PDFs. The gap isn't "we need a better UI" — it's "we need machine-readable governance infrastructure."

Frame through the Bitter Lesson (Sutton, 2019): the history of AI shows that general methods leveraging computation always win over hand-encoded human knowledge. Model governance is about to learn the same lesson. Today's governance is manual: humans assemble context, humans check compliance, humans write reports. model-ledger doesn't try to encode governance intelligence — it builds the structured representation that lets AI agents do the governing. The validation rules are the floor (regulatory minimums), not the ceiling. The real intelligence lives in agents that traverse, reason over, and act on the structured data.

Key distinction: model-ledger is infrastructure (representation), not reasoning. Like how good data formats (protobuf, JSON-LD) enable computation to scale, model-ledger is the governance data format that makes the Bitter Lesson possible for MRM.

#### 3. What model-ledger Is (~200 words)
One-paragraph definition, then three capabilities:
- A formal schema (models as hierarchical I/P/O components, per SR 11-7)
- A validation engine (executable compliance rules, not checklists)
- An export layer (audit packs, gap reports, agent-consumable configs)

Includes the cCRR tree diagram (visual, no code).

#### 4. Dual Value: Open Source + Block Internal (~250 words)
Two subsections:
- **External (PyPI, Apache-2.0)**: Industry standard anyone can adopt. Targets the 90% on spreadsheets. Positions Block as a governance thought leader.
- **Internal (`model-ledger-block`)**: Adapters that read from Yields, Jira CCM, GDrive, ML_Platform. Generates AutoValidator configs. Cuts context assembly from hours to minutes.

Clean separation: open-source core vs. internal adapters.

#### 5. How This Fits with Yields (~150 words)
Yields is the system of record. model-ledger is the standardization and interop layer — it makes Yields data portable, validatable, and agent-consumable. Maps to Phase 7 of the Yields PRD. Complements, never competes.

#### 6. What's Already Built (~100 words)
v0.1.0 exists: core schema, SDK, validation engine, storage backends, 81 tests. Not vaporware — working library ready for Prototype publication under `github.com/block`.

#### 7. Open Source Path (~150 words)
Block OSPO Prototype track → Incubation → Core. References `go/new-open-source`, `block/oss-project-template`, Apache-2.0. Maturity model alignment. Filing this week during hackweek.

#### 8. Success Metrics & Timeline (~100 words)
- Context assembly time: hours → ≤30 min
- 25 internal models in schema within 90 days
- 3 teams using (MRM, Risk ML, UCML) within 90 days
- External: first non-Block adopter within 6 months

#### 9. Decision Request (~50 words)
Three asks: approve repo creation, approve OSPO submission, approve 90-day pilot.

---

## Doc 2: "model-ledger — Technical Design"

**Audience**: Engineers, OSS contributors, Isha, Dan
**Tone**: Precise, code-heavy, opinionated. Real API, not pseudocode.
**Structure**: Contributor-first ("how it works") → Design rationale ("why it's built this way")

### Outline

#### 1. Overview (~100 words)
One-paragraph definition + link to What & Why for strategic context. Architecture diagram: Schema → SDK → Validation → Export. Block adapter layer as a separate package.

#### 2. Data Model (~400 words + code)
The core of the doc:
- `Model` and `ModelVersion` — identity, ownership, lifecycle states
- `ComponentNode` — I/P/O tree structure, typed containment rules
- `Finding`, `AuditEvent`, `GovernanceDoc` — governance artifacts
- Enums: `ModelType`, `RiskTier`, `ModelStatus`, `VersionStatus` (case-insensitive)
- Structural invariants: single parent, three top-level children, typed containment, version isolation
- Real Pydantic code from `core/models.py`

#### 3. SDK (~300 words + code)
How you use the library:
- `Inventory` — entry point, backend-agnostic
- `DraftVersion` — context manager for building model versions
- Registration flow: create model → draft version → add components → publish
- Assembly flow: read from adapters → normalize → validate → export
- Real examples from `sdk/inventory.py` and `sdk/draft_version.py`

#### 4. Validation Engine (~250 words + code)
How compliance checks work:
- `ValidationProfile` interface
- `sr_11_7` profile — 6 rules, what each checks, severity levels
- How to add a new profile (extension point for `eu-ai-act`, `nist-ai-rmf`, etc.)
- Real code from `validate/engine.py` and `profiles/sr_11_7.py`

#### 5. Storage Backends (~200 words + code)
Pluggable persistence:
- `MemoryBackend` — testing and ephemeral use
- `SQLiteBackend` — immutability enforcement, audit trail, migration strategy
- Backend interface for adding Postgres, DynamoDB, etc.
- Append-only audit events

#### 6. Export (~150 words)
What comes out:
- Audit packs (examiner-ready bundles)
- Gap reports (missing fields, severity, remediation hints)
- AutoValidator configs (`ValidationRunConfig` contract)
- JSON-LD (machine-readable semantic export)
- CycloneDX MBOM (supply chain integration)

#### 7. Block Integration Layer — `model-ledger-block` (~200 words)
Internal adapter package (lives in `forge-internal-mrm`, not OSS repo):
- Yields adapter — model metadata and status
- Jira CCM adapter — change history and approvals
- GDrive adapter — governance documents
- Assembly engine — orchestrates adapters into unified `Model` objects
- AutoValidator bridge — generates configs from assembled models
- Contract boundary: adapters depend on `model-ledger`, never the reverse

#### 8. Design Rationale (~500 words)
The "why" section:
- **Bitter Lesson alignment**: model-ledger is representation, not reasoning. The schema and validation rules are the minimum structure agents need — the floor, not the ceiling. The design deliberately avoids encoding governance intelligence (what to do about findings, how to prioritize risks, when a model is "good enough") and instead provides the structured data that lets agents like AutoValidator discover those answers through computation. Hardcoded rules (SR 11-7 profile) are regulatory minimums — test suites, not decision engines.
- Why OWL/SHACL-inspired but Pydantic-implemented (rigor without RDF complexity)
- Why strict I/P/O tree (SR 11-7 alignment, agent navigability, examiner expectations)
- Why immutable published versions (audit integrity, regulatory defensibility)
- Why assembler-first over SDK-first (immediate value for 44 existing models)
- Why Apache-2.0 (Block standard, maximum adoption, patent protection)
- Alternatives considered and rejected (ValidMind, custom platform, Yields extension)

#### 9. What's Next (~100 words)
Contributor roadmap:
- v0.2: Block adapters (Yields, Jira, GDrive)
- v0.3: CLI tooling, JSON-LD export
- v0.4: Additional compliance profiles
- Contributing guide pointer, DCO requirement, conventional commits

---

## Decisions Made During Brainstorming

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary job of What & Why | All three layered (industry → Block → decision) | Serves OSPO, stakeholders, and external adopters in one doc |
| Where docs live | Both (markdown source of truth + Google Docs for approval) | Version control + easy commenting |
| Yields relationship | "Yields' missing layer" framing | Positions as complement, respects Isha's work |
| OSPO track | Prototype (file immediately, build during 3-month window) | Hackweek urgency, low friction |
| Hackweek scope | Both docs drafted + OSPO issue + code push | Ambitious but source material is ready |
| Technical Design focus | Contributor-first, then design rationale | Serves the OSS audience first, curious readers second |
| Writing approach | Parallel with shared skeleton | Zero audience overlap, single feedback round, hackweek demands speed |
| Bitter Lesson framing | Integrate into both docs | Manager (Krish) sent Sutton's essay — model-ledger is representation (infrastructure) not reasoning (intelligence). Validation rules are the floor, agents are the ceiling. |
