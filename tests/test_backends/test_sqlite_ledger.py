"""Tests for SQLiteLedgerBackend."""

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from model_ledger.backends import batch_fallbacks
from model_ledger.backends.sqlite_ledger import SQLiteLedgerBackend
from model_ledger.core.ledger_models import ModelRef, Snapshot, Tag


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def backend(db_path):
    return SQLiteLedgerBackend(db_path)


def _make_model(name="test-model"):
    return ModelRef(
        name=name,
        owner="alice",
        model_type="ml_model",
        tier="high",
        purpose="testing",
        status="active",
    )


def _make_snapshot(model_hash, event_type="discovered"):
    return Snapshot(
        model_hash=model_hash,
        actor="test",
        event_type=event_type,
        payload={"key": "value"},
    )


class TestModels:
    def test_save_and_get(self, backend):
        m = _make_model()
        backend.save_model(m)
        result = backend.get_model(m.model_hash)
        assert result is not None
        assert result.name == "test-model"
        assert result.owner == "alice"

    def test_get_by_name(self, backend):
        m = _make_model()
        backend.save_model(m)
        result = backend.get_model_by_name("test-model")
        assert result is not None
        assert result.model_hash == m.model_hash

    def test_get_missing(self, backend):
        assert backend.get_model("nonexistent") is None
        assert backend.get_model_by_name("nonexistent") is None

    def test_list_models(self, backend):
        backend.save_model(_make_model("a"))
        backend.save_model(_make_model("b"))
        assert len(backend.list_models()) == 2

    def test_list_models_with_filter(self, backend):
        backend.save_model(_make_model("a"))
        backend.save_model(_make_model("b"))
        result = backend.list_models(name="a")
        assert len(result) == 1
        assert result[0].name == "a"

    def test_update_model(self, backend):
        m = _make_model()
        backend.save_model(m)
        m.status = "deprecated"
        backend.update_model(m)
        result = backend.get_model(m.model_hash)
        assert result.status == "deprecated"


class TestSnapshots:
    def test_append_and_get(self, backend):
        m = _make_model()
        backend.save_model(m)
        s = _make_snapshot(m.model_hash)
        backend.append_snapshot(s)
        result = backend.get_snapshot(s.snapshot_hash)
        assert result is not None
        assert result.payload == {"key": "value"}

    def test_list_snapshots(self, backend):
        m = _make_model()
        backend.save_model(m)
        backend.append_snapshot(_make_snapshot(m.model_hash, "registered"))
        backend.append_snapshot(_make_snapshot(m.model_hash, "discovered"))
        snaps = backend.list_snapshots(m.model_hash)
        assert len(snaps) == 2

    def test_list_snapshots_with_filter(self, backend):
        m = _make_model()
        backend.save_model(m)
        backend.append_snapshot(_make_snapshot(m.model_hash, "registered"))
        backend.append_snapshot(_make_snapshot(m.model_hash, "discovered"))
        snaps = backend.list_snapshots(m.model_hash, event_type="discovered")
        assert len(snaps) == 1
        assert snaps[0].event_type == "discovered"

    def test_latest_snapshot(self, backend):
        m = _make_model()
        backend.save_model(m)
        backend.append_snapshot(_make_snapshot(m.model_hash, "registered"))
        backend.append_snapshot(_make_snapshot(m.model_hash, "discovered"))
        latest = backend.latest_snapshot(m.model_hash)
        assert latest is not None

    def test_list_all_snapshots(self, backend):
        m1 = _make_model("a")
        m2 = _make_model("b")
        backend.save_model(m1)
        backend.save_model(m2)
        backend.append_snapshot(_make_snapshot(m1.model_hash, "discovered"))
        backend.append_snapshot(_make_snapshot(m2.model_hash, "discovered"))
        all_snaps = backend.list_all_snapshots(event_type="discovered")
        assert len(all_snaps) == 2


class TestTags:
    def test_set_and_get(self, backend):
        m = _make_model()
        backend.save_model(m)
        s = _make_snapshot(m.model_hash)
        backend.append_snapshot(s)
        tag = Tag(name="latest", model_hash=m.model_hash, snapshot_hash=s.snapshot_hash)
        backend.set_tag(tag)
        result = backend.get_tag(m.model_hash, "latest")
        assert result is not None
        assert result.snapshot_hash == s.snapshot_hash

    def test_list_tags(self, backend):
        m = _make_model()
        backend.save_model(m)
        s = _make_snapshot(m.model_hash)
        backend.append_snapshot(s)
        backend.set_tag(Tag(name="v1", model_hash=m.model_hash, snapshot_hash=s.snapshot_hash))
        backend.set_tag(Tag(name="v2", model_hash=m.model_hash, snapshot_hash=s.snapshot_hash))
        assert len(backend.list_tags(m.model_hash)) == 2


class TestPersistence:
    def test_data_survives_reopen(self, db_path):
        backend1 = SQLiteLedgerBackend(db_path)
        m = _make_model()
        backend1.save_model(m)
        backend1.append_snapshot(_make_snapshot(m.model_hash))
        del backend1

        backend2 = SQLiteLedgerBackend(db_path)
        assert backend2.get_model_by_name("test-model") is not None
        assert len(backend2.list_snapshots(m.model_hash)) == 1


