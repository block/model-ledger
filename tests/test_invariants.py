"""Property-based tests for model-ledger's core guarantees.

These prove the claims the event-log architecture rests on — not by example, but
by generating random event sequences with Hypothesis and asserting the invariants
hold. They are the executable counterpart to the Guarantees documentation
(docs/concepts/guarantees.md), which cites this module by name.

Invariants covered:
  1. Append-only       — history never shrinks; prior snapshots persist unchanged.
  2. Content-addressed — a snapshot's hash is deterministic from its content, and
                         differing content yields a differing hash (tamper-evident).
  3. Ordered history   — history() returns snapshots newest-first by timestamp.
  4. Point-in-time     — inventory_at(t) reflects only models that existed at t.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from model_ledger import Ledger
from model_ledger.backends.ledger_memory import InMemoryLedgerBackend
from model_ledger.core.ledger_models import Snapshot

# Safe alphabets keep the focus on the invariants, not unicode-encoding edge cases.
_TOKEN = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=12)
_VALUES = st.one_of(st.integers(), st.booleans(), st.none(), st.text(max_size=16))
_PAYLOADS = st.dictionaries(_TOKEN, _VALUES, max_size=4)
_EVENT_SEQ = st.lists(st.tuples(_TOKEN, _PAYLOADS), max_size=10)


def _ledger() -> Ledger:
    return Ledger(backend=InMemoryLedgerBackend())


def _register(ledger: Ledger, name: str = "m") -> None:
    ledger.register(name=name, owner="owner", model_type="ml_model", tier="high", purpose="p")


@settings(deadline=None, max_examples=40)
@given(seq=_EVENT_SEQ)
def test_history_is_append_only(seq: list[tuple[str, dict]]) -> None:
    """Recording events never deletes or mutates prior snapshots; history only grows."""
    ledger = _ledger()
    _register(ledger)
    prev_len = len(ledger.history("m"))
    seen = {s.snapshot_hash for s in ledger.history("m")}
    for event, payload in seq:
        ledger.record("m", event=event, payload=payload, actor="actor")
        history = ledger.history("m")
        assert len(history) >= prev_len  # never shrinks
        assert seen <= {s.snapshot_hash for s in history}  # prior snapshots persist unchanged
        prev_len = len(history)
        seen = {s.snapshot_hash for s in history}


@settings(deadline=None, max_examples=60)
@given(
    p1=_PAYLOADS,
    p2=_PAYLOADS,
    ts=st.datetimes(timezones=st.just(timezone.utc)),
    model_hash=_TOKEN,
)
def test_snapshot_hash_is_deterministic_and_content_addressed(
    p1: dict, p2: dict, ts: datetime, model_hash: str
) -> None:
    """Same content → same hash (deterministic); different content → different hash."""
    a = Snapshot(model_hash=model_hash, timestamp=ts, actor="x", event_type="e", payload=p1)
    b = Snapshot(model_hash=model_hash, timestamp=ts, actor="x", event_type="e", payload=p1)
    assert a.snapshot_hash == b.snapshot_hash and a.snapshot_hash != ""

    dumps = lambda p: json.dumps(p, sort_keys=True, default=str)  # noqa: E731
    assume(dumps(p1) != dumps(p2))  # only assert sensitivity when content actually differs
    c = Snapshot(model_hash=model_hash, timestamp=ts, actor="x", event_type="e", payload=p2)
    assert c.snapshot_hash != a.snapshot_hash


@settings(deadline=None, max_examples=40)
@given(seq=_EVENT_SEQ)
def test_history_is_ordered_newest_first(seq: list[tuple[str, dict]]) -> None:
    """history() returns snapshots in non-increasing timestamp order."""
    ledger = _ledger()
    _register(ledger)
    for event, payload in seq:
        ledger.record("m", event=event, payload=payload, actor="actor")
    timestamps = [s.timestamp for s in ledger.history("m")]
    assert timestamps == sorted(timestamps, reverse=True)


@settings(deadline=None, max_examples=30)
@given(names=st.lists(_TOKEN, unique=True, max_size=5))
def test_point_in_time_reflects_only_models_that_existed(names: list[str]) -> None:
    """inventory_at(t) includes a model iff it existed at t."""
    ledger = _ledger()
    a_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
    for name in names:
        _register(ledger, name)
    soon = datetime.now(timezone.utc) + timedelta(seconds=1)

    assert {m.name for m in ledger.inventory_at(soon)} == set(names)  # all exist now
    assert ledger.inventory_at(a_day_ago) == []  # none existed yesterday
