"""MCP (Model Context Protocol) server for model-ledger.

Exposes model-ledger tools and resources via the FastMCP framework,
allowing AI assistants to interact with the model inventory.

    >>> from model_ledger.mcp.server import create_server
    >>> server = create_server()
"""

from __future__ import annotations

__all__ = ["create_server", "main"]


def __getattr__(name: str):  # noqa: ANN001
    """Lazy import to avoid hard dep on mcp at package level."""
    if name in __all__:
        from model_ledger.mcp.server import create_server, main

        return {"create_server": create_server, "main": main}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
