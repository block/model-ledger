"""Tests for SQLiteLedgerBackend."""
import os
import tempfile
import pytest
from datetime import datetime, timezone
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
        name=name, owner="alice", model_type="ml_model",
        tier="high", purpose="testing", status="active",
    )


def _make_snapshot(model_hash, event_type="discovered"):
    return Snapshot(
        model_hash=model_hash, actor="test",
        event_type=event_type, payload={"key": "value"},
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


class TestLedgerIntegration:
    def test_full_workflow(self, db_path):
        from model_ledger import Ledger
        from model_ledger.graph.models import DataNode

        backend = SQLiteLedgerBackend(db_path)
        ledger = Ledger(backend)

        ledger.add([
            DataNode("writer", outputs=["shared_table"]),
            DataNode("reader", inputs=["shared_table"]),
        ])
        ledger.connect()

        assert len(ledger.list()) == 2
        trace = ledger.trace("reader")
        assert "writer" in trace
