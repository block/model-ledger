"""Discover tool — bulk ingestion from connectors, files, or inline data."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from model_ledger.connectors import prefect_connector, rest_connector
from model_ledger.graph.models import DataNode
from model_ledger.graph.protocol import SourceConnector
from model_ledger.sdk.ledger import Ledger
from model_ledger.tools.schemas import DiscoverInput, DiscoverOutput, ModelSummary

# Connectors whose entire configuration is plain data (no live connection
# object, no callable), so an agent can drive them purely from JSON.
_CONFIG_CONNECTORS: dict[str, Callable[[dict[str, Any]], SourceConnector]] = {
    "rest": lambda config: rest_connector(**config),
    "prefect": lambda config: prefect_connector(**config),
}

# Connectors that require a non-serializable argument an agent can't pass as
# JSON — point the caller to the SDK instead of failing opaquely.
_SDK_ONLY_CONNECTORS: dict[str, str] = {
    "sql": "needs a live database connection",
    "github": "needs a parser callable",
}


def _dict_to_datanode(d: dict[str, Any]) -> DataNode:
    """Convert a raw dict to a DataNode."""
    return DataNode(
        name=d["name"],
        platform=d.get("platform", ""),
        inputs=d.get("inputs", []),
        outputs=d.get("outputs", []),
        metadata={k: v for k, v in d.items() if k not in ("name", "platform", "inputs", "outputs")},
    )


def _error(message: str) -> DiscoverOutput:
    return DiscoverOutput(models_added=0, models_skipped=0, links_created=0, errors=[message])


def _ingest(nodes: list[DataNode], ledger: Ledger, auto_connect: bool) -> DiscoverOutput:
    """Add nodes to the ledger, optionally connect, and summarize."""
    add_result = ledger.add(nodes)
    added = add_result["added"]
    skipped = add_result["skipped"]

    links_created = 0
    if auto_connect and added > 0:
        links_created = ledger.connect()["links_created"]

    summaries: list[ModelSummary] = []
    for node in nodes:
        try:
            ref = ledger.get(node.name)
        except Exception:
            continue
        summaries.append(
            ModelSummary(
                name=ref.name,
                owner=ref.owner,
                model_type=ref.model_type,
                platform=node.platform or None,
                status=ref.status,
            )
        )

    return DiscoverOutput(
        models_added=added,
        models_skipped=skipped,
        links_created=links_created,
        models=summaries,
    )


def _discover_via_connector(input: DiscoverInput, ledger: Ledger) -> DiscoverOutput:
    """Build a config-driven connector, run it, and ingest the result.

    Returns errors in ``DiscoverOutput.errors`` (never raises) so an agent gets
    an actionable response instead of a crash.
    """
    name = input.connector_name
    if not name:
        return _error("connector_name is required when source_type is 'connector'")

    if name in _SDK_ONLY_CONNECTORS:
        reason = _SDK_ONLY_CONNECTORS[name]
        return _error(
            f"The '{name}' connector {reason}, which can't be supplied as JSON. "
            f"Run it from the Python SDK: ledger.add({name}_connector(...).discover())"
        )

    factory = _CONFIG_CONNECTORS.get(name)
    if factory is None:
        return _error(
            f"Unknown connector '{name}'. Config-drivable connectors: "
            f"{sorted(_CONFIG_CONNECTORS)}. SDK-only connectors: {sorted(_SDK_ONLY_CONNECTORS)}."
        )

    try:
        connector = factory(input.connector_config or {})
        nodes = list(connector.discover())
    except Exception as exc:
        return _error(f"connector '{name}' failed: {exc}")

    return _ingest(nodes, ledger, input.auto_connect)


def discover(input: DiscoverInput, ledger: Ledger) -> DiscoverOutput:
    """Import models from external sources into the ledger.

    Supports three source types:

    - **inline**: models passed directly as a list of dicts.
    - **file**: models loaded from a JSON file on disk.
    - **connector**: run a config-drivable connector (``rest``, ``prefect``) from
      ``connector_config``. Connectors needing a live connection or a callable
      (``sql``, ``github``) return a message in ``errors`` directing to the SDK.

    When ``auto_connect`` is True and models were added, runs ``ledger.connect()``
    to auto-link dependencies based on matching input/output ports.
    """
    if input.source_type == "connector":
        return _discover_via_connector(input, ledger)

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

    return _ingest(nodes, ledger, input.auto_connect)