class TestBatchMethodEquivalence:
    """Verify SQLite optimized batch methods return identical results to fallbacks."""

    @pytest.fixture
    def populated_backend(self, db_path):
        """Backend with models, snapshots, and dependencies for batch tests."""
        backend = SQLiteLedgerBackend(db_path)
        t0 = datetime(2026, 4, 1, tzinfo=timezone.utc)

        scorecard = _make_model("credit-scorecard")
        detector = _make_model("fraud-detector")
        empty = _make_model("empty-model")
        backend.save_model(scorecard)
        backend.save_model(detector)
        backend.save_model(empty)

        backend.append_snapshot(
            Snapshot(
                model_hash=scorecard.model_hash,
                actor="test",
                event_type="registered",
                timestamp=t0,
                payload={"name": "credit-scorecard"},
            )
        )
        backend.append_snapshot(
            Snapshot(
                model_hash=scorecard.model_hash,
                actor="test",
                event_type="discovered",
                timestamp=t0 + timedelta(hours=1),
                source="mlflow",
                payload={"platform": "mlflow"},
            )
        )
        backend.append_snapshot(
            Snapshot(
                model_hash=scorecard.model_hash,
                actor="pipeline",
                event_type="retrained",
                timestamp=t0 + timedelta(hours=2),
                payload={"accuracy": 0.95},
            )
        )
        backend.append_snapshot(
            Snapshot(
                model_hash=detector.model_hash,
                actor="test",
                event_type="registered",
                timestamp=t0,
                payload={"name": "fraud-detector"},
            )
        )
        backend.append_snapshot(
            Snapshot(
                model_hash=detector.model_hash,
                actor="test",
                event_type="discovered",
                timestamp=t0 + timedelta(hours=1),
                source="sagemaker",
                payload={"features": ["amount"]},
            )
        )
        backend.append_snapshot(
            Snapshot(
                model_hash=scorecard.model_hash,
                actor="test",
                event_type="depends_on",
                timestamp=t0 + timedelta(hours=3),
                payload={
                    "upstream_hash": detector.model_hash,
                    "upstream": "fraud-detector",
                    "relationship": "feeds",
                },
            )
        )
        backend.append_snapshot(
            Snapshot(
                model_hash=detector.model_hash,
                actor="test",
                event_type="has_dependent",
                timestamp=t0 + timedelta(hours=3),
                payload={
                    "downstream_hash": scorecard.model_hash,
                    "downstream": "credit-scorecard",
                    "relationship": "feeds",
                },
            )
        )
        return backend

    def test_count_all_snapshots_matches_fallback(self, populated_backend):
        optimized = populated_backend.count_all_snapshots()
        fallback = batch_fallbacks.count_all_snapshots(populated_backend)
        assert optimized == fallback

    def test_model_summaries_matches_fallback(self, populated_backend):
        hashes = [m.model_hash for m in populated_backend.list_models()]
        optimized = populated_backend.model_summaries(hashes)
        fallback = batch_fallbacks.model_summaries(populated_backend, hashes)
        assert optimized == fallback

    def test_changelog_page_matches_fallback(self, populated_backend):
        optimized_events, optimized_total = populated_backend.changelog_page()
        fallback_events, fallback_total = batch_fallbacks.changelog_page(populated_backend)
        assert optimized_total == fallback_total
        opt_set = {(e["model_hash"], e["event_type"], e["timestamp"]) for e in optimized_events}
        fb_set = {(e["model_hash"], e["event_type"], e["timestamp"]) for e in fallback_events}
        assert opt_set == fb_set

    def test_changelog_page_filtered_matches_fallback(self, populated_backend):
        scorecard = populated_backend.get_model_by_name("credit-scorecard")
        opt_events, opt_total = populated_backend.changelog_page(
            event_type="discovered",
            model_hash=scorecard.model_hash,
        )
        fb_events, fb_total = batch_fallbacks.changelog_page(
            populated_backend,
            event_type="discovered",
            model_hash=scorecard.model_hash,
        )
        assert opt_total == fb_total
        assert len(opt_events) == len(fb_events)

    def test_batch_dependencies_matches_fallback(self, populated_backend):
        scorecard = populated_backend.get_model_by_name("credit-scorecard")
        optimized = populated_backend.batch_dependencies(scorecard.model_hash)
        fallback = batch_fallbacks.batch_dependencies(populated_backend, scorecard.model_hash)
        assert optimized == fallback

    def test_batch_platforms_matches_fallback(self, populated_backend):
        hashes = [m.model_hash for m in populated_backend.list_models()]
        optimized = populated_backend.batch_platforms(hashes)
        fallback = batch_fallbacks.batch_platforms(populated_backend, hashes)
        assert optimized == fallback


class TestLedgerIntegration:
    def test_full_workflow(self, db_path):
        from model_ledger import Ledger
        from model_ledger.graph.models import DataNode

        backend = SQLiteLedgerBackend(db_path)
        ledger = Ledger(backend)

        ledger.add(
            [
                DataNode("writer", outputs=["shared_table"]),
                DataNode("reader", inputs=["shared_table"]),
            ]
        )
        ledger.connect()

        assert len(ledger.list()) == 2
        trace = ledger.trace("reader")
        assert "writer" in trace
