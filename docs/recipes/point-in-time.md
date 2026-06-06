---
title: "Recipe: Point-in-time inventory"
description: Reconstruct exactly which models were active, and in what state, on any past date — straight from the immutable event log.
---

# <span class="recipe-num">Recipe № 2</span> &nbsp; Point-in-time inventory

**Problem.** An examiner asks: *"Show me your model inventory as it stood on December
31."* A registry that overwrites state can't answer this. An event log can.

**Approach.** Because every change is an immutable [Snapshot](../concepts/snapshot.md),
the inventory at any date is just a replay of the log up to that moment.
`inventory_at()` does it for you.

```python
from datetime import datetime
from model_ledger import Ledger

ledger = Ledger.from_sqlite("./inventory.db")

# Register and evolve a model over time
ledger.register(name="fraud_scoring", owner="risk-team",
                model_type="ml_model", tier="high",
                purpose="Card fraud detection")
ledger.record("fraud_scoring", "retrained", payload={"accuracy": 0.94})
ledger.record("fraud_scoring", "deprecated")

# What did the inventory look like at year-end?
year_end = ledger.inventory_at(datetime(2025, 12, 31))
for ref in year_end:
    print(ref.name, ref.status)
```

**Expected output.** Every model that existed on that date, with the `status` and
metadata it carried *then* — not its state today. A model deprecated in 2026 still
shows as active in a 2025 snapshot.

## Why this matters

| Question an auditor asks | Registry (mutable) | Ledger (event log) |
|---|---|---|
| What's the current state? | ✅ | ✅ |
| What did it look like 6 months ago? | ❌ overwritten | ✅ replay the log |
| When exactly did this change, and who did it? | ❌ | ✅ `history()` |
| Prove nothing was edited after the fact | ❌ | ✅ content-addressed snapshots |

## Pair with history

For one model's full timeline:

```python
for snap in ledger.history("fraud_scoring"):
    print(snap.timestamp, snap.event_type, snap.actor)
```

Every line is immutable and ordered. That timeline *is* the audit trail — no separate
logging system to keep in sync.
