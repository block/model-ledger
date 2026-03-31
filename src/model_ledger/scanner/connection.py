"""DBConnection protocol — thin database abstraction for scanners."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DBConnection(Protocol):
    """Minimal database connection interface.

    Any database client that can execute SQL and return rows as dicts
    satisfies this protocol: Postgres, MySQL, BigQuery, Snowflake, SQLite.
    """

    def execute(
        self, query: str, params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...
