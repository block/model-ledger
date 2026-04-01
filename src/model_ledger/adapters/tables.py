"""Table-based pipeline discovery.

Discovers active pipelines by scanning database tables that have
(name_column, timestamp_column) schemas. Each distinct name in the table
represents one active pipeline.

Works with any database (Snowflake, BigQuery, Postgres) via the
DBConnection protocol.

Example:
    >>> from model_ledger.adapters.tables import discover_pipelines_from_table
    >>> nodes = discover_pipelines_from_table(
    ...     connection=conn,
    ...     table="scores_archive",
    ...     name_column="model_name",
    ...     timestamp_column="run_date",
    ... )
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from model_ledger.graph.models import DataNode, DataPort


@runtime_checkable
class DBConnection(Protocol):
    def execute(
        self, query: str, params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...


def discover_pipelines_from_table(
    connection: DBConnection,
    table: str,
    name_column: str,
    timestamp_column: str,
    node_type: str = "pipeline",
    platform: str = "database",
) -> list[DataNode]:
    """Discover active pipelines from a database table.

    Each distinct value in name_column becomes a DataNode with an output
    port pointing to the table (with the name as a discriminator).

    Args:
        connection: Database connection implementing execute()
        table: Fully qualified table name
        name_column: Column containing pipeline/model names
        timestamp_column: Column containing run timestamps
        node_type: Node type for metadata (default: "pipeline")
        platform: Platform name for the DataNode (default: "database")

    Returns:
        List of DataNodes, one per distinct name.
    """
    try:
        rows = connection.execute(f"""
            SELECT {name_column} AS name,
                   MIN({timestamp_column}) AS first_output,
                   MAX({timestamp_column}) AS last_output,
                   COUNT(*) AS total_rows
            FROM {table}
            WHERE {name_column} IS NOT NULL
            GROUP BY {name_column}
            ORDER BY last_output DESC
        """)
    except Exception:
        return []

    return [
        DataNode(
            name=f"pipeline:{row['NAME']}",
            platform=platform,
            inputs=[],
            outputs=[DataPort(table.lower(), **{name_column.lower(): row["NAME"]})],
            metadata={
                "pipeline_name": row["NAME"],
                "source_table": table,
                "first_output_date": str(row.get("FIRST_OUTPUT", "")),
                "last_output_date": str(row.get("LAST_OUTPUT", "")),
                "total_rows": row.get("TOTAL_ROWS", 0),
                "node_type": node_type,
            },
        )
        for row in rows
    ]
