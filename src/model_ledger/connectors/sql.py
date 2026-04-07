"""sql_connector — config-driven SQL-based model discovery.

Returns a SourceConnector that queries a database and maps rows to DataNodes.
Supports three levels: simple column mapping, explicit I/O columns, SQL parsing.
"""
from __future__ import annotations

from typing import Any

from model_ledger.graph.models import DataNode, DataPort


def sql_connector(
    *,
    name: str,
    connection: Any,
    query: str,
    name_column: str,
    name_prefix: str = "",
    input_columns: list[str] | None = None,
    output_columns: list[str] | None = None,
    sql_column: str | None = None,
    shared_table_patterns: list[str] | None = None,
    input_port: dict[str, str] | None = None,
    output_port: dict[str, str] | None = None,
    metadata_columns: dict[str, str] | None = None,
) -> _SQLConnector:
    """Create a SourceConnector that discovers models from a SQL query.

    Args:
        name: Platform name for discovered DataNodes.
        connection: Database connection with execute() method.
        query: SQL query to run.
        name_column: Column containing the model name.
        name_prefix: Optional prefix for model names (e.g., "queue:").
        input_columns: Columns containing input table/port identifiers.
        output_columns: Columns containing output table/port identifiers.
        sql_column: Column containing SQL to parse for input/output tables.
        shared_table_patterns: When sql_column is set, table names matching any of
            these substrings will get model_name discriminators from the parsed SQL.
            Default: ["scores", "alert"] (common patterns for shared scoring/alerting tables).
        input_port: Config dict with keys: column, fallback (optional), kind (optional).
            Creates a single input port from a column value.
        output_port: Config dict with keys: column, fallback (optional), kind (optional).
            Creates a single output port from a column value.
        metadata_columns: Explicit {metadata_key: column_name} mapping.
            If omitted, all unmapped columns become metadata automatically.

    Returns:
        A SourceConnector with a discover() method.
    """
    return _SQLConnector(
        name=name, connection=connection, query=query,
        name_column=name_column, name_prefix=name_prefix,
        input_columns=input_columns or [], output_columns=output_columns or [],
        sql_column=sql_column,
        shared_table_patterns=shared_table_patterns if shared_table_patterns is not None else ["scores", "alert"],
        input_port=input_port, output_port=output_port,
        metadata_columns=metadata_columns,
    )


class _SQLConnector:
    def __init__(
        self, *, name: str, connection: Any, query: str,
        name_column: str, name_prefix: str,
        input_columns: list[str], output_columns: list[str],
        sql_column: str | None, shared_table_patterns: list[str],
        input_port: dict[str, str] | None, output_port: dict[str, str] | None,
        metadata_columns: dict[str, str] | None,
    ) -> None:
        self.name = name
        self._conn = connection
        self._query = query
        self._name_column = name_column
        self._name_prefix = name_prefix
        self._input_columns = input_columns
        self._output_columns = output_columns
        self._sql_column = sql_column
        self._shared_table_patterns = shared_table_patterns
        self._input_port = input_port
        self._output_port = output_port
        self._metadata_columns = metadata_columns
        # Columns consumed by name/inputs/outputs (not metadata)
        self._reserved_columns: set[str] = {name_column}
        self._reserved_columns.update(input_columns)
        self._reserved_columns.update(output_columns)
        if sql_column:
            self._reserved_columns.add(sql_column)
        for port_cfg in [input_port, output_port]:
            if port_cfg:
                self._reserved_columns.add(port_cfg.get("column", ""))
                if "fallback" in port_cfg:
                    self._reserved_columns.add(port_cfg["fallback"])

    def discover(self) -> list[DataNode]:
        rows = self._conn.execute(self._query)
        return [self._to_node(row) for row in rows]

    def _build_port(self, row: dict[str, Any], port_cfg: dict[str, str]) -> DataPort | None:
        """Build a DataPort from a port config dict."""
        col = port_cfg.get("column", "")
        fallback = port_cfg.get("fallback")
        val = row.get(col)
        if val is None and fallback:
            val = row.get(fallback)
        if val is None:
            return None
        kwargs = {k: v for k, v in port_cfg.items() if k not in ("column", "fallback")}
        return DataPort(str(val), **kwargs)

    def _to_node(self, row: dict[str, Any]) -> DataNode:
        model_name = self._name_prefix + str(row[self._name_column])

        # Build inputs
        inputs: list[DataPort] = []
        for col in self._input_columns:
            val = row.get(col)
            if val:
                inputs.append(DataPort(str(val).lower()))

        # Build outputs
        outputs: list[DataPort] = []
        for col in self._output_columns:
            val = row.get(col)
            if val:
                outputs.append(DataPort(str(val).lower()))

        # SQL column parsing
        if self._sql_column:
            sql_text = row.get(self._sql_column) or ""
            if sql_text:
                from model_ledger.adapters.sql import (
                    extract_model_name_filters,
                    extract_tables_from_sql,
                    extract_write_tables,
                )
                read_tables = extract_tables_from_sql(sql_text)
                write_tables = extract_write_tables(sql_text)
                model_names = extract_model_name_filters(sql_text)

                for t in read_tables:
                    if model_names and any(p in t.lower() for p in self._shared_table_patterns):
                        for mn in model_names:
                            inputs.append(DataPort(t.lower(), model_name=mn))
                    else:
                        inputs.append(DataPort(t.lower()))
                for t in write_tables:
                    if model_names:
                        outputs.append(DataPort(t.lower(), model_name=model_names[0]))
                    else:
                        outputs.append(DataPort(t.lower()))

        # Input port config
        if self._input_port:
            port = self._build_port(row, self._input_port)
            if port:
                inputs.append(port)

        # Output port config
        if self._output_port:
            port = self._build_port(row, self._output_port)
            if port:
                outputs.append(port)

        # Build metadata
        if self._metadata_columns is not None:
            metadata = {
                meta_key: row.get(col_name)
                for meta_key, col_name in self._metadata_columns.items()
                if row.get(col_name) is not None
            }
        else:
            metadata = {
                k: v for k, v in row.items()
                if k not in self._reserved_columns and v is not None
            }

        metadata["node_type"] = metadata.get("node_type", self.name)

        return DataNode(
            name=model_name, platform=self.name,
            inputs=inputs, outputs=outputs, metadata=metadata,
        )
