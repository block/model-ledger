"""SQL parsing utilities for SourceConnectors.

Extract table references, write targets, and model_name filters from SQL.
Used by any connector that discovers models from SQL-based systems
(Snowflake, BigQuery, Postgres, etc.).
"""

from __future__ import annotations

import re

# Bare (unqualified) identifiers that can follow FROM/JOIN/INTO in valid SQL
# without naming a table — subqueries, table functions, literal row sources,
# and statement keywords. Qualified names (with dots) are never filtered.
_SQL_NON_TABLE_KEYWORDS = frozenset(
    {
        "select",
        "lateral",
        "unnest",
        "table",
        "values",
        "dual",
        "generator",
        "into",
        "overwrite",
        "if",
        "not",
        "exists",
        "or",
        "replace",
    }
)

_TABLE_IDENTIFIER = r"([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*){0,2})"

# A CTE binding: `WITH [RECURSIVE] name [(cols)] AS (` or a comma-continued
# `, name [(cols)] AS (`. The comma form is only meaningful inside a WITH
# clause, so _extract_cte_names guards on the statement containing WITH.
_CTE_BINDING_PATTERN = re.compile(
    r"(?:\bWITH\s+(?:RECURSIVE\s+)?|,\s*)"
    r"([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\([^()]*\)\s*)?AS\s*\(",
    re.IGNORECASE,
)

# `DELETE FROM target` — the target is neither a read nor (for lineage
# purposes here) a write; strip the FROM so the read extractor skips it.
_DELETE_FROM_PATTERN = re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE)


def _extract_cte_names(sql: str) -> set[str]:
    """Lowercased WITH-clause binding names (including nested/recursive CTEs).

    CTE names are query-local aliases: a reference to one resolves to the
    CTE for the whole statement (even when it shadows a real table), so
    they must never surface as read tables.
    """
    if not re.search(r"\bWITH\b", sql, re.IGNORECASE):
        return set()
    return {m.group(1).lower() for m in _CTE_BINDING_PATTERN.finditer(sql)}


def _is_table_name(identifier: str) -> bool:
    """True unless a bare identifier is really a SQL keyword."""
    return "." in identifier or identifier.lower() not in _SQL_NON_TABLE_KEYWORDS


def extract_tables_from_sql(sql: str | None) -> list[str]:
    """Extract table names from SQL FROM and JOIN clauses.

    Handles fully-qualified (``db.schema.table``), schema-qualified
    (``schema.table``), and bare (``table``) identifiers.
    CTE names (``WITH name AS (...)``) and ``DELETE FROM`` targets are
    excluded — neither is a read table.
    Returns deduplicated list preserving first-seen order.

    Note:
        A bare table genuinely named one of the filtered SQL keywords
        (``values``, ``table``, ``dual``, ...) is not extracted; qualify it
        (``schema.values``) to force extraction.

    Example:
        >>> extract_tables_from_sql("SELECT * FROM schema.table1 JOIN schema.table2 ON 1=1")
        ['schema.table1', 'schema.table2']
        >>> extract_tables_from_sql("SELECT * FROM raw_events")
        ['raw_events']
    """
    if not sql:
        return []
    cte_names = _extract_cte_names(sql)
    sql = _DELETE_FROM_PATTERN.sub("DELETE", sql)
    pattern = rf"(?:FROM|JOIN)\s+{_TABLE_IDENTIFIER}"
    matches = re.findall(pattern, sql, re.IGNORECASE)
    seen: set[str] = set()
    result: list[str] = []
    for table in matches:
        if not _is_table_name(table):
            continue
        lower = table.lower()
        if lower in cte_names:
            continue
        if lower not in seen:
            seen.add(lower)
            result.append(table)
    return result


def extract_write_tables(sql: str | None) -> list[str]:
    """Extract tables that a SQL statement writes to.

    Handles INSERT INTO, INSERT OVERWRITE [TABLE|INTO], CREATE [OR REPLACE]
    TABLE, MERGE INTO, with qualified or bare table identifiers.

    Note:
        A bare table genuinely named one of the filtered SQL keywords
        (``values``, ``table``, ``dual``, ...) is not extracted; qualify it
        (``schema.values``) to force extraction.

    Example:
        >>> extract_write_tables("INSERT INTO schema.output SELECT * FROM source")
        ['schema.output']
        >>> extract_write_tables("INSERT INTO feature_store SELECT * FROM raw_events")
        ['feature_store']
    """
    if not sql:
        return []
    results: list[str] = []
    seen: set[str] = set()

    for pattern in [
        rf"INSERT\s+(?:OVERWRITE\s+)?(?:TABLE\s+|INTO\s+)?{_TABLE_IDENTIFIER}",
        rf"CREATE\s+(?:OR\s+REPLACE\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?{_TABLE_IDENTIFIER}",
        rf"MERGE\s+INTO\s+{_TABLE_IDENTIFIER}",
    ]:
        for match in re.finditer(pattern, sql, re.IGNORECASE):
            if not _is_table_name(match.group(1)):
                continue
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

    Converts ``{{schema}}.{{table}}`` → ``schema.table``. Whitespace inside
    the braces is tolerated, so spaced variables like ``{{ ds }}`` (common
    in scheduler-templated SQL) are stripped too. Common in ETL platforms
    that use template variables in SQL.

    Example:
        >>> strip_template_vars("SELECT * FROM {{schema}}.{{table_name}}")
        'SELECT * FROM schema.table_name'
        >>> strip_template_vars("SELECT * FROM {{ analytics }}.{{ events }}")
        'SELECT * FROM analytics.events'
    """
    if not sql:
        return ""
    return re.sub(r"\{\{\s*(\w+)\s*\}\}", r"\1", sql)
