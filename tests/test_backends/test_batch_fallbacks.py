"""Tests for batch_fallbacks.py — fallback implementations using LedgerBackend protocol.

Each function is tested against InMemoryLedgerBackend with a known dataset.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from model_ledger.backends import batch_fallbacks
from model_ledger.backends.ledger_memory import InMemoryLedgerBackend
from model_ledger.core.ledger_models import ModelRef, Snapshot


def _make_model(name: str, owner: str = "risk-team") -> ModelRef:
    return ModelRef(
        name=name,
        owner=owner,
        model_type="ml_model",
        tier="high",
        purpose="testing",
    )


def _make_snapshot(
    model_hash: str,
    event_type: str = "registered",
    *,
    ts: datetime | None = None,
    actor: str = "test",
    source: str | None = None,
    payload: dict | None = None,
) -> Snapshot:
    return Snapshot(
        model_hash=model_hash,
        actor=actor,
        event_type=event_type,
        timestamp=ts or datetime.now(timezone.utc),
        source=source,
        payload=payload or {},
    )


@pytest.fixture
def backend() -> InMemoryLedgerBackend:
    """Backend with a known dataset of 3 models and multiple snapshots.

    Layout:
    - credit-scorecard: 3 snapshots (registered, discovered w/ platform, retrained)
    - fraud-detector:   2 snapshots (registered, discovered w/ source only)
    - empty-model:      0 snapshots (registered model, no events)

    Dependencies:
    - credit-scorecard depends_on fraud-detector (via snapshot)
    - fraud-detector has_dependent credit-scorecard (via snapshot)
    """
    b = InMemoryLedgerBackend()
    t0 = datetime(2026, 4, 1, tzinfo=timezone.utc)

    scorecard = _make_model("credit-scorecard")
    detector = _make_model("fraud-detector", owner="security-team")
    empty = _make_model("empty-model")
    b.save_model(scorecard)
    b.save_model(detector)
    b.save_model(empty)

    b.append_snapshot(
        _make_snapshot(
            scorecard.model_hash,
            "registered",
            ts=t0,
            payload={"name": "credit-scorecard"},
        )
    )
    b.append_snapshot(
        _make_snapshot(
            scorecard.model_hash,
            "discovered",
            ts=t0 + timedelta(hours=1),
            source="mlflow",
            payload={"platform": "mlflow"},
        )
    )
    b.append_snapshot(
        _make_snapshot(
            scorecard.model_hash,
            "retrained",
            ts=t0 + timedelta(hours=2),
            actor="pipeline",
            payload={"accuracy": 0.95},
        )
    )

    b.append_snapshot(
        _make_snapshot(
            detector.model_hash,
            "registered",
            ts=t0,
            payload={"name": "fraud-detector"},
        )
    )
    b.append_snapshot(
        _make_snapshot(
            detector.model_hash,
            "discovered",
            ts=t0 + timedelta(hours=1),
            source="sagemaker",
            payload={"features": ["amount", "frequency"]},
        )
    )

    b.append_snapshot(
        _make_snapshot(
            scorecard.model_hash,
            "depends_on",
            ts=t0 + timedelta(hours=3),
            payload={
                "upstream_hash": detector.model_hash,
                "upstream": "fraud-detector",
                "relationship": "feeds",
            },
        )
    )
    b.append_snapshot(
        _make_snapshot(
            detector.model_hash,
            "has_dependent",
            ts=t0 + timedelta(hours=3),
            payload={
                "downstream_hash": scorecard.model_hash,
                "downstream": "credit-scorecard",
                "relationship": "feeds",
            },
        )
    )

    return b


class TestCountAllSnapshots:
    def test_returns_correct_total(self, backend):
        total = batch_fallbacks.count_all_snapshots(backend)
        assert total == 7

    def test_empty_inventory(self):
        b = InMemoryLedgerBackend()
        assert batch_fallbacks.count_all_snapshots(b) == 0

    def test_models_with_no_snapshots_counted(self):
        b = InMemoryLedgerBackend()
        b.save_model(_make_model("lonely-model"))
        assert batch_fallbacks.count_all_snapshots(b) == 0


class TestModelSummaries:
    def test_returns_all_requested_hashes(self, backend):
        models = backend.list_models()
        hashes = [m.model_hash for m in models]
        result = batch_fallbacks.model_summaries(backend, hashes)

        for h in hashes:
            assert h in result

    def test_event_count_correct(self, backend):
        scorecard = backend.get_model_by_name("credit-scorecard")
        detector = backend.get_model_by_name("fraud-detector")

        result = batch_fallbacks.model_summaries(
            backend, [scorecard.model_hash, detector.model_hash]
        )

        assert result[scorecard.model_hash]["event_count"] == 4
        assert result[detector.model_hash]["event_count"] == 3

    def test_last_event_is_newest_timestamp(self, backend):
        scorecard = backend.get_model_by_name("credit-scorecard")
        result = batch_fallbacks.model_summaries(backend, [scorecard.model_hash])

        info = result[scorecard.model_hash]
        all_snaps = backend.list_snapshots(scorecard.model_hash)
        expected = max(s.timestamp for s in all_snaps)
        assert info["last_event"] == expected

    def test_platform_from_discovered_payload(self, backend):
        scorecard = backend.get_model_by_name("credit-scorecard")
        result = batch_fallbacks.model_summaries(backend, [scorecard.model_hash])

        assert result[scorecard.model_hash]["platform"] == "mlflow"

    def test_platform_from_source_fallback(self, backend):
        detector = backend.get_model_by_name("fraud-detector")
        result = batch_fallbacks.model_summaries(backend, [detector.model_hash])

        assert result[detector.model_hash]["platform"] == "sagemaker"

    def test_no_snapshots_returns_defaults(self, backend):
        empty = backend.get_model_by_name("empty-model")
        result = batch_fallbacks.model_summaries(backend, [empty.model_hash])

        info = result[empty.model_hash]
        assert info["last_event"] is None
        assert info["event_count"] == 0
        assert info["platform"] is None

    def test_empty_hash_list(self, backend):
        result = batch_fallbacks.model_summaries(backend, [])
        assert result == {}


class TestChangelogPage:
    def test_returns_all_events_unfiltered(self, backend):
        events, total = batch_fallbacks.changelog_page(backend)
        assert total == 7
        assert len(events) == 7

    def test_timestamp_desc_sort_order(self, backend):
        events, _ = batch_fallbacks.changelog_page(backend)
        timestamps = [e["timestamp"] for e in events]
        for i in range(len(timestamps) - 1):
            assert timestamps[i] >= timestamps[i + 1]

    def test_filter_by_event_type(self, backend):
        events, total = batch_fallbacks.changelog_page(backend, event_type="registered")
        assert total == 2
        for e in events:
            assert e["event_type"] == "registered"

    def test_filter_by_model_hash(self, backend):
        scorecard = backend.get_model_by_name("credit-scorecard")
        events, total = batch_fallbacks.changelog_page(backend, model_hash=scorecard.model_hash)
        assert total == 4  # registered + discovered + retrained + depends_on
        for e in events:
            assert e["model_hash"] == scorecard.model_hash

    def test_filter_by_since(self, backend):
        since = datetime(2026, 4, 1, 1, 30, tzinfo=timezone.utc)
        events, total = batch_fallbacks.changelog_page(backend, since=since)
        for e in events:
            assert e["timestamp"] >= since
        assert total == len(events)

    def test_filter_by_until(self, backend):
        until = datetime(2026, 4, 1, 0, 30, tzinfo=timezone.utc)
        events, total = batch_fallbacks.changelog_page(backend, until=until)
        for e in events:
            assert e["timestamp"] <= until

    def test_pagination_limit(self, backend):
        events, total = batch_fallbacks.changelog_page(backend, limit=3)
        assert len(events) == 3
        assert total == 7

    def test_pagination_offset(self, backend):
        page1, _ = batch_fallbacks.changelog_page(backend, limit=3, offset=0)
        page2, _ = batch_fallbacks.changelog_page(backend, limit=3, offset=3)
        # Pages should have different events
        p1_types = [(e["model_hash"], e["timestamp"]) for e in page1]
        p2_types = [(e["model_hash"], e["timestamp"]) for e in page2]
        assert p1_types != p2_types

    def test_event_dict_has_required_keys(self, backend):
        events, _ = batch_fallbacks.changelog_page(backend, limit=1)
        e = events[0]
        assert "model_hash" in e
        assert "model_name" in e
        assert "event_type" in e
        assert "timestamp" in e
        assert "actor" in e
        assert "summary" in e
        assert "payload" in e

    def test_empty_result_set(self, backend):
        events, total = batch_fallbacks.changelog_page(backend, event_type="nonexistent")
        assert total == 0
        assert events == []

    def test_combined_filters(self, backend):
        scorecard = backend.get_model_by_name("credit-scorecard")
        events, total = batch_fallbacks.changelog_page(
            backend,
            event_type="discovered",
            model_hash=scorecard.model_hash,
        )
        assert total == 1
        assert events[0]["event_type"] == "discovered"
        assert events[0]["model_hash"] == scorecard.model_hash


class TestBatchDependencies:
    def test_upstream_for_dependent_model(self, backend):
        scorecard = backend.get_model_by_name("credit-scorecard")
        deps = batch_fallbacks.batch_dependencies(backend, scorecard.model_hash)

        assert "upstream" in deps
        assert "downstream" in deps
        assert len(deps["upstream"]) == 1
        assert deps["upstream"][0]["model_name"] == "fraud-detector"
        assert deps["upstream"][0]["relationship"] == "feeds"

    def test_downstream_for_dependency_model(self, backend):
        detector = backend.get_model_by_name("fraud-detector")
        deps = batch_fallbacks.batch_dependencies(backend, detector.model_hash)

        assert len(deps["downstream"]) == 1
        assert deps["downstream"][0]["model_name"] == "credit-scorecard"

    def test_model_with_no_dependencies(self, backend):
        empty = backend.get_model_by_name("empty-model")
        deps = batch_fallbacks.batch_dependencies(backend, empty.model_hash)

        assert deps["upstream"] == []
        assert deps["downstream"] == []

    def test_dependency_dict_has_required_keys(self, backend):
        scorecard = backend.get_model_by_name("credit-scorecard")
        deps = batch_fallbacks.batch_dependencies(backend, scorecard.model_hash)

        for d in deps["upstream"]:
            assert "model_hash" in d
            assert "model_name" in d
            assert "relationship" in d


class TestBatchPlatforms:
    def test_platform_from_discovered_payload(self, backend):
        scorecard = backend.get_model_by_name("credit-scorecard")
        result = batch_fallbacks.batch_platforms(backend, [scorecard.model_hash])
        assert result[scorecard.model_hash] == "mlflow"

    def test_platform_from_source_fallback(self, backend):
        detector = backend.get_model_by_name("fraud-detector")
        result = batch_fallbacks.batch_platforms(backend, [detector.model_hash])
        assert result[detector.model_hash] == "sagemaker"

    def test_no_platform_returns_none(self, backend):
        empty = backend.get_model_by_name("empty-model")
        result = batch_fallbacks.batch_platforms(backend, [empty.model_hash])
        assert result[empty.model_hash] is None

    def test_multiple_models(self, backend):
        models = backend.list_models()
        hashes = [m.model_hash for m in models]
        result = batch_fallbacks.batch_platforms(backend, hashes)

        assert len(result) == 3
        for h in hashes:
            assert h in result

    def test_empty_hash_list(self, backend):
        result = batch_fallbacks.batch_platforms(backend, [])
        assert result == {}
