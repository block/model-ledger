---
title: "ADR 0001 — Event log, not a registry"
description: Model the inventory as an append-only log of immutable snapshots rather than mutable current-state rows.
---

# ADR 0001 — Model the inventory as an event log, not a registry

**Status:** Accepted

## Context

A model inventory has to answer two kinds of question. Operators ask *"what is the current
state?"* Auditors and regulators ask *"show me the complete history of every change,
approval, and validation"* and *"what did the inventory look like on this past date?"*

A conventional registry stores current state and overwrites it on each change. It answers
the first question well and the second not at all — once a row is updated, the prior state
is gone, and there is no tamper-evident record that it ever existed.

## Decision

The inventory is an **append-only event log**. A model is a stable identity (`ModelRef`);
everything that happens to it is an immutable, content-addressed `Snapshot`. Current state
is a *projection* of the log; point-in-time state (`inventory_at`) is a replay of the log
up to a timestamp.

Content addressing (each snapshot's hash derives from its content) makes the chain
tamper-evident: you cannot alter history without the hashes diverging.

## Consequences

**Positive**

- History and point-in-time reconstruction are free — they're inherent to the structure,
  not a bolted-on audit table that can drift from the real data.
- The log *is* the audit trail; there is no separate logging system to keep in sync.
- Tamper-evidence comes from content addressing, which regulated use cases need.

**Negative (accepted)**

- More storage than last-write-wins, and reconstruction is a replay rather than a row read.
- Callers think in events, not in-place edits — a small conceptual shift.

## Alternatives considered

- **Mutable registry (rejected):** simplest writes, but structurally cannot answer the
  historical questions that are the entire point for governance.
- **Registry + a separate audit table (rejected):** two sources of truth that drift; the
  audit table is exactly the thing an examiner distrusts.

See [Snapshots & the event log](../concepts/snapshot.md) and [Architecture](../concepts/architecture.md).
