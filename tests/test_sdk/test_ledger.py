"""Tests for Ledger SDK — tool-shaped API for v0.3.0."""

from datetime import datetime, timezone

import pytest

from model_ledger.backends.ledger_memory import InMemoryLedgerBackend
from model_ledger.sdk.ledger import Ledger, ModelNotFoundError


@pytest.fixture
def ledger():
    return Ledger(backend=InMemoryLedgerBackend())


class TestRegister:
    def test_register_model(self, ledger):
        model = ledger.register(
            name="fraud-detector", owner="ml-team",
            model_type="ml_model", tier="high",
            purpose="Detect fraud",
        )
        assert model.name == "fraud-detector"
        assert model.model_hash

    def test_register_idempotent(self, ledger):
        m1 = ledger.register(
            name="a", owner="b", model_type="ml", tier="high", purpose="x",
        )
        m2 = ledger.register(
            name="a", owner="b", model_type="ml", tier="high", purpose="x",
        )
        assert m1.model_hash == m2.model_hash

    def test_register_creates_snapshot(self, ledger):
        model = ledger.register(
            name="a", owner="b", model_type="ml", tier="high", purpose="x",
        )
        snaps = ledger.history(model)
        assert len(snaps) == 1
        assert snaps[0].event_type == "registered"

    def test_register_with_model_origin(self, ledger):
        model = ledger.register(
            name="vendor-model", owner="vendor-co",
            model_type="vendor", tier="high",
            purpose="Credit scoring", model_origin="vendor",
        )
        assert model.model_origin == "vendor"


class TestRecord:
    def test_record_snapshot(self, ledger):
        model = ledger.register(
            name="a", owner="b", model_type="ml", tier="high", purpose="x",
        )
        snap = ledger.record(
            model, event="introspected", source="ml_platform",
            payload={"features": ["f1"]}, actor="test",
        )
        assert snap.event_type == "introspected"
        assert snap.payload == {"features": ["f1"]}

    def test_record_with_model_name(self, ledger):
        ledger.register(
            name="a", owner="b", model_type="ml", tier="high", purpose="x",
        )
        snap = ledger.record("a", event="tested", payload={}, actor="ci")
        assert snap.model_hash


class TestTag:
    def test_tag_model(self, ledger):
        model = ledger.register(
            name="a", owner="b", model_type="ml", tier="high", purpose="x",
        )
        snap = ledger.record(
            model, event="deployed", payload={}, actor="ci",
        )
        tag = ledger.tag(model, "active")
        assert tag.snapshot_hash == snap.snapshot_hash

    def test_tag_moves(self, ledger):
        model = ledger.register(
            name="a", owner="b", model_type="ml", tier="high", purpose="x",
        )
        ledger.record(model, event="v1", payload={}, actor="x")
        ledger.tag(model, "active")
        s2 = ledger.record(model, event="v2", payload={}, actor="x")
        tag = ledger.tag(model, "active")
        assert tag.snapshot_hash == s2.snapshot_hash


class TestQuery:
    def test_get_by_name(self, ledger):
        ledger.register(
            name="my-model", owner="team", model_type="ml",
            tier="high", purpose="x",
        )
        result = ledger.get("my-model")
        assert result.name == "my-model"

    def test_get_nonexistent_raises(self, ledger):
        with pytest.raises(ModelNotFoundError):
            ledger.get("nonexistent")

    def test_list_all(self, ledger):
        ledger.register(
            name="a", owner="t", model_type="ml", tier="high", purpose="x",
        )
        ledger.register(
            name="b", owner="t", model_type="heuristic", tier="low", purpose="y",
        )
        assert len(ledger.list()) == 2

    def test_list_filtered(self, ledger):
        ledger.register(
            name="a", owner="t", model_type="ml", tier="high", purpose="x",
        )
        ledger.register(
            name="b", owner="t", model_type="heuristic", tier="low", purpose="y",
        )
        assert len(ledger.list(model_type="ml")) == 1


class TestHistory:
    def test_history_returns_newest_first(self, ledger):
        model = ledger.register(
            name="a", owner="b", model_type="ml", tier="high", purpose="x",
        )
        ledger.record(
            model, event="introspected", payload={"v": 1}, actor="x",
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        ledger.record(
            model, event="validated", payload={"v": 2}, actor="x",
            timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        snaps = ledger.history(model)
        assert snaps[0].timestamp > snaps[1].timestamp

    def test_latest(self, ledger):
        model = ledger.register(
            name="a", owner="b", model_type="ml", tier="high", purpose="x",
        )
        ledger.record(
            model, event="v1", payload={}, actor="x",
            timestamp=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        ledger.record(
            model, event="v2", payload={}, actor="x",
            timestamp=datetime(2099, 1, 2, tzinfo=timezone.utc),
        )
        latest = ledger.latest(model)
        assert latest.event_type == "v2"


class TestDependencies:
    def test_link_dependency_creates_two_snapshots(self, ledger):
        ledger.register(
            name="feature-a", owner="team", model_type="signal",
            tier="unclassified", purpose="velocity feature",
        )
        ledger.register(
            name="fraud-model", owner="team", model_type="ml_model",
            tier="high", purpose="Detect fraud",
        )
        up_snap, down_snap = ledger.link_dependency(
            "feature-a", "fraud-model",
            relationship="consumes", actor="scanner:ml_platform",
        )
        assert up_snap.event_type == "has_dependent"
        assert up_snap.payload["downstream"] == "fraud-model"
        assert up_snap.payload["relationship"] == "consumes"
        assert down_snap.event_type == "depends_on"
        assert down_snap.payload["upstream"] == "feature-a"

    def test_dependencies_upstream(self, ledger):
        ledger.register(
            name="signal-x", owner="t", model_type="signal",
            tier="unclassified", purpose="x",
        )
        ledger.register(
            name="model-a", owner="t", model_type="ml_model",
            tier="high", purpose="x",
        )
        ledger.link_dependency(
            "signal-x", "model-a",
            relationship="consumes", actor="test",
        )
        deps = ledger.dependencies("model-a", direction="upstream")
        assert len(deps) == 1
        assert deps[0]["model"].name == "signal-x"
        assert deps[0]["relationship"] == "consumes"
        assert deps[0]["direction"] == "upstream"

    def test_dependencies_downstream(self, ledger):
        ledger.register(
            name="signal-x", owner="t", model_type="signal",
            tier="unclassified", purpose="x",
        )
        ledger.register(
            name="model-a", owner="t", model_type="ml_model",
            tier="high", purpose="x",
        )
        ledger.link_dependency(
            "signal-x", "model-a",
            relationship="consumes", actor="test",
        )
        deps = ledger.dependencies("signal-x", direction="downstream")
        assert len(deps) == 1
        assert deps[0]["model"].name == "model-a"

    def test_dependencies_both_directions(self, ledger):
        ledger.register(
            name="signal-x", owner="t", model_type="signal",
            tier="unclassified", purpose="x",
        )
        ledger.register(
            name="model-a", owner="t", model_type="ml_model",
            tier="high", purpose="x",
        )
        ledger.register(
            name="rule-b", owner="t", model_type="heuristic",
            tier="medium", purpose="x",
        )
        ledger.link_dependency("signal-x", "model-a", actor="test")
        ledger.link_dependency("model-a", "rule-b", actor="test")
        deps = ledger.dependencies("model-a", direction="both")
        assert len(deps) == 2
