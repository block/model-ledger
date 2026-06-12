---
title: Guarantees & invariants
description: The properties model-ledger guarantees — append-only history, content-addressed snapshots, ordered history, point-in-time reconstruction — each property-tested in CI.
---

# Guarantees & invariants

A system of record is only as trustworthy as the properties it can promise. These are
model-ledger's — stated precisely, and **property-tested in CI** against randomized event
sequences (not just examples). Each guarantee below names the test that enforces it in
[`tests/test_invariants.py`](https://github.com/block/model-ledger/blob/main/tests/test_invariants.py).

## 1. Append-only

Snapshots are never deleted or modified. Recording an event only ever *appends*; the
history of a model never shrinks, and every prior snapshot persists byte-for-byte.

- **Contract:** for any sequence of `record()` calls, `len(history)` is non-decreasing and
  every previously seen `snapshot_hash` remains present and unchanged.
- **Enforced by:** `test_history_is_append_only`.

## 2. Content-addressed identity (tamper-evident)

A snapshot's hash is derived from its content — the model identity, the timestamp, and the
payload. Identical content always yields the same hash; any difference in content yields a
different hash. You cannot alter a recorded payload after the fact without the hash
diverging from what was stored.

- **Contract:** `snapshot_hash` is a deterministic function of `(model_hash, timestamp,
  payload)`; equal content ⇒ equal hash, differing content ⇒ differing hash.
- **Enforced by:** `test_snapshot_hash_is_deterministic_and_content_addressed`.

!!! note "Scope, stated honestly"
    The hash content-addresses each snapshot individually over `(model_hash, timestamp,
    payload)`. It is **not yet** a chained Merkle hash that folds in `parent_hash`,
    `actor`, and `event_type` — so the *sequence* is ordered and individually
    content-addressed, but not cryptographically linked end-to-end. Strengthening the hash
    to chain the full event is a deliberate future change (it alters existing hashes, so it
    will land as its own decision record), not an accidental gap.

## 3. Ordered history

`history()` returns a model's snapshots newest-first by timestamp — a stable, total order
you can rely on for "what happened, in what sequence."

- **Contract:** the returned list is sorted by `timestamp`, descending.
- **Enforced by:** `test_history_is_ordered_newest_first`.

## 4. Point-in-time reconstruction

Because nothing is overwritten, `inventory_at(t)` reconstructs the inventory as it stood at
time `t`: a model appears if and only if it existed at `t`.

- **Contract:** `inventory_at(t)` includes a model iff it was created at or before `t` (and
  its latest state as of `t` is not a removal).
- **Enforced by:** `test_point_in_time_reflects_only_models_that_existed`.

---

These four are the foundation the [event-log architecture](architecture.md) trades for —
see [ADR 0001](../adr/0001-event-log-not-a-registry.md). If a change to the SDK ever broke
one of them, the property tests would fail the build before it shipped.
