# model-ledger — Technical Design

A typed, version-controlled model inventory with pluggable storage, executable compliance profiles, and structured observation tracking.

**Author**: Vignesh Narayanaswamy
**Date**: March 2026
**Prerequisite**: [What & Why](what-and-why.md) covers the motivation and strategic context.

---

## Overview

model-ledger has four layers:

```
┌──────────────────────────────────────────────────────┐
│  Export          audit packs, gap reports, configs    │
├──────────────────────────────────────────────────────┤
│  Validation      SR 11-7 profile, pluggable engine   │
├──────────────────────────────────────────────────────┤
│  SDK             Inventory, DraftVersion, feedback    │
├──────────────────────────────────────────────────────┤
│  Core            Models, enums, exceptions, schema   │
├──────────────────────────────────────────────────────┤
│  Storage         SQLite, Memory, Protocol interface   │
└──────────────────────────────────────────────────────┘
```

Organization-specific adapters sit alongside, not above — they depend on `model-ledger`, never the reverse.

### Package Structure

```
src/model_ledger/
├── core/
│   ├── models.py       # Pydantic data models
│   ├── enums.py        # Case-insensitive enums
│   └── exceptions.py   # Actionable error hierarchy
├── sdk/
│   ├── inventory.py    # Main entry point
│   └── draft_version.py # Context manager for version building
├── validate/
│   ├── engine.py       # Profile registry and runner
│   └── profiles/
│       └── sr_11_7.py  # SR 11-7 compliance rules
├── backends/
│   ├── protocol.py     # Backend interface (Protocol)
│   ├── sqlite.py       # SQLite with immutability enforcement
│   └── memory.py       # In-memory for testing
├── export/             # Audit packs, gap reports, configs
└── introspect/         # Schema introspection utilities
```

---

## Data Model

The data model is informed by OWL ontology and SHACL constraint patterns, but implemented in Pydantic — ontological rigor without RDF complexity.

### Model

The top-level entity. Carries identity, ownership, risk classification, and regulatory metadata.

```python
class Model(BaseModel):
    model_id: str = Field(default_factory=_uuid)
    name: str
    description: str | None = None
    model_type: ModelType = ModelType.ML_MODEL     # ml_model, heuristic, vendor, llm, spreadsheet

    owner: str
    developers: list[str] = Field(default_factory=list)
    validator: str | None = None
    approver: str | None = None
    stakeholders: list[Stakeholder] = Field(default_factory=list)

    intended_purpose: str
    actual_use: str | None = None
    restrictions_on_use: list[str] = Field(default_factory=list)

    tier: RiskTier                                  # high, medium, low
    risk_rating: ModelRiskRating | None = None       # 4-factor calculator
    status: ModelStatus = ModelStatus.DEVELOPMENT    # development, review, active, deprecated, retired

    jurisdictions: list[str] = Field(default_factory=list)
    vendor: str | None = None

    versions: list[ModelVersion] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
```

### ModelVersion

A versioned snapshot of a model's structure and metadata. Versions are immutable once published — modifying a published version raises `ImmutableVersionError`.

```python
class ModelVersion(BaseModel):
    version: str
    status: VersionStatus = VersionStatus.DRAFT     # draft, published, deprecated

    training_target: str | None = None
    methodology_approach: str | None = None
    run_frequency: str | None = None
    deployment_mode: str | None = None
    monitoring_frequency: str | None = None
    next_validation_due: date | None = None

    tree: ComponentNode = Field(default_factory=_default_tree)

    upstream_models: list[str] = Field(default_factory=list)
    downstream_models: list[str] = Field(default_factory=list)

    documents: list[GovernanceDoc] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    artifacts: list[ModelArtifact] = Field(default_factory=list)
    deployments: list[DeploymentRecord] = Field(default_factory=list)
```

### ComponentNode

The I/P/O tree. Each model version has a root node with exactly three children: Inputs, Processing, Outputs. Leaf nodes are typed components.

