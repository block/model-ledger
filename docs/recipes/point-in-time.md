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
from datetime import datetime, timezone, timedelta
from model_ledger import Ledger

ledger = Ledger.from_sqlite("./inventory.db")

ledger.register(name="fraud_scoring", owner="risk-team",
                model_type="ml_model", tier="high",
                purpose="Card fraud detection")
ledger.record("fraud_scoring", event="retrained",
              payload={"accuracy": 0.94}, actor="ml-pipeline")

now = datetime.now(timezone.utc)

# The inventory as it stands now — fraud_scoring is present:
for ref in ledger.inventory_at(now):
    print(ref.name, ref.status)

# ...and as it stood a year ago — empty; the model didn't exist yet.
ledger.inventory_at(now - timedelta(days=365))
```

**Expected output.** `fraud_scoring active` for *now*, and nothing for a year ago —
the model didn't exist then. Pass any timestamp (e.g. an examiner's "as of December
31") and `inventory_at` replays the event log up to that moment, returning each model
with the `status` and metadata it carried *then* — not its state today. Nothing is
overwritten, so history is always reconstructable.

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
