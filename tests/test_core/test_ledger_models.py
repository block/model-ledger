"""Tests for v0.3.0 data models — ModelRef, Snapshot, Tag."""

from datetime import datetime, timezone

from model_ledger.core.ledger_models import ModelRef, Snapshot, Tag


class TestModelRef:
    def test_create_with_auto_hash(self):
        model = ModelRef(
            name="fraud-detector",
            owner="ml-team",
            model_type="ml_model",
            tier="high",
            purpose="Detect fraudulent transactions",
        )
        assert model.name == "fraud-detector"
        assert model.owner == "ml-team"
        assert model.model_hash  # auto-generated
        assert model.status == "active"
        assert model.created_at is not None

    def test_hash_is_deterministic(self):
        t = datetime(2026, 1, 1, tzinfo=timezone.utc)
        m1 = ModelRef(name="a", owner="b", model_type="ml", tier="high", purpose="x", created_at=t)
        m2 = ModelRef(name="a", owner="b", model_type="ml", tier="high", purpose="x", created_at=t)
        assert m1.model_hash == m2.model_hash

    def test_different_names_produce_different_hashes(self):
        t = datetime(2026, 1, 1, tzinfo=timezone.utc)
        m1 = ModelRef(name="a", owner="b", model_type="ml", tier="high", purpose="x", created_at=t)
        m2 = ModelRef(name="c", owner="b", model_type="ml", tier="high", purpose="x", created_at=t)
        assert m1.model_hash != m2.model_hash

    def test_json_serializable(self):
        model = ModelRef(name="test", owner="owner", model_type="ml", tier="low", purpose="testing")
        data = model.model_dump()
        assert isinstance(data, dict)
        assert data["name"] == "test"
        roundtrip = ModelRef.model_validate(data)
        assert roundtrip.model_hash == model.model_hash

    def test_hash_length_is_32(self):
        model = ModelRef(
            name="test",
            owner="owner",
            model_type="ml",
            tier="high",
            purpose="testing",
        )
        assert len(model.model_hash) == 32

    def test_model_origin_defaults_to_internal(self):
        model = ModelRef(
            name="test",
            owner="owner",
            model_type="ml",
            tier="high",
            purpose="testing",
        )
        assert model.model_origin == "internal"

    def test_model_origin_can_be_set(self):
        model = ModelRef(
            name="vendor-model",
            owner="vendor-team",
            model_type="vendor",
            tier="high",
            purpose="Credit scoring",
            model_origin="vendor",
        )
        assert model.model_origin == "vendor"


class TestSnapshot:
    def test_create_snapshot(self):
        snapshot = Snapshot(
            model_hash="abc123",
            actor="ml_platform-watcher",
            event_type="introspected",
            source="ml_platform",
            payload={"algorithm": "XGBoost", "features": ["f1", "f2"]},
        )
        assert snapshot.snapshot_hash  # auto-computed
        assert snapshot.model_hash == "abc123"
        assert snapshot.event_type == "introspected"
        assert snapshot.parent_hash is None
        assert snapshot.tags == {}

    def test_snapshot_hash_includes_timestamp(self):
        s1 = Snapshot(
            model_hash="abc",
            actor="x",
            event_type="test",
            payload={"a": 1},
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        s2 = Snapshot(
            model_hash="abc",
            actor="x",
            event_type="test",
            payload={"a": 1},
            timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        assert s1.snapshot_hash != s2.snapshot_hash

    def test_snapshot_json_serializable(self):
        snapshot = Snapshot(
            model_hash="abc",
            actor="test",
            event_type="registered",
            payload={"name": "test-model"},
        )
        data = snapshot.model_dump()
        assert isinstance(data["payload"], dict)
        roundtrip = Snapshot.model_validate(data)
        assert roundtrip.snapshot_hash == snapshot.snapshot_hash

    def test_snapshot_hash_length_is_32(self):
        snapshot = Snapshot(
            model_hash="a" * 32,
            actor="test",
            event_type="registered",
            payload={"x": 1},
        )
        assert len(snapshot.snapshot_hash) == 32


class TestTag:
    def test_create_tag(self):
        tag = Tag(name="v3", model_hash="abc123", snapshot_hash="def456")
        assert tag.name == "v3"
        assert tag.updated_at is not None

    def test_tag_json_serializable(self):
        tag = Tag(name="active", model_hash="abc", snapshot_hash="def")
        data = tag.model_dump()
        roundtrip = Tag.model_validate(data)
        assert roundtrip.name == "active"
