"""Tests for InMemoryLedgerBackend — exercises the LedgerBackend protocol."""

from datetime import datetime, timezone

import pytest

from model_ledger.backends.ledger_memory import InMemoryLedgerBackend
from model_ledger.core.ledger_models import ModelRef, Snapshot, Tag


@pytest.fixture
def backend():
    return InMemoryLedgerBackend()


@pytest.fixture
def sample_model():
    return ModelRef(
        name="test-model", owner="team-a", model_type="ml_model",
        tier="high", purpose="testing",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class TestModelOperations:
    def test_save_and_get_model(self, backend, sample_model):
        backend.save_model(sample_model)
        result = backend.get_model(sample_model.model_hash)
        assert result is not None
        assert result.name == "test-model"

    def test_get_model_by_name(self, backend, sample_model):
        backend.save_model(sample_model)
        result = backend.get_model_by_name("test-model")
        assert result is not None
        assert result.model_hash == sample_model.model_hash

    def test_get_nonexistent_returns_none(self, backend):
        assert backend.get_model("nonexistent") is None

    def test_list_models_empty(self, backend):
        assert backend.list_models() == []

    def test_list_models_with_filters(self, backend, sample_model):
        backend.save_model(sample_model)
        assert len(backend.list_models(tier="high")) == 1
        assert len(backend.list_models(tier="low")) == 0

    def test_update_model(self, backend, sample_model):
        backend.save_model(sample_model)
        sample_model.status = "deprecated"
        backend.update_model(sample_model)
        result = backend.get_model(sample_model.model_hash)
        assert result.status == "deprecated"


class TestSnapshotOperations:
    def test_append_and_get_snapshot(self, backend, sample_model):
        backend.save_model(sample_model)
        snap = Snapshot(
            model_hash=sample_model.model_hash, actor="test",
            event_type="registered", payload={"name": "test-model"},
        )
        backend.append_snapshot(snap)
        result = backend.get_snapshot(snap.snapshot_hash)
        assert result is not None
        assert result.event_type == "registered"

    def test_list_snapshots(self, backend, sample_model):
        backend.save_model(sample_model)
        for i in range(3):
            backend.append_snapshot(Snapshot(
                model_hash=sample_model.model_hash, actor="test",
                event_type=f"event_{i}", payload={"i": i},
                timestamp=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
            ))
        snaps = backend.list_snapshots(sample_model.model_hash)
        assert len(snaps) == 3

    def test_list_snapshots_with_event_filter(self, backend, sample_model):
        backend.save_model(sample_model)
        backend.append_snapshot(Snapshot(
            model_hash=sample_model.model_hash, actor="test",
            event_type="registered", payload={},
        ))
        backend.append_snapshot(Snapshot(
            model_hash=sample_model.model_hash, actor="test",
            event_type="introspected", payload={"features": []},
        ))
        snaps = backend.list_snapshots(sample_model.model_hash, event_type="introspected")
        assert len(snaps) == 1

    def test_latest_snapshot(self, backend, sample_model):
        backend.save_model(sample_model)
        backend.append_snapshot(Snapshot(
            model_hash=sample_model.model_hash, actor="test",
            event_type="v1", payload={},
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ))
        backend.append_snapshot(Snapshot(
            model_hash=sample_model.model_hash, actor="test",
            event_type="v2", payload={},
            timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc),
        ))
        latest = backend.latest_snapshot(sample_model.model_hash)
        assert latest.event_type == "v2"


class TestTagOperations:
    def test_set_and_get_tag(self, backend, sample_model):
        backend.save_model(sample_model)
        tag = Tag(name="active", model_hash=sample_model.model_hash, snapshot_hash="snap1")
        backend.set_tag(tag)
        result = backend.get_tag(sample_model.model_hash, "active")
        assert result is not None
        assert result.snapshot_hash == "snap1"

    def test_move_tag(self, backend, sample_model):
        backend.save_model(sample_model)
        mh = sample_model.model_hash
        backend.set_tag(Tag(name="active", model_hash=mh, snapshot_hash="snap1"))
        backend.set_tag(Tag(name="active", model_hash=mh, snapshot_hash="snap2"))
        result = backend.get_tag(mh, "active")
        assert result.snapshot_hash == "snap2"

    def test_list_tags(self, backend, sample_model):
        backend.save_model(sample_model)
        backend.set_tag(Tag(name="v1", model_hash=sample_model.model_hash, snapshot_hash="s1"))
        backend.set_tag(Tag(name="active", model_hash=sample_model.model_hash, snapshot_hash="s1"))
        tags = backend.list_tags(sample_model.model_hash)
        assert len(tags) == 2


class TestListSnapshotsBefore:
    def test_filters_by_timestamp(self):
        backend = InMemoryLedgerBackend()
        model = ModelRef(
            name="m", owner="o", model_type="ml", tier="h", purpose="p",
        )
        backend.save_model(model)

        s1 = Snapshot(
            model_hash=model.model_hash, actor="x", event_type="registered",
            payload={}, timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        s2 = Snapshot(
            model_hash=model.model_hash, actor="x", event_type="scan_confirmed",
            payload={}, timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        s3 = Snapshot(
            model_hash=model.model_hash, actor="x", event_type="scan_confirmed",
            payload={}, timestamp=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
        backend.append_snapshot(s1)
        backend.append_snapshot(s2)
        backend.append_snapshot(s3)

        result = backend.list_snapshots_before(
            model.model_hash, datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        assert len(result) == 2

    def test_filters_by_event_type(self):
        backend = InMemoryLedgerBackend()
        model = ModelRef(
            name="m", owner="o", model_type="ml", tier="h", purpose="p",
        )
        backend.save_model(model)

        s1 = Snapshot(
            model_hash=model.model_hash, actor="x", event_type="registered",
            payload={}, timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        s2 = Snapshot(
            model_hash=model.model_hash, actor="x", event_type="not_found",
            payload={}, timestamp=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        backend.append_snapshot(s1)
        backend.append_snapshot(s2)

        result = backend.list_snapshots_before(
            model.model_hash,
            datetime(2026, 6, 1, tzinfo=timezone.utc),
            event_type="not_found",
        )
        assert len(result) == 1
        assert result[0].event_type == "not_found"

    def test_empty_when_no_snapshots_before(self):
        backend = InMemoryLedgerBackend()
        result = backend.list_snapshots_before(
            "nonexistent", datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        assert result == []
