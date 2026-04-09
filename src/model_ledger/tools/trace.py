"""Trace tool — dependency graph traversal."""

from __future__ import annotations

from model_ledger.sdk.ledger import Ledger
from model_ledger.tools.schemas import DependencyNode, TraceInput, TraceOutput


def _get_platform(name: str, ledger: Ledger) -> str | None:
    """Try to extract platform from the model's snapshot history."""
    try:
        model = ledger.get(name)
        for snap in ledger.history(model):
            if snap.source:
                return snap.source
            # Also check payload for platform from discovered events
            if snap.payload.get("platform"):
                return snap.payload["platform"]
    except Exception:
        pass
    return None


def trace(input: TraceInput, ledger: Ledger) -> TraceOutput:
    """Traverse a model's dependency graph.

    Walks upstream (models this one depends on) and/or downstream
    (models that depend on this one), returning ``DependencyNode`` lists
    with depth and relationship metadata.

    Raises:
        ModelNotFoundError: If the target model does not exist.
    """
    # 1. Verify model exists — raises ModelNotFoundError if missing
    ledger.get(input.name)

    # 2. Build upstream list
    upstream_nodes: list[DependencyNode] = []
    if input.direction in ("upstream", "both"):
        try:
            upstream_names = ledger.upstream(input.name)
        except (KeyError, ValueError):
            upstream_names = []

        # upstream() returns topological order (sources first, nearest last),
        # so reverse depth: nearest dependency = depth 1, furthest = len.
        total_up = len(upstream_names)
        for idx, name in enumerate(upstream_names):
            platform = _get_platform(name, ledger)
            upstream_nodes.append(
                DependencyNode(
                    name=name,
                    platform=platform,
                    depth=total_up - idx,
                    relationship="depends_on",
                )
            )

    # 3. Build downstream list
    downstream_nodes: list[DependencyNode] = []
    if input.direction in ("downstream", "both"):
        try:
            downstream_names = ledger.downstream(input.name)
        except (KeyError, ValueError):
            downstream_names = []

        for idx, name in enumerate(downstream_names):
            platform = _get_platform(name, ledger)
            downstream_nodes.append(
                DependencyNode(
                    name=name,
                    platform=platform,
                    depth=idx + 1,
                    relationship="feeds_into",
                )
            )

    # 4. Apply depth filter
    if input.depth is not None:
        upstream_nodes = [n for n in upstream_nodes if n.depth <= input.depth]
        downstream_nodes = [n for n in downstream_nodes if n.depth <= input.depth]

    # 5. Return result
    total = len(upstream_nodes) + len(downstream_nodes)
    return TraceOutput(
        root=input.name,
        upstream=upstream_nodes,
        downstream=downstream_nodes,
        total_nodes=total,
    )
