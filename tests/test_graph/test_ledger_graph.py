"""Tests for Ledger graph methods."""
import pytest
from model_ledger.graph.models import DataNode, DataPort
from model_ledger.sdk.ledger import Ledger

@pytest.fixture
def ledger():
    return Ledger()

class TestAdd:
    def test_add_single(self, ledger):
        ledger.add(DataNode("scorer", platform="gondola", inputs=["features"], outputs=["scores"]))
        assert ledger.get("scorer").name == "scorer"

    def test_add_list(self, ledger):
        ledger.add([DataNode("a", outputs=["t1"]), DataNode("b", inputs=["t1"])])
        assert len(ledger.list()) == 2

    def test_add_creates_snapshot(self, ledger):
        ledger.add(DataNode("scorer", platform="gondola", inputs=["f"], outputs=["s"]))
        snaps = ledger.history("scorer")
        discovered = [s for s in snaps if s.event_type == "discovered"]
        assert len(discovered) == 1
        assert discovered[0].payload["platform"] == "gondola"

    def test_add_idempotent(self, ledger):
        ledger.add(DataNode("scorer", outputs=["s"]))
        ledger.add(DataNode("scorer", outputs=["s"]))
        assert len(ledger.list()) == 1

class TestConnect:
    def test_matching_ports(self, ledger):
        ledger.add([DataNode("writer", outputs=["shared"]), DataNode("reader", inputs=["shared"])])
        result = ledger.connect()
        assert result["links_created"] >= 1
        deps = ledger.dependencies("reader", direction="upstream")
        assert any(d["model"].name == "writer" for d in deps)

    def test_no_match(self, ledger):
        ledger.add([DataNode("a", outputs=["x"]), DataNode("b", inputs=["y"])])
        assert ledger.connect()["links_created"] == 0

    def test_skips_self_refs(self, ledger):
        ledger.add(DataNode("a", inputs=["t"], outputs=["t"]))
        assert ledger.connect()["links_created"] == 0

    def test_shared_table_discriminator(self, ledger):
        ledger.add([
            DataNode("w_a", outputs=[DataPort("shared", model_name="a")]),
            DataNode("w_b", outputs=[DataPort("shared", model_name="b")]),
            DataNode("r_a", inputs=[DataPort("shared", model_name="a")]),
        ])
        ledger.connect()
        ups = [d["model"].name for d in ledger.dependencies("r_a", direction="upstream")]
        assert "w_a" in ups
        assert "w_b" not in ups

    def test_pipeline(self, ledger):
        ledger.add([
            DataNode("seg", outputs=["segments"]),
            DataNode("score", inputs=["segments"], outputs=["scores"]),
            DataNode("alert", inputs=["scores"]),
        ])
        ledger.connect()
        assert any(d["model"].name == "score" for d in ledger.dependencies("alert", direction="upstream"))
        assert any(d["model"].name == "seg" for d in ledger.dependencies("score", direction="upstream"))

class TestTrace:
    def test_ordered_pipeline(self, ledger):
        ledger.add([
            DataNode("seg", outputs=["segments"]),
            DataNode("score", inputs=["segments"], outputs=["scores"]),
            DataNode("alert", inputs=["scores"]),
        ])
        ledger.connect()
        assert ledger.trace("alert") == ["seg", "score", "alert"]

    def test_single_node(self, ledger):
        ledger.add(DataNode("standalone"))
        ledger.connect()
        assert ledger.trace("standalone") == ["standalone"]

    def test_not_found(self, ledger):
        with pytest.raises(Exception):
            ledger.trace("nonexistent")

class TestUpstreamDownstream:
    def test_upstream(self, ledger):
        ledger.add([
            DataNode("a", outputs=["t1"]),
            DataNode("b", inputs=["t1"], outputs=["t2"]),
            DataNode("c", inputs=["t2"]),
        ])
        ledger.connect()
        assert "a" in ledger.upstream("c")
        assert "b" in ledger.upstream("c")

    def test_downstream(self, ledger):
        ledger.add([
            DataNode("a", outputs=["t1"]),
            DataNode("b", inputs=["t1"], outputs=["t2"]),
            DataNode("c", inputs=["t2"]),
        ])
        ledger.connect()
        assert "b" in ledger.downstream("a")
        assert "c" in ledger.downstream("a")

    def test_upstream_empty(self, ledger):
        ledger.add(DataNode("root", outputs=["t1"]))
        ledger.connect()
        assert ledger.upstream("root") == []
