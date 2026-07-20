"""Trace tool — dependency graph traversal."""

from __future__ import annotations

import contextlib

from model_ledger.backends import batch_fallbacks
from model_ledger.core.exceptions import ModelNotFoundError
from model_ledger.sdk.ledger import Ledger
from model_ledger.tools.schemas import DependencyNode, TraceInput, TraceOutput


def _bfs_levels(
    ledger: Ledger,
    root: str,
    direction: str,
    max_depth: int | None,
) -> list[tuple[str, int]]:
    """Breadth-first traversal from ``root``, recording each node's real level.

    ``depth`` is the BFS level — the shortest edge distance from the traced
    node — not a position in a flat transitive list. Each node is reported
    once, at its minimum depth. The traversal terminates at ``max_depth``,
    so depth-bounded queries do depth-bounded work.
    """
    visited: set[str] = {root}
    frontier: list[str] = [root]
    levels: list[tuple[str, int]] = []
    depth = 0
    while frontier and (max_depth is None or depth < max_depth):
        depth += 1
        next_frontier: list[str] = []
        for name in frontier:
            try:
                edges = ledger.dependencies(name, direction=direction)
            except (KeyError, ValueError, ModelNotFoundError):
                continue
            for edge in edges:
                child = edge["model"].name
                if child in visited:
                    continue
                visited.add(child)
                levels.append((child, depth))
                next_frontier.append(child)
        frontier = next_frontier
    return levels


def trace(input: TraceInput, ledger: Ledger) -> TraceOutput:
    """Traverse a model's dependency graph.

    Walks upstream (models this one depends on) and/or downstream
    (models that depend on this one) breadth-first, returning
    ``DependencyNode`` lists whose ``depth`` is the actual BFS level from
    the traced model. ``input.depth`` bounds the traversal itself, not
    just the output.

    Raises:
        ModelNotFoundError: If the target model does not exist.
    """
    ledger.get(input.name)
    backend = ledger.backend

    upstream_levels: list[tuple[str, int]] = []
    if input.direction in ("upstream", "both"):
        upstream_levels = _bfs_levels(ledger, input.name, "upstream", input.depth)

    downstream_levels: list[tuple[str, int]] = []
    if input.direction in ("downstream", "both"):
        downstream_levels = _bfs_levels(ledger, input.name, "downstream", input.depth)

    name_to_hash: dict[str, str] = {}
    for n, _ in upstream_levels + downstream_levels:
        with contextlib.suppress(Exception):
            name_to_hash[n] = ledger.get(n).model_hash

    all_model_hashes = list(name_to_hash.values())
    if all_model_hashes:
        if hasattr(backend, "batch_platforms"):
            platforms = backend.batch_platforms(all_model_hashes)
        else:
            platforms = batch_fallbacks.batch_platforms(backend, all_model_hashes)
    else:
        platforms = {}

    def _node(name: str, depth: int, relationship: str) -> DependencyNode:
        mh = name_to_hash.get(name)
        return DependencyNode(
            name=name,
            platform=platforms.get(mh) if mh else None,
            depth=depth,
            relationship=relationship,
        )

    upstream_nodes = [_node(n, d, "depends_on") for n, d in upstream_levels]
    downstream_nodes = [_node(n, d, "feeds_into") for n, d in downstream_levels]

    # Distinct models: with direction="both" (e.g. in a cycle) a node can be
    # reachable in both directions but must be counted once.
    total = len({n for n, _ in upstream_levels} | {n for n, _ in downstream_levels})
    return TraceOutput(
        root=input.name,
        upstream=upstream_nodes,
        downstream=downstream_nodes,
        total_nodes=total,
    )
