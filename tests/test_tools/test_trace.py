"""Tests for the trace tool — dependency graph traversal."""

from __future__ import annotations

import pytest

from model_ledger.backends.ledger_memory import InMemoryLedgerBackend
from model_ledger.core.exceptions import ModelNotFoundError
from model_ledger.graph.models import DataNode
from model_ledger.sdk.ledger import Ledger
from model_ledger.tools.schemas import DependencyNode, TraceInput, TraceOutput
from model_ledger.tools.trace import trace


@pytest.fixture
def ledger():
    return Ledger(backend=InMemoryLedgerBackend())


@pytest.fixture
def graph_ledger(ledger):
    """Ledger with a 4-node linear pipeline for graph traversal tests.

    raw_data -> feature_pipeline -> scoring_model -> alert_engine
    """
    ledger.add(
        [
            DataNode("raw_data", platform="database", outputs=["customers"]),
            DataNode(
                "feature_pipeline",
                platform="etl",
                inputs=["customers"],
                outputs=["features"],
            ),
            DataNode(
                "scoring_model",
                platform="ml",
                inputs=["features"],
                outputs=["scores"],
            ),
            DataNode("alert_engine", platform="alerting", inputs=["scores"]),
        ]
    )
    ledger.connect()
    return ledger


class TestTraceBothDirections:
    """Trace both upstream and downstream from a middle node."""

    def test_returns_trace_output(self, graph_ledger):
        result = trace(TraceInput(name="scoring_model"), graph_ledger)

        assert isinstance(result, TraceOutput)

    def test_root_is_target_model(self, graph_ledger):
        result = trace(TraceInput(name="scoring_model"), graph_ledger)

        assert result.root == "scoring_model"

    def test_upstream_contains_dependencies(self, graph_ledger):
        result = trace(TraceInput(name="scoring_model"), graph_ledger)

        upstream_names = [n.name for n in result.upstream]
        assert "feature_pipeline" in upstream_names
        assert "raw_data" in upstream_names

    def test_downstream_contains_dependents(self, graph_ledger):
        result = trace(TraceInput(name="scoring_model"), graph_ledger)

        downstream_names = [n.name for n in result.downstream]
        assert "alert_engine" in downstream_names

    def test_nodes_are_dependency_nodes(self, graph_ledger):
        result = trace(TraceInput(name="scoring_model"), graph_ledger)

        for node in result.upstream + result.downstream:
            assert isinstance(node, DependencyNode)
            assert node.depth >= 1
            assert node.relationship in ("depends_on", "feeds_into")

    def test_total_nodes_counts_all(self, graph_ledger):
        result = trace(TraceInput(name="scoring_model"), graph_ledger)

        assert result.total_nodes == len(result.upstream) + len(result.downstream)

    def test_upstream_relationship_is_depends_on(self, graph_ledger):
        result = trace(TraceInput(name="scoring_model"), graph_ledger)

        for node in result.upstream:
            assert node.relationship == "depends_on"

    def test_downstream_relationship_is_feeds_into(self, graph_ledger):
        result = trace(TraceInput(name="scoring_model"), graph_ledger)

        for node in result.downstream:
            assert node.relationship == "feeds_into"


class TestTraceUpstreamOnly:
    """Trace upstream only — downstream list should be empty."""

    def test_upstream_populated(self, graph_ledger):
        result = trace(
            TraceInput(name="scoring_model", direction="upstream"),
            graph_ledger,
        )

        upstream_names = [n.name for n in result.upstream]
        assert "feature_pipeline" in upstream_names
        assert "raw_data" in upstream_names

    def test_downstream_empty(self, graph_ledger):
        result = trace(
            TraceInput(name="scoring_model", direction="upstream"),
            graph_ledger,
        )

        assert result.downstream == []

    def test_total_nodes_excludes_downstream(self, graph_ledger):
        result = trace(
            TraceInput(name="scoring_model", direction="upstream"),
            graph_ledger,
        )

        assert result.total_nodes == len(result.upstream)


class TestTraceDownstreamOnly:
    """Trace downstream only — upstream list should be empty."""

    def test_downstream_populated(self, graph_ledger):
        result = trace(
            TraceInput(name="scoring_model", direction="downstream"),
            graph_ledger,
        )

        downstream_names = [n.name for n in result.downstream]
        assert "alert_engine" in downstream_names

    def test_upstream_empty(self, graph_ledger):
        result = trace(
            TraceInput(name="scoring_model", direction="downstream"),
            graph_ledger,
        )

        assert result.upstream == []

    def test_total_nodes_excludes_upstream(self, graph_ledger):
        result = trace(
            TraceInput(name="scoring_model", direction="downstream"),
            graph_ledger,
        )

        assert result.total_nodes == len(result.downstream)


class TestTraceLeafNode:
    """Trace a leaf node — no downstream dependents."""

    def test_leaf_has_no_downstream(self, graph_ledger):
        result = trace(TraceInput(name="alert_engine"), graph_ledger)

        assert result.downstream == []

    def test_leaf_has_upstream(self, graph_ledger):
        result = trace(TraceInput(name="alert_engine"), graph_ledger)

        upstream_names = [n.name for n in result.upstream]
        assert len(upstream_names) >= 1

    def test_root_node_has_no_upstream(self, graph_ledger):
        result = trace(TraceInput(name="raw_data"), graph_ledger)

        assert result.upstream == []

    def test_root_node_has_downstream(self, graph_ledger):
        result = trace(TraceInput(name="raw_data"), graph_ledger)

        downstream_names = [n.name for n in result.downstream]
        assert len(downstream_names) >= 1


class TestTraceDepthFilter:
    """Depth filter limits how far the trace goes."""

    def test_depth_1_limits_results(self, graph_ledger):
        result = trace(
            TraceInput(name="scoring_model", depth=1),
            graph_ledger,
        )

        for node in result.upstream + result.downstream:
            assert node.depth <= 1

    def test_depth_1_excludes_transitive(self, graph_ledger):
        result = trace(
            TraceInput(name="scoring_model", depth=1),
            graph_ledger,
        )

        upstream_names = [n.name for n in result.upstream]
        # feature_pipeline is depth 1, raw_data is depth 2
        assert "feature_pipeline" in upstream_names
        assert "raw_data" not in upstream_names


class TestTraceNonexistentModel:
    """Tracing a model that doesn't exist should raise."""

    def test_raises_model_not_found(self, ledger):
        with pytest.raises(ModelNotFoundError):
            trace(TraceInput(name="nonexistent_model"), ledger)
