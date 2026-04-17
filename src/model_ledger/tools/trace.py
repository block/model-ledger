"""Trace tool — dependency graph traversal."""

from __future__ import annotations

import contextlib

from model_ledger.backends import batch_fallbacks
from model_ledger.sdk.ledger import Ledger
from model_ledger.tools.schemas import DependencyNode, TraceInput, TraceOutput


def trace(input: TraceInput, ledger: Ledger) -> TraceOutput:
    """Traverse a model's dependency graph.

    Walks upstream (models this one depends on) and/or downstream
    (models that depend on this one), returning ``DependencyNode`` lists
    with depth and relationship metadata.

    Raises:
        ModelNotFoundError: If the target model does not exist.
    """
    ledger.get(input.name)
    backend = ledger._backend

    upstream_names: list[str] = []
    if input.direction in ("upstream", "both"):
        try:
            upstream_names = ledger.upstream(input.name)
        except (KeyError, ValueError):
            upstream_names = []

    downstream_names: list[str] = []
    if input.direction in ("downstream", "both"):
        try:
            downstream_names = ledger.downstream(input.name)
        except (KeyError, ValueError):
            downstream_names = []

    all_names = upstream_names + downstream_names
    name_to_hash: dict[str, str] = {}
    for n in all_names:
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

    upstream_nodes: list[DependencyNode] = []
    total_up = len(upstream_names)
    for idx, name in enumerate(upstream_names):
        mh = name_to_hash.get(name)
        platform = platforms.get(mh) if mh else None
        upstream_nodes.append(
            DependencyNode(
                name=name,
                platform=platform,
                depth=total_up - idx,
                relationship="depends_on",
            )
        )

    downstream_nodes: list[DependencyNode] = []
    for idx, name in enumerate(downstream_names):
        mh = name_to_hash.get(name)
        platform = platforms.get(mh) if mh else None
        downstream_nodes.append(
            DependencyNode(
                name=name,
                platform=platform,
                depth=idx + 1,
                relationship="feeds_into",
            )
        )

    if input.depth is not None:
        upstream_nodes = [n for n in upstream_nodes if n.depth <= input.depth]
        downstream_nodes = [n for n in downstream_nodes if n.depth <= input.depth]

    total = len(upstream_nodes) + len(downstream_nodes)
    return TraceOutput(
        root=input.name,
        upstream=upstream_nodes,
        downstream=downstream_nodes,
        total_nodes=total,
    )
