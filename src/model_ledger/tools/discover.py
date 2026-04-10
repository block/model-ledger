"""Discover tool — bulk ingestion from connectors, files, or inline data."""

from __future__ import annotations

import json
from typing import Any

from model_ledger.graph.models import DataNode
from model_ledger.sdk.ledger import Ledger
from model_ledger.tools.schemas import DiscoverInput, DiscoverOutput, ModelSummary


def _dict_to_datanode(d: dict[str, Any]) -> DataNode:
    """Convert a raw dict to a DataNode."""
    return DataNode(
        name=d["name"],
        platform=d.get("platform", ""),
        inputs=d.get("inputs", []),
        outputs=d.get("outputs", []),
        metadata={k: v for k, v in d.items() if k not in ("name", "platform", "inputs", "outputs")},
    )


def discover(input: DiscoverInput, ledger: Ledger) -> DiscoverOutput:
    """Import models from external sources into the ledger.

    Supports three source types:

    - **inline**: models passed directly as a list of dicts.
    - **file**: models loaded from a JSON file on disk.
    - **connector**: not yet supported — raises ``NotImplementedError``.

    When ``auto_connect`` is True and models were added, runs
    ``ledger.connect()`` to auto-link dependencies based on matching
    input/output ports.
    """
    if input.source_type == "connector":
        raise NotImplementedError(
            "Connector execution via tool not yet supported. Use the Python SDK directly."
        )

    if input.source_type == "file":
        if input.file_path is None:
            raise ValueError("file_path is required when source_type is 'file'")
        with open(input.file_path) as f:
            raw_models = json.load(f)
        nodes = [_dict_to_datanode(d) for d in raw_models]

    else:  # inline
        if input.models is None:
            raise ValueError("models is required when source_type is 'inline'")
        nodes = [_dict_to_datanode(d) for d in input.models]

    # Add nodes to ledger (content-hash dedup)
    add_result = ledger.add(nodes)
    added = add_result["added"]
    skipped = add_result["skipped"]

    # Auto-connect dependencies if requested and models were added
    links_created = 0
    if input.auto_connect and added > 0:
        connect_result = ledger.connect()
        links_created = connect_result["links_created"]

    # Build summaries for added models
    summaries: list[ModelSummary] = []
    for node in nodes:
        try:
            ref = ledger.get(node.name)
            summaries.append(
                ModelSummary(
                    name=ref.name,
                    owner=ref.owner,
                    model_type=ref.model_type,
                    platform=node.platform or None,
                    status=ref.status,
                )
            )
        except Exception:
            pass

    return DiscoverOutput(
        models_added=added,
        models_skipped=skipped,
        links_created=links_created,
        models=summaries,
    )
