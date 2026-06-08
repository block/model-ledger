"""Discover third-party LedgerBackend implementations via entry points.

Built-in backends (in-memory, SQLite, JSON, Snowflake, HTTP) are resolved
directly. This module fulfills the storage-agnostic extension contract from
ADR 0005: a downstream package can register its own backend without any change
to the core, by declaring an entry point —

    # in the downstream package's pyproject.toml
    [project.entry-points."model_ledger.backends"]
    postgres = "my_package:PostgresBackend"

The registered target is called with the connection string if one is given
(``Backend(path)``), otherwise with no arguments (``Backend()``).
"""

from __future__ import annotations

from typing import Any

ENTRY_POINT_GROUP = "model_ledger.backends"


def load_backend_class(name: str) -> Any:
    """Return the backend target registered under ``name``, or ``None`` if absent.

    Args:
        name: The entry-point name to look up in the ``model_ledger.backends`` group.

    Returns:
        The loaded class or factory, or ``None`` if no entry point matches (or the
        metadata is unavailable).
    """
    try:
        from importlib.metadata import entry_points

        for ep in entry_points(group=ENTRY_POINT_GROUP):
            if ep.name == name:
                return ep.load()
    except Exception:
        return None
    return None
