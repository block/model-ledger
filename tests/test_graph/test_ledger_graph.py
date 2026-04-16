"""Tests for Ledger graph methods."""

import pytest

from model_ledger.core.exceptions import ModelNotFoundError
from model_ledger.graph.models import DataNode, DataPort
from model_ledger.sdk.ledger import Ledger


@pytest.fixture
def ledger():
    return Ledger()


class TestAdd:
    def test_add_single(self, ledger):
        ledger.add(
            DataNode("scorer", platform="ml_platform", inputs=["features"], outputs=["scores"])
        )
        assert ledger.get("scorer").name == "scorer"

    def test_add_list(self, ledger):
        ledger.add([DataNode("a", outputs=["t1"]), DataNode("b", inputs=["t1"])])
        assert len(ledger.list()) == 2

    def test_add_creates_snapshot(self, ledger):
        ledger.add(DataNode("scorer", platform="ml_platform", inputs=["f"], outputs=["s"]))
        snaps = ledger.history("scorer")
        discovered = [s for s in snaps if s.event_type == "discovered"]
        assert len(discovered) == 1
        assert discovered[0].payload["platform"] == "ml_platform"

    def test_add_idempotent(self, ledger):
        ledger.add(DataNode("scorer", outputs=["s"]))
        ledger.add(DataNode("scorer", outputs=["s"]))
        assert len(ledger.list()) == 1

    def test_add_content_hash_dedup_counters(self, ledger):
        node = DataNode("scorer", platform="ml_platform", outputs=["scores"])
        r1 = ledger.add(node)
        assert r1["added"] == 1
        assert r1["skipped"] == 0
        r2 = ledger.add(DataNode("scorer", platform="ml_platform", outputs=["scores"]))
        assert r2["added"] == 0
        assert r2["skipped"] == 1

    def test_add_detects_payload_change(self, ledger):
        ledger.add(DataNode("scorer", platform="ml_platform", outputs=["scores_v1"]))
        r2 = ledger.add(DataNode("scorer", platform="ml_platform", outputs=["scores_v2"]))
        assert r2["added"] == 1
        assert r2["skipped"] == 0

    def test_add_sets_last_seen(self, ledger):
        ledger.add(DataNode("scorer", platform="ml_platform", outputs=["scores"]))
        ref = ledger.get("scorer")
        assert ref.last_seen is not None

    def test_add_updates_last_seen_on_unchanged(self, ledger):
        ledger.add(DataNode("scorer", platform="ml_platform", outputs=["scores"]))
        first_seen = ledger.get("scorer").last_seen
        ledger.add(DataNode("scorer", platform="ml_platform", outputs=["scores"]))
        second_seen = ledger.get("scorer").last_seen
        assert second_seen >= first_seen

    def test_add_sets_change_detected(self, ledger):
        ledger.add(DataNode("scorer", platform="ml_platform", outputs=["scores"]))
        snap = [s for s in ledger.history("scorer") if s.event_type == "discovered"][0]
        assert "change_detected" in snap.payload

    def test_add_sets_change_occurred_when_provided(self, ledger):
        node = DataNode(
            "scorer",
            platform="ml_platform",
            outputs=["scores"],
            metadata={"source_updated_at": "2026-04-01T12:00:00"},
        )
        ledger.add(node)
        snap = [s for s in ledger.history("scorer") if s.event_type == "discovered"][0]
        assert snap.payload["change_occurred"] == "2026-04-01T12:00:00"

    def test_add_omits_change_occurred_when_absent(self, ledger):
        ledger.add(DataNode("scorer", platform="ml_platform", outputs=["scores"]))
        snap = [s for s in ledger.history("scorer") if s.event_type == "discovered"][0]
        assert "change_occurred" not in snap.payload

    def test_add_source_updated_at_does_not_affect_dedup(self, ledger):
        node1 = DataNode(
            "scorer",
            platform="ml_platform",
            outputs=["scores"],
            metadata={"source_updated_at": "2026-04-01T12:00:00"},
        )
        node2 = DataNode(
            "scorer",
            platform="ml_platform",
            outputs=["scores"],
            metadata={"source_updated_at": "2026-04-02T12:00:00"},
        )
        r1 = ledger.add(node1)
        r2 = ledger.add(node2)
        assert r1["added"] == 1
        assert r2["skipped"] == 1


