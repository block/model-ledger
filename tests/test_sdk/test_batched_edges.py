"""Tests for batched edge resolution in the graph traversal hot path.

The graph methods (``dependencies``/``members``/``groups``) and the
``investigate`` tool used to resolve each dependency or membership edge with
its own single-model ``get()`` round trip, so the backend call count grew
linearly with edge count. These tests pin the new behavior:

1. Round-trip count stays flat as the number of edges grows (no per-edge
   ``get_model``).
2. Results are identical to resolving every edge individually.
"""

from __future__ import annotations

from collections import Counter

import pytest

from model_ledger.backends.ledger_memory import InMemoryLedgerBackend
from model_ledger.backends.sqlite_ledger import SQLiteLedgerBackend
from model_ledger.sdk.ledger import Ledger
from model_ledger.tools.investigate import investigate
from model_ledger.tools.schemas import InvestigateInput


class _CountingMixin:
    """Tallies single-model vs. batched resolution round trips.

    ``get_model`` / ``get_model_by_name`` are the per-edge round trips we want
    to eliminate; ``get_models`` is the batched replacement. Tallying all three
    lets a test assert the *shape* of resolution, not just the total.
    """

    def _init_counter(self) -> None:
        self.calls: Counter[str] = Counter()

    def get_model(self, model_hash):  # type: ignore[override]
        self.calls["get_model"] += 1
        return super().get_model(model_hash)

    def get_model_by_name(self, name):  # type: ignore[override]
        self.calls["get_model_by_name"] += 1
        return super().get_model_by_name(name)

    def get_models(self, model_hashes):  # type: ignore[override]
        self.calls["get_models"] += 1
        return super().get_models(model_hashes)

    @property
    def single_get_calls(self) -> int:
        """Per-edge single-model lookups — the cost we want flat (ideally 0)."""
        return self.calls["get_model"] + self.calls["get_model_by_name"]


class CountingBackend(_CountingMixin, InMemoryLedgerBackend):
    def __init__(self) -> None:
        super().__init__()
        self._init_counter()


class CountingSQLiteBackend(_CountingMixin, SQLiteLedgerBackend):
    """A production-representative backend (native batched SQL methods).

    Unlike the in-memory backend, SQLite ships its own ``batch_dependencies``
    and ``get_models``, so this exercises the full batched-resolution path that
    a real deployment hits — and where eliminating per-edge round trips matters.
    """

    def __init__(self, db_path: str) -> None:
        super().__init__(db_path)
        self._init_counter()


def _build(backend: InMemoryLedgerBackend, n_deps: int, n_groups: int) -> Ledger:
    """A central model with ``n_deps`` upstream + ``n_deps`` downstream edges,
    belonging to ``n_groups`` composites."""
    led = Ledger(backend)
    led.register(
        name="central",
        owner="risk-team",
        model_type="ml_model",
        tier="high",
        purpose="central node",
        actor="test",
    )
    for i in range(n_deps):
        led.register(
            name=f"up_{i}",
            owner="risk-team",
            model_type="ml_model",
            tier="low",
            purpose="upstream",
            actor="test",
        )
        led.link_dependency(
            upstream=f"up_{i}", downstream="central", relationship="data_flow", actor="test"
        )
        led.register(
            name=f"down_{i}",
            owner="risk-team",
            model_type="ml_model",
            tier="low",
            purpose="downstream",
            actor="test",
        )
        led.link_dependency(
            upstream="central", downstream=f"down_{i}", relationship="data_flow", actor="test"
        )
    for g in range(n_groups):
        led.register_group(
            name=f"grp_{g}",
            owner="risk-team",
            model_type="composite",
            tier="high",
            purpose="group",
            members=["central"],
            actor="test",
        )
    # Drop the SDK name cache so reads go through the backend, simulating a
    # fresh process investigating a pre-existing model.
    led._name_cache.clear()
    led._cache_complete = False
    return led


@pytest.fixture
def sqlite_factory(tmp_path):
    """Yields a builder for a CountingSQLiteBackend-backed ledger."""
    created = []

    def make(n_deps: int, n_groups: int):
        path = str(tmp_path / f"ledger_{len(created)}.db")
        backend = CountingSQLiteBackend(path)
        led = _build(backend, n_deps=n_deps, n_groups=n_groups)
        backend.calls.clear()
        created.append((backend, led))
        return backend, led

    return make


