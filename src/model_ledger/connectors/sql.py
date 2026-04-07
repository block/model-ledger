"""sql_connector — config-driven SQL-based model discovery.

Returns a SourceConnector that queries a database and maps rows to DataNodes.
Supports three levels: simple column mapping, explicit I/O columns, SQL parsing.
"""
from __future__ import annotations

import re
from typing import Any, Callable

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
    sql_preprocessor: Callable[[str], str] | None = "default",
    shared_table_patterns: list[str] | None = None,
    shared_table_fallback: dict[str, str] | None = None,
    cron_column: str | None = None,
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
        sql_preprocessor: Function to clean SQL before parsing (e.g., strip template
            variables). Default: strip_template_vars from model_ledger.adapters.sql.
            Pass None to disable preprocessing.
        shared_table_patterns: When sql_column is set, table names matching any of
            these substrings will get model_name discriminators from the parsed SQL.
            Default: ["scores", "alert"].
        shared_table_fallback: When a write table matches shared_table_patterns but
            no model_name is found in the SQL, derive model_name from a column value.
            Dict with keys: source_column (required), strip_prefix (optional regex).
            Example: {"source_column": "NAME", "strip_prefix": "etl_"}
        cron_column: Column containing a cron expression. When set, adds both
            the raw cron and an English translation to metadata.
        input_port: Config dict with keys: column, fallback (optional), kind (optional).
        output_port: Config dict with keys: column, fallback (optional), kind (optional).
        metadata_columns: Explicit {metadata_key: column_name} mapping.
            If omitted, all unmapped columns become metadata automatically.

    Returns:
        A SourceConnector with a discover() method.
    """
    # Resolve default preprocessor
    if sql_preprocessor == "default":
        from model_ledger.adapters.sql import strip_template_vars
        sql_preprocessor = strip_template_vars

    return _SQLConnector(
        name=name, connection=connection, query=query,
        name_column=name_column, name_prefix=name_prefix,
        input_columns=input_columns or [], output_columns=output_columns or [],
        sql_column=sql_column, sql_preprocessor=sql_preprocessor,
        shared_table_patterns=shared_table_patterns if shared_table_patterns is not None else ["scores", "alert"],
        shared_table_fallback=shared_table_fallback,
        cron_column=cron_column,
        input_port=input_port, output_port=output_port,
        metadata_columns=metadata_columns,
    )


class _SQLConnector:
    def __init__(
        self, *, name: str, connection: Any, query: str,
        name_column: str, name_prefix: str,
        input_columns: list[str], output_columns: list[str],
        sql_column: str | None, sql_preprocessor: Callable[[str], str] | None,
        shared_table_patterns: list[str],
        shared_table_fallback: dict[str, str] | None,
        cron_column: str | None,
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
        self._sql_preprocessor = sql_preprocessor
        self._shared_table_patterns = shared_table_patterns
        self._shared_table_fallback = shared_table_fallback
        self._cron_column = cron_column
        self._input_port = input_port
        self._output_port = output_port
        self._metadata_columns = metadata_columns
        # Columns consumed by name/inputs/outputs (not metadata)
        self._reserved_columns: set[str] = {name_column}
        self._reserved_columns.update(input_columns)
        self._reserved_columns.update(output_columns)
        if sql_column:
            self._reserved_columns.add(sql_column)
        if cron_column:
            self._reserved_columns.add(cron_column)
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
            if self._sql_preprocessor and sql_text:
                sql_text = self._sql_preprocessor(sql_text)
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
                    elif self._shared_table_fallback and any(
                        p in t.lower() for p in self._shared_table_patterns
                    ):
                        # Derive model_name from name column with optional prefix stripping
                        src_col = self._shared_table_fallback["source_column"]
                        fallback_name = str(row.get(src_col, ""))
                        strip = self._shared_table_fallback.get("strip_prefix")
                        if strip:
                            fallback_name = re.sub(f"^{strip}", "", fallback_name)
                        outputs.append(DataPort(t.lower(), model_name=fallback_name))
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

        # Cron column translation
        if self._cron_column:
            cron_val = row.get(self._cron_column)
            if cron_val:
                from model_ledger.adapters.cron import translate_cron_to_english
                metadata["cron"] = cron_val
                metadata["run_frequency"] = translate_cron_to_english(cron_val)

        metadata["node_type"] = metadata.get("node_type", self.name)

        return DataNode(
            name=model_name, platform=self.name,
            inputs=inputs, outputs=outputs, metadata=metadata,
        )