class TestConnect:
    def test_matching_ports(self, ledger):
        ledger.add([DataNode("writer", outputs=["shared"]), DataNode("reader", inputs=["shared"])])
        result = ledger.connect()
        assert result["links_created"] >= 1
        deps = ledger.dependencies("reader", direction="upstream")
        assert any(d["model"].name == "writer" for d in deps)

    def test_arbitrary_schema_key_matching(self, ledger):
        """DataPort supports any schema key for matching, not just model_name."""
        ledger.add(
            [
                DataNode("producer", outputs=[DataPort("queue_slug", kind="alert_queue")]),
                DataNode("consumer", inputs=[DataPort("queue_slug", kind="alert_queue")]),
            ]
        )
        result = ledger.connect()
        assert result["links_created"] >= 1

    def test_no_match(self, ledger):
        ledger.add([DataNode("a", outputs=["x"]), DataNode("b", inputs=["y"])])
        assert ledger.connect()["links_created"] == 0

    def test_skips_self_refs(self, ledger):
        ledger.add(DataNode("a", inputs=["t"], outputs=["t"]))
        assert ledger.connect()["links_created"] == 0

    def test_shared_table_discriminator(self, ledger):
        ledger.add(
            [
                DataNode("w_a", outputs=[DataPort("shared", model_name="a")]),
                DataNode("w_b", outputs=[DataPort("shared", model_name="b")]),
                DataNode("r_a", inputs=[DataPort("shared", model_name="a")]),
            ]
        )
        ledger.connect()
        ups = [d["model"].name for d in ledger.dependencies("r_a", direction="upstream")]
        assert "w_a" in ups
        assert "w_b" not in ups

    def test_connect_skips_existing_edges(self, ledger):
        ledger.add([DataNode("writer", outputs=["t"]), DataNode("reader", inputs=["t"])])
        r1 = ledger.connect()
        assert r1["links_created"] >= 1
        r2 = ledger.connect()
        assert r2["links_created"] == 0
        assert r2["links_skipped"] >= 1

    def test_pipeline(self, ledger):
        ledger.add(
            [
                DataNode("seg", outputs=["segments"]),
                DataNode("score", inputs=["segments"], outputs=["scores"]),
                DataNode("alert", inputs=["scores"]),
            ]
        )
        ledger.connect()
        assert any(
            d["model"].name == "score" for d in ledger.dependencies("alert", direction="upstream")
        )
        assert any(
            d["model"].name == "seg" for d in ledger.dependencies("score", direction="upstream")
        )


class TestTrace:
    def test_ordered_pipeline(self, ledger):
        ledger.add(
            [
                DataNode("seg", outputs=["segments"]),
                DataNode("score", inputs=["segments"], outputs=["scores"]),
                DataNode("alert", inputs=["scores"]),
            ]
        )
        ledger.connect()
        assert ledger.trace("alert") == ["seg", "score", "alert"]

    def test_single_node(self, ledger):
        ledger.add(DataNode("standalone"))
        ledger.connect()
        assert ledger.trace("standalone") == ["standalone"]

    def test_not_found(self, ledger):
        with pytest.raises(ModelNotFoundError):
            ledger.trace("nonexistent")


class TestUpstreamDownstream:
    def test_upstream(self, ledger):
        ledger.add(
            [
                DataNode("a", outputs=["t1"]),
                DataNode("b", inputs=["t1"], outputs=["t2"]),
                DataNode("c", inputs=["t2"]),
            ]
        )
        ledger.connect()
        assert "a" in ledger.upstream("c")
        assert "b" in ledger.upstream("c")

    def test_downstream(self, ledger):
        ledger.add(
            [
                DataNode("a", outputs=["t1"]),
                DataNode("b", inputs=["t1"], outputs=["t2"]),
                DataNode("c", inputs=["t2"]),
            ]
        )
        ledger.connect()
        assert "b" in ledger.downstream("a")
        assert "c" in ledger.downstream("a")

    def test_upstream_empty(self, ledger):
        ledger.add(DataNode("root", outputs=["t1"]))
        ledger.connect()
        assert ledger.upstream("root") == []
