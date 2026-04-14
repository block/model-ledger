"""prefect_connector — discover deployments from Prefect Cloud.

Queries the Prefect Cloud API for deployments and converts each to a
DataNode with schedule, parameters, and metadata.

    >>> from model_ledger.connectors import prefect_connector
    >>> connector = prefect_connector(name="prefect")
    >>> nodes = connector.discover()
"""
from __future__ import annotations

from typing import Any

try:
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.filters import DeploymentFilter, DeploymentFilterTags
except ImportError:  # pragma: no cover
    get_client = None  # type: ignore[assignment]

from model_ledger.graph.models import DataNode


class _PrefectConnector:
    def __init__(
        self, *, name: str, tag_filter: list[str] | None,
    ) -> None:
        self.name = name
        self._tag_filter = tag_filter

    def discover(self) -> list[DataNode]:
        if get_client is None:  # pragma: no cover
            raise ImportError("prefect is required for prefect_connector. Install with: pip install prefect")
        import asyncio
        return asyncio.run(self._discover_async())

    async def _discover_async(self) -> list[DataNode]:
        PAGE_SIZE = 200
        all_deployments: list[Any] = []
        offset = 0

        deployment_filter = None
        if self._tag_filter:
            deployment_filter = DeploymentFilter(
                tags=DeploymentFilterTags(all_=self._tag_filter)
            )

        async with get_client() as client:
            while True:
                batch = await client.read_deployments(
                    deployment_filter=deployment_filter,
                    limit=PAGE_SIZE,
                    offset=offset,
                )
                if not batch:
                    break
                all_deployments.extend(batch)
                offset += len(batch)

        nodes = []
        seen: set[str] = set()
        for dep in all_deployments:
            if dep.name in seen:
                continue
            seen.add(dep.name)
            nodes.append(self._to_node(dep))
        return nodes

    def _to_node(self, dep: Any) -> DataNode:
        tags = {
            t.split(":", 1)[0]: t.split(":", 1)[1]
            for t in (dep.tags or []) if ":" in t
        }

        schedule = None
        if dep.schedules:
            sched = dep.schedules[0].schedule
            schedule = getattr(sched, "cron", None) or str(sched)

        return DataNode(
            name=dep.name,
            platform=self.name,
            metadata={
                "node_type": "prefect_deployment",
                "application": tags.get("application"),
                "repo": tags.get("repo"),
                "owner": tags.get("author"),
                "schedule": schedule,
                "has_schedule": bool(dep.schedules),
                "entrypoint": dep.entrypoint,
                "version": dep.version,
                "source_updated_at": dep.updated.isoformat() if dep.updated else None,
            },
        )


def prefect_connector(
    *,
    name: str = "prefect",
    tag_filter: list[str] | None = None,
) -> _PrefectConnector:
    """Create a SourceConnector that discovers deployments from Prefect Cloud.

    Args:
        name: Platform name for discovered DataNodes.
        tag_filter: Optional list of tags to filter deployments (all must match).
            Example: ["deploy_from:main"] to get only production deployments.
            If None, returns all deployments.

    Returns:
        A SourceConnector with a discover() method.
    """
    return _PrefectConnector(name=name, tag_filter=tag_filter)
