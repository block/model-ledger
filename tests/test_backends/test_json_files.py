"""Tests for JsonFileLedgerBackend."""

import json
import os
import tempfile
from datetime import datetime, timezone

import pytest

from model_ledger.backends.json_files import JsonFileLedgerBackend
from model_ledger.core.ledger_models import ModelRef, Snapshot, Tag


@pytest.fixture
def backend_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def backend(backend_dir):
    return JsonFileLedgerBackend(backend_dir)


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

    def test_list_snapshots_sorted_descending(self, backend):
        """Snapshots are returned newest-first."""
        m = _make_model()
        backend.save_model(m)
        s1 = Snapshot(
            model_hash=m.model_hash,
            actor="test",
            event_type="registered",
            payload={"order": 1},
            timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        s2 = Snapshot(
            model_hash=m.model_hash,
            actor="test",
            event_type="discovered",
            payload={"order": 2},
            timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        backend.append_snapshot(s1)
        backend.append_snapshot(s2)
        snaps = backend.list_snapshots(m.model_hash)
        assert snaps[0].timestamp > snaps[1].timestamp

    def test_latest_snapshot(self, backend):
        m = _make_model()
        backend.save_model(m)
        s1 = Snapshot(
            model_hash=m.model_hash,
            actor="test",
            event_type="registered",
            payload={"v": 1},
            timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        s2 = Snapshot(
            model_hash=m.model_hash,
            actor="test",
            event_type="discovered",
            payload={"v": 2},
            timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        backend.append_snapshot(s1)
        backend.append_snapshot(s2)
        latest = backend.latest_snapshot(m.model_hash)
        assert latest is not None
        assert latest.payload["v"] == 2

    def test_latest_snapshot_empty(self, backend):
        assert backend.latest_snapshot("nonexistent") is None

    def test_list_snapshots_before(self, backend):
        m = _make_model()
        backend.save_model(m)
        s1 = Snapshot(
            model_hash=m.model_hash,
            actor="test",
            event_type="registered",
            payload={},
            timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        s2 = Snapshot(
            model_hash=m.model_hash,
            actor="test",
            event_type="discovered",
            payload={},
            timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        backend.append_snapshot(s1)
        backend.append_snapshot(s2)
        before = datetime(2025, 3, 1, tzinfo=timezone.utc)
        results = backend.list_snapshots_before(m.model_hash, before)
        assert len(results) == 1
        assert results[0].snapshot_hash == s1.snapshot_hash

    def test_list_snapshots_before_with_event_type(self, backend):
        m = _make_model()
        backend.save_model(m)
        s1 = Snapshot(
            model_hash=m.model_hash,
            actor="test",
            event_type="registered",
            payload={},
            timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        s2 = Snapshot(
            model_hash=m.model_hash,
            actor="test",
            event_type="discovered",
            payload={},
            timestamp=datetime(2025, 2, 1, tzinfo=timezone.utc),
        )
        backend.append_snapshot(s1)
        backend.append_snapshot(s2)
        before = datetime(2025, 6, 1, tzinfo=timezone.utc)
        results = backend.list_snapshots_before(
            m.model_hash,
            before,
            event_type="registered",
        )
        assert len(results) == 1
        assert results[0].event_type == "registered"


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

    def test_latest_via_tag(self, backend):
        """latest_snapshot with a tag resolves through the tag pointer."""
        m = _make_model()
        backend.save_model(m)
        s1 = _make_snapshot(m.model_hash, "registered")
        s2 = _make_snapshot(m.model_hash, "discovered")
        backend.append_snapshot(s1)
        backend.append_snapshot(s2)
        backend.set_tag(Tag(name="pinned", model_hash=m.model_hash, snapshot_hash=s1.snapshot_hash))
        result = backend.latest_snapshot(m.model_hash, tag="pinned")
        assert result is not None
        assert result.snapshot_hash == s1.snapshot_hash

    def test_get_tag_missing(self, backend):
        assert backend.get_tag("nonexistent", "v1") is None


class TestPersistence:
    def test_data_survives_reopen(self, backend_dir):
        backend1 = JsonFileLedgerBackend(backend_dir)
        m = _make_model()
        backend1.save_model(m)
        backend1.append_snapshot(_make_snapshot(m.model_hash))
        backend1.set_tag(
            Tag(
                name="v1",
                model_hash=m.model_hash,
                snapshot_hash=_make_snapshot(m.model_hash).snapshot_hash,
            )
        )
        del backend1

        backend2 = JsonFileLedgerBackend(backend_dir)
        assert backend2.get_model_by_name("test-model") is not None
        assert len(backend2.list_snapshots(m.model_hash)) == 1
        assert len(backend2.list_tags(m.model_hash)) == 1


class TestReadableJson:
    def test_model_file_is_valid_json(self, backend, backend_dir):
        m = _make_model()
        backend.save_model(m)
        # Find the model file and read it with json.load
        models_dir = os.path.join(backend_dir, "models")
        files = os.listdir(models_dir)
        assert len(files) == 1
        with open(os.path.join(models_dir, files[0])) as f:
            data = json.load(f)
        assert data["name"] == "test-model"
        assert data["owner"] == "alice"
        assert data["model_hash"] == m.model_hash

    def test_snapshot_file_is_valid_json(self, backend, backend_dir):
        m = _make_model()
        backend.save_model(m)
        s = _make_snapshot(m.model_hash)
        backend.append_snapshot(s)
        snap_dir = os.path.join(backend_dir, "snapshots")
        files = os.listdir(snap_dir)
        assert len(files) == 1
        with open(os.path.join(snap_dir, files[0])) as f:
            data = json.load(f)
        assert data["snapshot_hash"] == s.snapshot_hash
        assert data["payload"]["key"] == "value"

    def test_tag_file_is_valid_json(self, backend, backend_dir):
        m = _make_model()
        backend.save_model(m)
        s = _make_snapshot(m.model_hash)
        backend.append_snapshot(s)
        tag = Tag(name="v1", model_hash=m.model_hash, snapshot_hash=s.snapshot_hash)
        backend.set_tag(tag)
        tag_file = os.path.join(backend_dir, "tags", m.model_hash, "v1.json")
        assert os.path.exists(tag_file)
        with open(tag_file) as f:
            data = json.load(f)
        assert data["name"] == "v1"
        assert data["snapshot_hash"] == s.snapshot_hash


class TestFilenamesSanitized:
    def test_model_with_special_chars(self, backend):
        m = _make_model("my model/v1\\test")
        backend.save_model(m)
        result = backend.get_model_by_name("my model/v1\\test")
        assert result is not None
        assert result.name == "my model/v1\\test"


class TestLedgerIntegration:
    def test_full_workflow(self, backend_dir):
        from model_ledger import Ledger
        from model_ledger.graph.models import DataNode

        backend = JsonFileLedgerBackend(backend_dir)
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