```python
class ComponentNode(BaseModel):
    node_id: str = Field(default_factory=_uuid)
    name: str
    node_type: str              # "category", "dataset", "algorithm", "feature_set", etc.
    path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    children: list[ComponentNode] = Field(default_factory=list)

def _default_tree() -> ComponentNode:
    return ComponentNode(
        name="root", node_type="root",
        children=[
            ComponentNode(name="Inputs", node_type="category"),
            ComponentNode(name="Processing", node_type="category"),
            ComponentNode(name="Outputs", node_type="category"),
        ],
    )
```

### Enums

All enums are case-insensitive. `RiskTier("HIGH")`, `RiskTier("high")`, and `RiskTier("High")` all resolve to `RiskTier.HIGH`.

```python
class CaseInsensitiveEnum(str, Enum):
    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for member in cls:
                if member.value.lower() == value.lower():
                    return member
        return None

class ModelType(CaseInsensitiveEnum):
    ML_MODEL = "ml_model"
    HEURISTIC = "heuristic"
    VENDOR = "vendor"
    LLM = "llm"
    SPREADSHEET = "spreadsheet"

class RiskTier(CaseInsensitiveEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
```

### Structural Invariants

These are enforced by the validation engine and storage backends:

1. **Single parent.** Every component has exactly one parent. The tree is strict — no cycles, no shared children.
2. **Three top-level children.** Every model version has exactly one Inputs, one Processing, one Outputs node.
3. **Typed containment.** Inputs contain datasets, assumptions, feature sets. Processing contains algorithms, preprocessing steps, feature selection. Outputs contain scores, classifications, deployments.
4. **Version isolation.** Each ModelVersion has its own tree. Modifying one version cannot affect another.
5. **Publish immutability.** Published versions cannot be mutated. All changes require a new version.

---

## SDK

### Inventory

The main entry point. Backend-agnostic — pass any `InventoryBackend` implementation.

```python
from model_ledger import Inventory

inv = Inventory("governance.db")

# Register a model
model = inv.register_model(
    name="Fraud Detection Model",
    owner="ML Engineering",
    tier="high",
    intended_purpose="Credit risk scoring for loan applicants",
    developers=["alice", "bob"],
    validator="carol",
    model_type="ml_model",
    actor="vignesh",
)
```

### DraftVersion

Context manager for building a version. Mutations happen on the draft. Auto-saves on exit, does not auto-publish.

```python
with inv.new_version("Fraud Detection Model", version="2.0.0", actor="alice") as v:
    # Build the component tree
    v.add_component("Inputs/credit_features", type="feature_set",
                     metadata={"count": 150, "source": "Feature Store"})
    v.add_component("Inputs/active_customers", type="dataset",
                     metadata={"source": "data_warehouse", "query": "SELECT ..."})
    v.add_component("Processing/xgboost_classifier", type="algorithm",
                     metadata={"library": "xgboost", "features": 200})
    v.add_component("Outputs/risk_score", type="probability_score",
                     metadata={"range": [0, 1]})

    # Attach governance documents
    v.add_document(doc_type="system_design", title="Fraud Detection v2 Design Doc",
                   url="https://docs.google.com/document/d/...")
    v.add_document(doc_type="validation_report", title="2025 Annual Validation")

    # Set validation schedule
    v.set_next_validation_due("2027-03-01")

# Publish when ready (immutable after this)
inv.publish_version("Fraud Detection Model", "2.0.0", actor="carol")
```

### Assembly Flow (with adapters)

For existing models, adapters read from source systems and populate the inventory:

```python
# Example: adapters for your organization's systems
from my_org.adapters import InventoryAdapter, TicketAdapter

inventory = InventoryAdapter(credentials=...)
tickets = TicketAdapter(credentials=...)

# Assemble from existing systems
model_data = inventory.fetch_model("Fraud Detection Model")
change_history = tickets.fetch_changes("Fraud Detection Model")

# Normalize into model-ledger schema
inv.register_model(**model_data)
with inv.new_version("Fraud Detection Model", version="2.0.0") as v:
    inventory.populate_tree(v)
    tickets.attach_findings(v, change_history)
```

---

## Observations & Feedback

Observations are first-class inventory objects — validation findings from any source.

### Observation

