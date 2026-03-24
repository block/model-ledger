# model-ledger

A formal, open-source model inventory and governance framework for the AI era.

**Author**: Vignesh Narayanaswamy, Block MRM
**Date**: March 2026
**License**: Apache-2.0

---

## Overview

model-ledger is a Python library that provides a typed, version-controlled, machine-readable inventory for model risk management. It implements the structural requirements of SR 11-7 and related regulatory frameworks as executable code — not as checklists, spreadsheets, or commercial platforms.

The library is designed so that AI agents can consume, traverse, validate, and act on governance metadata — not just humans. This is the core architectural principle: governance infrastructure should be structured for computation, because computation scales and manual processes don't.

```
pip install model-ledger
```

---

## Background

### What a model inventory is

Every regulated financial institution that uses models — credit risk, fraud detection, transaction monitoring, pricing — is required to maintain an inventory of those models. The Federal Reserve's SR 11-7 guidance states explicitly: *"Banks should maintain a comprehensive set of information for models implemented for use, under development for implementation, or recently retired."*

This inventory must track model identity, ownership, purpose, risk tier, structural components (inputs, processing logic, outputs), governance documents, validation history, and findings. Examiners expect to see it. Internal audit expects to review it. Model validators need it to do their work.

### How the industry does it today

Spreadsheets. At Block, at JPMorgan, at most of the financial industry. A model inventory is typically an Excel workbook or a SharePoint list maintained by the MRM team. It tracks 20-50 models with columns for name, owner, tier, status, last validation date.

This fails in predictable ways:

- **Stale data.** The spreadsheet drifts from reality within weeks. Nobody's workflow includes "update the inventory spreadsheet."
- **No audit trail.** When did the tier change? Who approved it? The spreadsheet doesn't know.
- **Flat structure.** SR 11-7 defines a model as having input, processing, and output components. A spreadsheet row can't represent a hierarchical decomposition.
- **No machine consumption.** AI agents (like Block's AutoValidator) can't traverse a spreadsheet to understand model structure.
- **No validation.** There's no way to run compliance checks against a spreadsheet — someone eyeballs it.

Commercial tools exist. Yields.io, ValidMind, SAS Model Risk Management, and others offer hosted platforms with UIs, dashboards, and workflow engines. They're expensive, proprietary, not developer-friendly, and create vendor lock-in. None of them provide an open standard that the industry can build on.

### What's different now

Two things have changed that make a new approach viable:

**1. AI agents are doing governance work.** Block's AutoValidator generates validation reports from model artifacts — compressing multi-day manual work into sub-hour generation. Other institutions are building similar tools. These agents need machine-readable governance data as input, not spreadsheets and PDFs.

**2. The Bitter Lesson applies to governance.** Rich Sutton's observation — that general methods leveraging computation always outperform hand-encoded human knowledge — is playing out in model risk management. The bottleneck isn't "smarter rules" or "better checklists." It's structured data that agents can compute over. More data, better agents, less manual work. The alternative is encoding more human judgment into more rigid workflows, which is exactly the approach that plateaus.

model-ledger is the infrastructure layer that makes both of these possible.

---

## What model-ledger Provides

The library is a formal inventory that tracks four first-class entities:

### Models

A model is a versioned, hierarchical structure. Each version contains a component tree with three top-level branches — Inputs, Processing, and Outputs — per SR 11-7's three-component definition. This isn't just metadata; it's a structural decomposition that agents can traverse and validators can assess component by component.

```
cCRR Global v2.0.0
├── Inputs/
│   ├── beacon_features [FeatureSet, 497 features from Dumbo]
│   ├── feature_engine_signals [FeatureSet, from Feature Engine]
│   ├── active_sellers_population [Dataset, Snowflake SQL]
│   └── stationarity_assumption [Assumption, "risk patterns stable over 180 days"]
├── Processing/
│   ├── fillna_imputation [Preprocessing, fillna_value=0]
│   ├── shap_feature_selection [FeatureSelection, 2-stage]
│   └── xgboost_classifier [Algorithm, XGBClassifier, 200 features]
└── Outputs/
    ├── risk_score [ProbabilityScore, 0-1]
    ├── batch_score_table [Dataset, app_compliance.square.batch_score_prefect]
    └── ml_platform_deployment [Deployment, daily batch via Prefect + Cascade]
```

Each model also carries ownership, risk tier, intended purpose, regulatory jurisdiction, vendor information, and lifecycle status — all typed, all validated.

### Governance Documents

Linked evidence — model specifications, validation reports, conceptual soundness documents, approval records. Referenced by URI, not copied, so they stay current.

### Observations

Validation findings from any source: human reviewers, AI agents, automated testing tools, or manual entry. Each observation has a source tag identifying who generated it, and a full lifecycle:

> **Created** → **Triaged** (kept / removed / modified, with reason and rationale) → **Issued** (published in a final validation report) or **Removed** (preserved in history)

Observations can be grouped into validation runs. Multiple runs can exist for a single model version — the full history is preserved, but only one run is marked `final`, and only `issued` observations appear in the published report.

### Feedback

Structured records of what happened to each observation and why. Every triage decision — keep, remove, modify — is captured with a reason code (from a taxonomy like `refuted_by_code`, `justified_by_design`, `wrong_scope`, `consolidated`) and a free-text rationale. This accumulated feedback is queryable: any tool can check "have similar observations been removed before?" before generating new ones.

### Validation Engine

Executable compliance profiles — starting with SR 11-7 — that check models against regulatory requirements and return structured results with severity levels and remediation suggestions. Profiles are pluggable; adding `eu-ai-act` or `nist-ai-rmf` means implementing a new profile class, not changing the engine.

### Export

Audit packs (examiner-ready bundles), gap reports (missing fields with severity and remediation hints), and agent-consumable configs (the `ValidationRunConfig` contract that AutoValidator and similar tools consume).

---

## The Feedback Loop

The most common question about AI-assisted governance: "How does it get better over time?"

Today, validation observations get triaged in spreadsheets. A reviewer removes an observation because the AutoValidator cross-contaminated findings between two models, or because it flagged an intentional design choice. That correction is lost. The next validation cycle makes the same mistake.

model-ledger captures these corrections as structured data — not as spreadsheet edits that nobody will ever read again. Over validation cycles and across models, this feedback accumulates into a dataset of governance judgment: what was flagged, what survived triage, what was removed and why.

This is valuable for three reasons:

1. **Agent improvement.** Any validation tool — AI or otherwise — can query the feedback corpus before generating observations. "Have observations like this been removed for `justified_by_design` on similar models?" This is pure computation over accumulated data, not new rules.
2. **Process visibility.** Leadership can see acceptance rates by observation type, model, and pillar. If the same removal reasons keep recurring, the tooling isn't learning.
3. **Regulatory defensibility.** The full triage history — including what was removed and why — is structured, immutable, and auditable. Examiners can see that the process is rigorous even when observations are removed.

The design principle: the core schema (I/P/O tree, regulatory fields, structural invariants) is fixed — this is the auditable floor that regulators expect. The feedback layer is the learning surface that improves governance quality with each cycle. Stability where governance demands it; adaptability where computation can improve it.

---

## Architecture

### Open-source core (`model-ledger`, PyPI)

The schema, SDK, validation engine, storage backends, feedback system, and export layer. Any organization can use this — no Block-specific dependencies. Apache-2.0 licensed.

### Internal adapters (`model-ledger-block`, Block-internal)

Adapters that read from Block's existing systems of record — Yields, Jira CCM, Google Drive, ML_Platform — and normalize data into model-ledger's schema. Also includes the AutoValidator integration: generating `ValidationRunConfig` inputs from the inventory and ingesting observation outputs back.

This separation is deliberate. The open-source core never depends on Block-specific systems. The internal package is where Block gets immediate operational value — context assembly that currently takes hours becomes a repeatable, command-driven operation.

### Schema Extension Points

The core schema is designed for stability but not rigidity. An `extra_metadata` field on all major objects (Model, ModelVersion, ComponentNode, Observation) allows any tool to park discovered patterns. If a field consistently appears in `extra_metadata` across many models — meaning agents or users keep finding it useful — it can be promoted to a first-class field in a future schema version. Agents discover what's useful; humans decide when to formalize.

---

## Relationship with Existing Tools

model-ledger stands on the shoulders of the tools that came before it.

**Yields.io** is Block's current model inventory system of record. It tracks model identity, status, and ownership through a web UI that MRM and model teams use today. model-ledger can ingest from Yields as a data source, providing the structural decomposition, validation engine, observation tracking, and agent-consumable exports that Yields was not designed for. In the short term, Yields remains the UI and entry point that teams are comfortable with. Over time, as model-ledger gains its own interfaces and teams interact with it directly, it progressively becomes the primary governance layer — a vendor-neutral, open-source alternative to commercial inventory platforms.

**ValidMind** and **SAS Model Risk Management** are commercial platforms that offer hosted model governance with dashboards, workflow engines, and compliance reporting. They are expensive and proprietary. model-ledger is not a hosted platform — it's a library. Organizations that need a UI can build one on top of model-ledger's schema and SDK. The value is in the open standard, not the hosting.

**AutoValidator** (Block-internal) is an AI agent that generates validation reports from model artifacts. model-ledger provides the structured model context that AutoValidator consumes as input, and captures AutoValidator's observation outputs with full lifecycle tracking. model-ledger is the filing cabinet; AutoValidator is the analyst. They are complementary systems with a clean interface boundary.

---

## Open Source at Block

model-ledger follows Block's established open-source program:

- **OSPO Prototype track.** Repository created immediately under `github.com/block/model-ledger`. Three-month evaluation window, then graduation to Incubation.
- **Apache-2.0 license.** Block's standard for open-source projects. Maximum adoption, patent protection.
- **Template and governance.** Built from `block/oss-project-template` with GOVERNANCE.md, CONTRIBUTING.md (DCO sign-off, conventional commits), and CODEOWNERS.
- **Maturity model.** Prototype → Incubation → Core, per `go/open-source-maturity`. model-ledger targets Incubation within the first 90 days.
- **OSPO contacts.** Manik Surtani (Head of OSPO), Nidhi Nahar (Head of Patents & OSS), `#opensource` Slack channel.

---

## Roadmap

| Phase | Scope | Timeline |
|-------|-------|----------|
| v0.1 | Core schema, SDK, SR 11-7 profile, storage backends, observation lifecycle | Built (81 tests passing) |
| v0.2 | Block adapters (Yields, Jira CCM, GDrive), AutoValidator integration | Q2 2026 |
| v0.3 | CLI tooling, JSON-LD export, additional compliance profiles | Q3 2026 |
| v0.4 | CycloneDX MBOM export, contributor ecosystem, first external adopter | Q4 2026 |

### Success Metrics

- Context assembly time reduced from manual multi-hour effort to ≤30 minutes in pilot
- 25 internal models represented in unified schema within 90 days
- 3 internal teams actively using (MRM, Risk ML, UCML) within 90 days
- First non-Block adopter within 6 months of public release

---

## Decision Request

1. Approve repository creation under `github.com/block` with Apache-2.0 licensing.
2. Approve OSPO Prototype submission via `go/new-open-source`.
3. Approve a 90-day pilot with MRM, Risk ML, and UCML.