class TestDependenciesBatching:
    def test_no_per_edge_get_on_dependencies(self):
        backend = CountingBackend()
        led = _build(backend, n_deps=8, n_groups=0)
        backend.calls.clear()

        deps = led.dependencies("central", direction="both")

        # 8 upstream + 8 downstream edges, but the resolution does NOT fan out
        # into one get_model per edge.
        assert len(deps) == 16
        assert backend.calls["get_model"] == 0
        # All 16 targets resolved in a single batched get_models call.
        assert backend.calls["get_models"] == 1

    def test_dependencies_parity_with_per_edge_resolution(self):
        backend = InMemoryLedgerBackend()
        led = _build(backend, n_deps=5, n_groups=0)

        deps = led.dependencies("central", direction="both")
        got = sorted((d["model"].name, d["relationship"], d["direction"]) for d in deps)

        # Independently resolve every edge by hand from the raw snapshots.
        ref = led.get("central")
        expected = []
        for s in backend.list_snapshots(ref.model_hash):
            if s.event_type == "depends_on":
                target = backend.get_model(s.payload["upstream_hash"])
                expected.append(
                    (target.name, s.payload.get("relationship", "depends_on"), "upstream")
                )
            elif s.event_type == "has_dependent":
                target = backend.get_model(s.payload["downstream_hash"])
                expected.append(
                    (target.name, s.payload.get("relationship", "depends_on"), "downstream")
                )
        assert got == sorted(expected)


class TestInvestigateRoundTrips:
    @pytest.mark.parametrize(
        ("n_deps", "n_groups"),
        [(3, 2), (12, 4), (30, 8)],
    )
    def test_no_per_edge_single_lookups(self, sqlite_factory, n_deps, n_groups):
        backend, led = sqlite_factory(n_deps, n_groups)

        investigate(InvestigateInput(model_name="central", detail="full"), led)

        # The old path issued O(edges) single-model lookups (one get_model per
        # dependency and per membership event). The batched path resolves every
        # edge through get_models, so per-edge single lookups stay at zero
        # regardless of how many edges the node has — the regression guard.
        assert backend.calls["get_model"] == 0
        assert backend.single_get_calls <= 1  # only the initial name resolve

    def test_round_trip_count_is_flat_across_graph_sizes(self, sqlite_factory):
        """Same fixed budget for a sparse and a dense node."""
        sparse_be, sparse = sqlite_factory(3, 2)
        investigate(InvestigateInput(model_name="central", detail="full"), sparse)
        sparse_total = sum(sparse_be.calls.values())

        dense_be, dense = sqlite_factory(30, 8)
        investigate(InvestigateInput(model_name="central", detail="full"), dense)
        dense_total = sum(dense_be.calls.values())

        # Dense graph has ~10x the edges but the resolution budget barely moves
        # (a few extra batched get_models for the extra groups, not O(edges)).
        assert dense_total - sparse_total <= 6


class TestInvestigateParity:
    def test_results_identical_with_and_without_batching(self):
        """A model in groups, with deps, returns the same investigate output."""
        backend = InMemoryLedgerBackend()
        led = _build(backend, n_deps=4, n_groups=3)

        out = investigate(InvestigateInput(model_name="central", detail="full"), led)

        assert sorted(d.name for d in out.upstream) == [f"up_{i}" for i in range(4)]
        assert {d.name for d in out.downstream} == {f"down_{i}" for i in range(4)} | {
            f"grp_{g}" for g in range(3)
        }
        assert sorted(out.groups) == [f"grp_{g}" for g in range(3)]

    def test_removed_member_excluded_after_batching(self):
        """Replay semantics survive batching: a removed member drops out."""
        backend = InMemoryLedgerBackend()
        led = Ledger(backend)
        led.register_group(
            name="scorecard",
            owner="risk-team",
            model_type="composite",
            tier="high",
            purpose="group",
            members=[],
            actor="test",
        )
        for name in ("feature_pipeline", "scoring_model", "alert_queue"):
            led.register(
                name=name,
                owner="risk-team",
                model_type="ml_model",
                tier="low",
                purpose="member",
                actor="test",
            )
            led.add_member("scorecard", name, actor="test")
        led.remove_member("scorecard", "alert_queue", actor="test")

        members = {m.name for m in led.members("scorecard")}
        assert members == {"feature_pipeline", "scoring_model"}
        # The removed member must not list the group either.
        assert led.groups("alert_queue") == []
        assert {g.name for g in led.groups("scoring_model")} == {"scorecard"}