```python
class Observation(BaseModel):
    observation_id: str = Field(default_factory=_uuid)
    content: str
    priority: str | None = None
    pillar: str | None = None           # "Conceptual Soundness", "Input Data Validation", etc.

    source_type: str                    # "human_reviewer", "ai_agent", "automated_tool", "manual_entry"
    source_detail: str | None = None    # "Validation Agent run 3", "Jane Smith during annual review"

    model_version_ref: str              # model_name + version
    status: str = "draft"               # draft → issued | removed
```

### ValidationRun

Groups observations from a single validation effort.

```python
class ValidationRun(BaseModel):
    run_id: str = Field(default_factory=_uuid)
    timestamp: datetime = Field(default_factory=_now)
    source_type: str                    # who ran this validation
    config_snapshot: dict[str, Any] = Field(default_factory=dict)

    observations: list[str] = Field(default_factory=list)  # observation IDs
    status: str = "draft"               # draft | superseded | final
```

Multiple runs can exist per model version. When a new run is marked `final`, the previous final run becomes `superseded`. Full history is always preserved.

### ValidationReport

The "published" artifact — the final set of observations that were issued.

```python
class ValidationReport(BaseModel):
    model_version_ref: str
    issued_observations: list[str]      # observation IDs — THE final set
    issued_at: datetime
    issued_by: str
    # Immutable after issuance (mirrors ModelVersion.publish())
```

### FeedbackEvent

What happened to an observation and why. Append-only.

```python
class FeedbackEvent(BaseModel):
    event_id: str = Field(default_factory=_uuid)
    observation_ref: str
    verdict: str                        # "keep", "remove", "modify"
    reason_code: str                    # "refuted_by_code", "justified_by_design", "wrong_scope", etc.
    rationale: str                      # free-text explanation
    stage: str                          # "pipeline_filter", "triage", "stakeholder_review"
    actor: str                          # human name or tool identifier
    timestamp: datetime = Field(default_factory=_now)
```

### FeedbackCorpus

Aggregate query interface. Not a Pydantic model — a query API over the storage backend.

```python
corpus = inv.feedback_corpus()

# What observations have been removed for this pillar?
removed = corpus.query(
    pillar="Conceptual Soundness",
    verdict="remove",
    model_type="ml_model",
)

# Acceptance rate by observation type
stats = corpus.summary_stats(model_name="Fraud Detection Model")
```

### Schema Extension Points

All major objects support `extra_metadata: dict[str, Any]` for agent-discovered patterns. If a field consistently appears across models, it can be promoted to a first-class field in a future version. Agents discover what's useful; humans decide when to formalize.

---

## Validation Engine

Profile-based compliance checking with a plugin registry.

### Running Validation

```python
from model_ledger.validate import validate

result = validate(model, version, profile="sr_11_7")
print(result)
# FAIL: Fraud Detection Model [sr_11_7]
#   Errors: 2
#   [ERROR] has_ipo_structure: Component tree missing required sections: {'Outputs'}
#   [ERROR] has_governance_document: No governance documents attached to this version.
```

### SR 11-7 Profile

Six rules, each with severity and actionable suggestions:

| Rule | Checks | Severity |
|------|--------|----------|
| `has_developers` | Model has at least one developer listed | error |
| `has_validator` | Model has an independent validator assigned | error |
| `validator_independence` | Validator is not also a developer | error |
| `has_ipo_structure` | Version tree has Inputs, Processing, Outputs | error |
| `has_governance_document` | At least one governance doc attached | error |
| `has_validation_schedule` | Next validation date set (error for high-tier, warning otherwise) | error/warning |

### Adding a New Profile

Implement a class with a `validate` method and register it:

```python
from model_ledger.validate.engine import register_profile, ValidationResult, Violation

@register_profile("eu_ai_act")
class EUAIActProfile:
    def validate(self, model, version) -> ValidationResult:
        result = ValidationResult(model_name=model.name, profile="eu_ai_act")
        # Check EU AI Act requirements...
        if not model.affected_populations:
            result.violations.append(Violation(
                rule_id="affected_populations",
                severity="error",
                message="EU AI Act requires listing affected populations.",
                suggestion="Set affected_populations=['...'] on the model.",
            ))
        return result
```

---

## Storage Backends

All backends implement the `InventoryBackend` protocol:

```python
@runtime_checkable
class InventoryBackend(Protocol):
    def save_model(self, model: Model) -> None: ...
    def get_model(self, name: str) -> Model | None: ...
    def list_models(self) -> list[Model]: ...
    def save_version(self, model_name: str, version: ModelVersion) -> None: ...
    def get_version(self, model_name: str, version: str) -> ModelVersion | None: ...
    def append_audit_event(self, event: AuditEvent) -> None: ...
    def get_audit_log(self, model_name: str, version: str | None = None) -> list[AuditEvent]: ...
```

### SQLiteBackend

Default backend. Enforces immutability — writing to a published version raises `ImmutableVersionError`. Audit events are append-only.

### MemoryBackend

In-memory implementation for testing. Same invariants, no persistence.

### Adding a Backend

Implement the protocol. PostgreSQL, DynamoDB, or any storage system that can enforce the immutability and audit trail invariants.

---

## Export

| Format | Status | Description |
|--------|--------|-------------|
| Audit packs | Planned (v0.2) | Examiner-ready bundles with model profile, findings, evidence |
| Gap reports | Planned (v0.2) | Missing fields with severity and remediation hints |
| Agent configs | Planned (v0.2) | Structured inputs for AI validation tools |
| JSON-LD | Planned (v0.3) | Machine-readable semantic export with linked data context |
| CycloneDX MBOM | Planned (v0.4) | Software supply chain integration for model components |

The `export/` module is scaffolded but not yet implemented. This is the primary focus for v0.2.

---

## Design Decisions

### Why Pydantic, not RDF

The data model is inspired by OWL ontology and SHACL constraints — the class hierarchy, structural invariants, and typed containment rules come from formal ontological design. But the implementation uses Pydantic, not RDF triplestores. Developers don't want to learn SPARQL to register a model. Pydantic gives us schema validation, JSON serialization, and Python IDE support with no additional dependencies beyond what most ML teams already have.

### Why a strict I/P/O tree

SR 11-7 defines a model as having input, processing, and output components. This isn't a suggestion — it's what examiners expect to see and what validators need to assess. The strict tree structure makes this explicit and enforceable, and gives AI agents a navigable structure they can traverse programmatically.

### Why immutable published versions

Regulatory defensibility. If a published version's tree can be silently modified, the audit trail is meaningless. Immutability means that when an examiner asks "what was the model structure at the time of validation?", the answer is unambiguous. All changes require a new version with a new audit event.

### Why assembler-first, SDK-next

Most organizations have models already in production. An SDK-only approach would require every model team to adopt model-ledger before it provides value. The assembler approach provides immediate value by reading from existing systems via adapters — no workflow changes required. The SDK path follows for new models and teams that want to register governance metadata in code.

### Why Apache-2.0

Maximizes adoption (no copyleft concerns for enterprise users) and includes patent protection.

### Why representation, not reasoning

model-ledger deliberately avoids encoding governance intelligence — it doesn't decide what observations mean, how to prioritize risks, or when a model is "good enough." It provides the structured data that lets agents discover those answers through computation. The validation rules (SR 11-7 profile) are regulatory minimums — the floor, not the ceiling. The real governance intelligence lives in agents and human reviewers who operate over the data model-ledger provides.

### When NOT to use model-ledger

- If you need a hosted platform with a dashboard UI out of the box — model-ledger is a library, not a platform.
- If your inventory has fewer than 5 models and no compliance requirements — a spreadsheet is fine.
- If you need real-time model monitoring or drift detection — model-ledger tracks governance metadata, not operational metrics.

---

## Contributing

model-ledger follows standard open-source contribution guidelines:

- **DCO sign-off** on all commits (`git commit --signoff`)
- **Conventional commits** for PR titles (`feat(sdk): add bulk registration`)
- **Fork and branch** workflow
- Python 3.10+, Pydantic 2.x, uv for package management, ruff for linting, pytest for testing

See CONTRIBUTING.md for build, test, and development instructions.

### Roadmap

- **v0.2**: Export layer, CLI tooling, adapter examples
- **v0.3**: JSON-LD export, additional compliance profiles (`eu_ai_act`, `nist_ai_rmf`)
- **v0.4**: CycloneDX MBOM export, contributor ecosystem growth
