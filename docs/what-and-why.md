# model-ledger

A formal, open-source model inventory and governance framework for the AI era.

**Author**: Vignesh Narayanaswamy
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

Spreadsheets. At most of the financial industry. A model inventory is typically an Excel workbook or a SharePoint list maintained by the MRM team. It tracks 20-50 models with columns for name, owner, tier, status, last validation date.

This fails in predictable ways:

- **Stale data.** The spreadsheet drifts from reality within weeks. Nobody's workflow includes "update the inventory spreadsheet."
- **No audit trail.** When did the tier change? Who approved it? The spreadsheet doesn't know.
- **Flat structure.** SR 11-7 defines a model as having input, processing, and output components. A spreadsheet row can't represent a hierarchical decomposition.
- **No machine consumption.** AI agents can't traverse a spreadsheet to understand model structure.
- **No validation.** There's no way to run compliance checks against a spreadsheet — someone eyeballs it.

Commercial tools exist. ValidMind, SAS Model Risk Management, and others offer hosted platforms with UIs, dashboards, and workflow engines. They're expensive, proprietary, not developer-friendly, and create vendor lock-in. None of them provide an open standard that the industry can build on.

### What's different now

Two things have changed that make a new approach viable:

**1. AI agents are doing governance work.** Organizations are building AI agents that generate validation reports from model artifacts — compressing multi-day manual work into sub-hour generation. These agents need machine-readable governance data as input, not spreadsheets and PDFs.

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

Audit packs (examiner-ready bundles), gap reports (missing fields with severity and remediation hints), and agent-consumable configs (structured inputs that AI validation tools can consume directly).

---

## The Feedback Loop

The most common question about AI-assisted governance: "How does it get better over time?"

Today, validation observations get triaged in spreadsheets. A reviewer removes an observation because an AI agent cross-contaminated findings between two models, or because it flagged an intentional design choice. That correction is lost. The next validation cycle makes the same mistake.

model-ledger captures these corrections as structured data — not as spreadsheet edits that nobody will ever read again. Over validation cycles and across models, this feedback accumulates into a dataset of governance judgment: what was flagged, what survived triage, what was removed and why.

This is valuable for three reasons:

1. **Agent improvement.** Any validation tool — AI or otherwise — can query the feedback corpus before generating observations. "Have observations like this been removed for `justified_by_design` on similar models?" This is pure computation over accumulated data, not new rules.
2. **Process visibility.** Leadership can see acceptance rates by observation type, model, and pillar. If the same removal reasons keep recurring, the tooling isn't learning.
3. **Regulatory defensibility.** The full triage history — including what was removed and why — is structured, immutable, and auditable. Examiners can see that the process is rigorous even when observations are removed.

The design principle: the core schema (I/P/O tree, regulatory fields, structural invariants) is fixed — this is the auditable floor that regulators expect. The feedback layer is the learning surface that improves governance quality with each cycle. Stability where governance demands it; adaptability where computation can improve it.

---

## Architecture

### Core library (`model-ledger`, PyPI)

The schema, SDK, validation engine, storage backends, feedback system, and export layer. Apache-2.0 licensed.

### Adapters (organization-specific)

model-ledger's `InventoryBackend` protocol and adapter pattern are designed so that any organization can write adapters to read from their existing systems of record — Jira, ServiceNow, Google Drive, Snowflake, internal inventory platforms — and normalize data into model-ledger's schema. The core library never depends on any specific external system.

### Schema Extension Points

The core schema is designed for stability but not rigidity. An `extra_metadata` field on all major objects (Model, ModelVersion, ComponentNode, Observation) allows any tool to park discovered patterns. If a field consistently appears in `extra_metadata` across many models — meaning agents or users keep finding it useful — it can be promoted to a first-class field in a future schema version. Agents discover what's useful; humans decide when to formalize.

---

## Relationship with Existing Tools

model-ledger is not a replacement for commercial platforms — it's a different layer.

**Commercial platforms** (ValidMind, SAS Model Risk Management, and similar) offer hosted model governance with dashboards, workflow engines, and compliance reporting. They are proprietary and expensive. model-ledger is not a hosted platform — it's a library. Organizations that need a UI can build one on top of model-ledger's schema and SDK. The value is in the open standard, not the hosting.

**Existing inventory systems** (Yields.io, ServiceNow, internal databases) can serve as data sources. model-ledger's adapter pattern lets you ingest from these systems, adding the structural decomposition, validation engine, observation tracking, and agent-consumable exports they were not designed for.

**AI validation agents** produce observations that model-ledger captures with full lifecycle tracking. model-ledger provides the structured model context these agents consume as input — model-ledger is the filing cabinet; the agent is the analyst.

---

## Roadmap

| Phase | Scope | Timeline |
|-------|-------|----------|
| v0.1 | Core schema, SDK, SR 11-7 profile, storage backends, observation lifecycle, feedback corpus | Built (95 tests passing) |
| v0.2 | Export layer, CLI tooling, adapter examples | Q2 2026 |
| v0.3 | JSON-LD export, additional compliance profiles (EU AI Act, NIST AI RMF) | Q3 2026 |
| v0.4 | CycloneDX MBOM export, contributor ecosystem | Q4 2026 |
