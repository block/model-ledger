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
        assert "feature_pipeline" in upstream_names
        assert "raw_data" not in upstream_names


class TestTraceBatchDispatch:
    """Trace produces correct output via fallback batch platform dispatch."""

    def test_platforms_resolved_via_fallback(self, graph_ledger):
        assert not hasattr(graph_ledger._backend, "batch_platforms")

        result = trace(TraceInput(name="scoring_model"), graph_ledger)

        for node in result.upstream + result.downstream:
            assert isinstance(node, DependencyNode)

    def test_trace_structure_via_fallback(self, graph_ledger):
        result = trace(TraceInput(name="scoring_model"), graph_ledger)

        upstream_names = [n.name for n in result.upstream]
        downstream_names = [n.name for n in result.downstream]
        assert "feature_pipeline" in upstream_names
        assert "alert_engine" in downstream_names
        assert result.total_nodes == len(result.upstream) + len(result.downstream)


class TestTraceNonexistentModel:
    """Tracing a model that doesn't exist should raise."""

    def test_raises_model_not_found(self, ledger):
        with pytest.raises(ModelNotFoundError):
            trace(TraceInput(name="nonexistent_model"), ledger)


@pytest.fixture
def fanout_ledger(ledger):
    """Synthetic fan-out DAG: 19 transitive upstreams of scoring_model
    spread over 8 real BFS levels with uneven fan-out, a diamond
    (r1 is reachable via both t1 and t2), and a shortcut (r2 is both a
    direct upstream and reachable again at level 3).

    Level sizes from scoring_model: [4, 3, 2, 4, 2, 2, 1, 1].
    """
    edges = [
        # (upstream, downstream) — downstream depends_on upstream
        ("f1", "scoring_model"),
        ("f2", "scoring_model"),
        ("f3", "scoring_model"),
        ("r2", "scoring_model"),  # shortcut: also reachable at level 3
        ("t1", "f1"),
        ("t2", "f1"),
        ("t3", "f2"),
        ("r1", "t1"),
        ("r1", "t2"),  # diamond: r1 via two paths
        ("r2", "t2"),
        ("r3", "t3"),
        ("s1", "r1"),
        ("s2", "r1"),
        ("s3", "r1"),
        ("s4", "r1"),
        ("u1", "s1"),
        ("u2", "s4"),
        ("v1", "u1"),
        ("v2", "u1"),
        ("w1", "v1"),
        ("x1", "w1"),
    ]
    names = {"scoring_model"} | {n for e in edges for n in e}
    for name in sorted(names):
        ledger.register(
            name=name,
            owner="risk-team",
            model_type="ml_model",
            tier="low",
            purpose="fixture",
        )
    for up, down in edges:
        ledger.link_dependency(up, down, actor="graph_builder")
    return ledger


EXPECTED_UPSTREAM_DEPTHS = {
    "f1": 1,
    "f2": 1,
    "f3": 1,
    "r2": 1,  # shortest path wins over the level-3 route
    "t1": 2,
    "t2": 2,
    "t3": 2,
    "r1": 3,
    "r3": 3,
    "s1": 4,
    "s2": 4,
    "s3": 4,
    "s4": 4,
    "u1": 5,
    "u2": 5,
    "v1": 6,
    "v2": 6,
    "w1": 7,
    "x1": 8,
}


class TestTraceDepthIsBfsLevel:
    """Regression: depth must be the actual BFS level from the traced node,
    not the node's position in a flat transitive list. Previously any model
    with N transitive upstreams rendered as an N-deep linear chain."""

    def test_upstream_depths_are_bfs_levels(self, fanout_ledger):
        result = trace(TraceInput(name="scoring_model", direction="upstream"), fanout_ledger)

        depths = {n.name: n.depth for n in result.upstream}
        assert depths == EXPECTED_UPSTREAM_DEPTHS

    def test_max_depth_is_level_count_not_node_count(self, fanout_ledger):
        result = trace(TraceInput(name="scoring_model", direction="upstream"), fanout_ledger)

        assert len(result.upstream) == 19
        assert max(n.depth for n in result.upstream) == 8  # not 19

    def test_diamond_node_appears_once_at_min_depth(self, fanout_ledger):
        result = trace(TraceInput(name="scoring_model", direction="upstream"), fanout_ledger)

        r1 = [n for n in result.upstream if n.name == "r1"]
        assert len(r1) == 1
        assert r1[0].depth == 3
        # Shortcut node: direct edge beats the longer route.
        r2 = [n for n in result.upstream if n.name == "r2"]
        assert len(r2) == 1
        assert r2[0].depth == 1

    def test_depth_bound_returns_exactly_the_near_levels(self, fanout_ledger):
        result = trace(
            TraceInput(name="scoring_model", direction="upstream", depth=3),
            fanout_ledger,
        )

        expected = {n for n, d in EXPECTED_UPSTREAM_DEPTHS.items() if d <= 3}
        assert {n.name for n in result.upstream} == expected

    def test_downstream_depths_are_bfs_levels(self, fanout_ledger):
        """Symmetry: downstream had the same flat-list fabrication."""
        result = trace(TraceInput(name="x1", direction="downstream"), fanout_ledger)

        depths = {n.name: n.depth for n in result.downstream}
        assert depths == {
            "w1": 1,
            "v1": 2,
            "u1": 3,
            "s1": 4,
            "r1": 5,
            "t1": 6,
            "t2": 6,  # fan-out: two nodes share level 6
            "f1": 7,
            "scoring_model": 8,
        }

    def test_depth_bound_limits_traversal_work(self, fanout_ledger):
        """depth must bound the traversal itself, not just filter output."""
        backend = fanout_ledger._backend
        calls = {"n": 0}
        original = backend.list_snapshots

        def counting_list_snapshots(*args, **kwargs):
            calls["n"] += 1
            return original(*args, **kwargs)

        backend.list_snapshots = counting_list_snapshots
        try:
            trace(TraceInput(name="scoring_model", direction="upstream", depth=1), fanout_ledger)
            bounded = calls["n"]
            calls["n"] = 0
            trace(TraceInput(name="scoring_model", direction="upstream"), fanout_ledger)
            unbounded = calls["n"]
        finally:
            backend.list_snapshots = original

        assert bounded < unbounded


class TestTotalNodesCountsDistinctModels:
    def test_cycle_traced_both_ways_counts_each_model_once(self, ledger):
        for name in ("a", "b"):
            ledger.register(
                name=name, owner="risk-team", model_type="ml_model", tier="low", purpose="fixture"
            )
        ledger.link_dependency("a", "b", actor="graph_builder")
        ledger.link_dependency("b", "a", actor="graph_builder")

        out = trace(TraceInput(name="a", direction="both"), ledger)
        # b is reachable upstream AND downstream of a — one distinct model.
        assert len(out.upstream) == 1
        assert len(out.downstream) == 1
        assert out.total_nodes == 1

    def test_disjoint_directions_still_sum(self, ledger):
        for name in ("mid", "up", "down"):
            ledger.register(
                name=name, owner="risk-team", model_type="ml_model", tier="low", purpose="fixture"
            )
        ledger.link_dependency("up", "mid", actor="graph_builder")
        ledger.link_dependency("mid", "down", actor="graph_builder")

        out = trace(TraceInput(name="mid", direction="both"), ledger)
        assert out.total_nodes == 2
