---
title: Governance
description: A complete, auditable, point-in-time model inventory — the durable building blocks every model-risk regime asks for, mapped to model-ledger primitives.
---

# Governance

Model-risk regimes change their names and their numbers. What they *ask for* barely
changes. Strip away the acronyms and every regime — US banking, EU, insurance — wants
the same six things from your model inventory. model-ledger is built to produce them as
a byproduct of normal use, not as a separate compliance chore.

## What every regime actually asks for

| The durable need | What an examiner says | The model-ledger primitive |
|---|---|---|
| **Complete inventory** | "Show me *every* model — including the shadow ones." | Cross-platform [discovery & connectors](guides/connectors.md) — ML models, rules, and ETL as one graph |
| **Risk tiering** | "Which are high-materiality?" | `tier` on every [`ModelRef`](reference/index.md); business systems roll up as [composites](concepts/composite.md) |
| **Change control + audit trail** | "What changed, when, and who did it?" | Immutable, content-addressed [Snapshots](concepts/snapshot.md) — append-only, tamper-evident |
| **Dependency & lineage** | "How do these components feed each other?" | The [dependency graph](concepts/datanode.md), built from port matching |
| **Validation records** | "Prove this was validated, and find what wasn't." | `record_validation()` events live in the same immutable log |
| **Point-in-time reconstruction** | "Show me the inventory as it stood on December 31." | [`inventory_at(date)`](recipes/point-in-time.md) replays the log |

That's the whole compliance story: **nothing is overwritten, so the answer to "what was
true then?" is always reconstructable.**

## It falls out of normal use

```python
from model_ledger import Ledger

ledger = Ledger.from_sqlite("./inventory.db")

# Identity + risk tier — the minimum a regulator needs
ledger.register(
    name="credit_scorecard", owner="risk-team",
    model_type="ml_model", tier="high",
    purpose="Consumer credit decisioning",
)

# Validation outcomes are just events in the same immutable log
ledger.record("credit_scorecard", event="validated", actor="mrm-team",
              payload={"result": "pass", "validator": "second-line"})

# The full, ordered, tamper-evident history an examiner can replay
for snap in ledger.history("credit_scorecard"):
    print(snap.timestamp, snap.event_type, snap.actor)
```

## Frameworks it maps to

The primitives above satisfy the documentation and inventory expectations of the major
model-risk and AI-governance regimes:

- **US banking — SR 26‑2 / OCC Bulletin 2026‑13** (the 2026 revision that superseded
  SR 11‑7): tiered model inventory, materiality classification, lifecycle documentation,
  and validation status.
- **EU AI Act — Annex IV**: version-tracked technical documentation, component
  dependencies, and change history for high-risk systems.
- **NIST AI RMF** and **ISO/IEC 42001**: inventory, risk management, and lifecycle
  governance practices.

model-ledger ships **pluggable validation profiles** (`sr_11_7`, `eu_ai_act`,
`nist_ai_rmf`) that check a model's completeness against a framework, and you can add
your own — profiles are a plugin layer, not the core. Run them with
`model-ledger validate --profile <name>` (see the [CLI guide](guides/cli.md)).

!!! note "Framework-agnostic on purpose"
    model-ledger is a model inventory for *any* organization with deployed models — not
    a single-regulation tool. The frameworks above are examples of what the underlying
    capability is good for; they are a thin, swappable layer over a durable foundation.
    When a regulator renumbers a rule, you update a profile — not your inventory.
