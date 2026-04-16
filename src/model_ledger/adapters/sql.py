"""SQL parsing utilities for SourceConnectors.

Extract table references, write targets, and model_name filters from SQL.
Used by any connector that discovers models from SQL-based systems
(Snowflake, BigQuery, Postgres, etc.).
"""

from __future__ import annotations

import re


def extract_tables_from_sql(sql: str | None) -> list[str]:
    """Extract table names from SQL FROM and JOIN clauses.

    Returns deduplicated list preserving first-seen order.

    Example:
        >>> extract_tables_from_sql("SELECT * FROM schema.table1 JOIN schema.table2 ON 1=1")
        ['schema.table1', 'schema.table2']
    """
    if not sql:
        return []
    pattern = r"(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*){1,2})"
    matches = re.findall(pattern, sql, re.IGNORECASE)
    seen: set[str] = set()
    result: list[str] = []
    for table in matches:
        lower = table.lower()
        if lower not in seen:
            seen.add(lower)
            result.append(table)
    return result


def extract_write_tables(sql: str | None) -> list[str]:
    """Extract tables that a SQL statement writes to.

    Handles INSERT INTO, CREATE [OR REPLACE] TABLE, MERGE INTO.

    Example:
        >>> extract_write_tables("INSERT INTO schema.output SELECT * FROM source")
        ['schema.output']
    """
    if not sql:
        return []
    table_pattern = r"([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*){1,2})"
    results: list[str] = []
    seen: set[str] = set()

    for pattern in [
        rf"INSERT\s+(?:INTO\s+)?{table_pattern}",
        rf"CREATE\s+(?:OR\s+REPLACE\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?{table_pattern}",
        rf"MERGE\s+INTO\s+{table_pattern}",
    ]:
        for match in re.finditer(pattern, sql, re.IGNORECASE):
            t = match.group(1).lower()
            if t not in seen:
                seen.add(t)
                results.append(match.group(1))
    return results


def extract_model_name_filters(sql: str | None) -> list[str]:
    """Extract model_name values from SQL — filters, aliases, and literals.

    Handles:
        WHERE model_name = 'value'
        WHERE model_name LIKE 'pattern'
        WHERE model_name IN ('v1', 'v2')
        'value' AS model_name  (column alias in SELECT/INSERT)

    Example:
        >>> extract_model_name_filters("WHERE model_name = 'fraud_v3'")
        ['fraud_v3']
        >>> extract_model_name_filters("SELECT 'tm_checks' AS model_name")
        ['tm_checks']
    """
    if not sql:
        return []
    results: list[str] = []
    seen: set[str] = set()

    patterns = [
        r"model_name\s*=\s*'([^']+)'",  # WHERE model_name = 'X'
        r"model_name\s+LIKE\s+'([^']+)'",  # WHERE model_name LIKE 'X%'
        r"'([^']+)'\s+AS\s+model_name",  # 'X' AS model_name
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, sql, re.IGNORECASE):
            val = match.group(1)
            if val not in seen:
                seen.add(val)
                results.append(val)

    # IN (...) lists
    for match in re.finditer(r"model_name\s+IN\s*\(([^)]+)\)", sql, re.IGNORECASE):
        for val in re.findall(r"'([^']+)'", match.group(1)):
            if val not in seen:
                seen.add(val)
                results.append(val)

    return results


def extract_lookback_from_sql(sql: str | None) -> str | None:
    """Extract lookback window from SQL.

    Detects common patterns: lookback=N, DATEADD(day, -N, ...), INTERVAL 'N days'.

    Example:
        >>> extract_lookback_from_sql("WHERE date >= DATEADD(day, -30, CURRENT_DATE())")
        '30 days'
        >>> extract_lookback_from_sql("SELECT 1")
    """
    if not sql:
        return None
    match = re.search(r"lookback\s*=\s*(\d+)", sql, re.IGNORECASE)
    if match:
        return f"{match.group(1)} days"
    match = re.search(r"DATEADD\s*\(\s*day\s*,\s*-(\d+)", sql, re.IGNORECASE)
    if match:
        return f"{match.group(1)} days"
    match = re.search(r"INTERVAL\s+'?(\d+)\s*(?:days?)'?", sql, re.IGNORECASE)
    if match:
        return f"{match.group(1)} days"
    return None


def extract_comment_tags(sql: str | None, prefix: str = "@") -> dict[str, str]:
    """Extract structured tags from SQL comments.

    Parses lines like `-- @key: value` and returns a dict.
    The prefix defaults to "@" but can be customized.

    Example:
        >>> extract_comment_tags("-- @owner: compliance\\n-- @tier: high\\nSELECT 1")
        {'owner': 'compliance', 'tier': 'high'}
    """
    if not sql:
        return {}
    tags: dict[str, str] = {}
    for line in sql.split("\n"):
        line = line.strip()
        if line.startswith(f"-- {prefix}"):
            parts = line[len(f"-- {prefix}") :].split(":", 1)
            if len(parts) == 2:
                tags[parts[0].strip()] = parts[1].strip()
    return tags


def strip_template_vars(sql: str | None) -> str:
    """Strip {{var}} template wrappers from SQL.

    Converts {{schema}}.{{table}} → schema.table.
    Common in ETL platforms that use template variables in SQL.

    Example:
        >>> strip_template_vars("SELECT * FROM {{schema}}.{{table_name}}")
        'SELECT * FROM app_compliance.cash.table'
    """
    if not sql:
        return ""
    return re.sub(r"\{\{(\w+)\}\}", r"\1", sql)
