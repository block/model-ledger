"""FastMCP server wrapping model-ledger's 6 tools and 3 resources.

Usage:
    >>> from model_ledger.mcp.server import create_server
    >>> server = create_server()
    >>> server.run()  # stdio transport

CLI entry point:
    $ model-ledger mcp --demo
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from model_ledger.backends.ledger_memory import InMemoryLedgerBackend
from model_ledger.backends.ledger_protocol import LedgerBackend
from model_ledger.sdk.ledger import Ledger
from model_ledger.tools import schemas
from model_ledger.tools.changelog import changelog as _changelog
from model_ledger.tools.discover import discover as _discover
from model_ledger.tools.investigate import investigate as _investigate
from model_ledger.tools.query import query as _query
from model_ledger.tools.record import record as _record
from model_ledger.tools.trace import trace as _trace


def create_server(
    backend: LedgerBackend | None = None,
    demo: bool = False,
) -> FastMCP:
    """Create a FastMCP server with model-ledger tools and resources.

    Args:
        backend: Optional storage backend. Defaults to InMemoryLedgerBackend.
            If an HttpLedgerBackend is provided, tools call the remote REST API
            directly instead of going through the Ledger SDK.
        demo: If True, pre-populate with sample data (requires datasets.demo module).

    Returns:
        A configured FastMCP server ready to ``run()``.
    """
    from model_ledger.backends.http import HttpLedgerBackend

    # HTTP backend → pass-through mode: call REST API directly
    if isinstance(backend, HttpLedgerBackend):
        return _create_http_server(backend)

    if backend is None:
        backend = InMemoryLedgerBackend()

    ledger = Ledger(backend=backend)

    if demo:
        try:
            from model_ledger.datasets.demo import load_demo_inventory

            load_demo_inventory(ledger)
        except ImportError:
            pass

    mcp = FastMCP("model-ledger")

    # ------------------------------------------------------------------
    # Tools (6) — thin wrappers that convert primitives -> Pydantic -> tool fn
    # ------------------------------------------------------------------

    @mcp.tool()
    def discover(
        source_type: str,
        models: list[dict] | None = None,
        connector_name: str | None = None,
        connector_config: dict | None = None,
        file_path: str | None = None,
        auto_connect: bool = True,
    ) -> dict:
        """Import models from external sources into the ledger.

        Supports inline model dicts, JSON files, or named connectors.
        Returns counts of models added/skipped and links created.
        """
        inp = schemas.DiscoverInput(
            source_type=source_type,  # type: ignore[arg-type]
            models=models,
            connector_name=connector_name,
            connector_config=connector_config,
            file_path=file_path,
            auto_connect=auto_connect,
        )
        return _discover(inp, ledger).model_dump(mode="json")

    @mcp.tool()
    def record(
        model_name: str,
        event: str,
        payload: dict | None = None,
        actor: str = "user",
        owner: str | None = None,
        model_type: str | None = None,
        purpose: str | None = None,
    ) -> dict:
        """Register a new model or record an event on an existing model.

        Use event='registered' to create a new model. Any other event
        value appends to an existing model's history.
        """
        inp = schemas.RecordInput(
            model_name=model_name,
            event=event,
            payload=payload or {},
            actor=actor,
            owner=owner,
            model_type=model_type,
            purpose=purpose,
        )
        return _record(inp, ledger).model_dump(mode="json")

    @mcp.tool()
    def investigate(
        model_name: str,
        detail: str = "summary",
        as_of: str | None = None,
    ) -> dict:
        """Deep-dive into a single model — history, metadata, dependencies.

        Returns owner, type, status, recent events, upstream/downstream
        dependencies, and group memberships.
        """
        from datetime import datetime, timezone

        as_of_dt = None
        if as_of is not None:
            as_of_dt = datetime.fromisoformat(as_of)
            if as_of_dt.tzinfo is None:
                as_of_dt = as_of_dt.replace(tzinfo=timezone.utc)

        inp = schemas.InvestigateInput(
            model_name=model_name,
            detail=detail,  # type: ignore[arg-type]
            as_of=as_of_dt,
        )
        return _investigate(inp, ledger).model_dump(mode="json")

    @mcp.tool()
    def query(
        text: str | None = None,
        platform: str | None = None,
        model_type: str | None = None,
        owner: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Search and filter the model inventory.

        Supports text search (fuzzy name/purpose match) and structured
        filters (platform, model_type, owner, status) with pagination.
        """
        inp = schemas.QueryInput(
            text=text,
            platform=platform,
            model_type=model_type,
            owner=owner,
            status=status,
            limit=limit,
            offset=offset,
        )
        return _query(inp, ledger).model_dump(mode="json")

    @mcp.tool()
    def trace(
        name: str,
        direction: str = "both",
        depth: int | None = None,
    ) -> dict:
        """Traverse a model's dependency graph.

        Walks upstream (models this one depends on) and/or downstream
        (models that depend on this one). Returns dependency nodes with
        depth and relationship metadata.
        """
        inp = schemas.TraceInput(
            name=name,
            direction=direction,  # type: ignore[arg-type]
            depth=depth,
        )
        return _trace(inp, ledger).model_dump(mode="json")

    @mcp.tool()
    def changelog(
        since: str | None = None,
        until: str | None = None,
        model_name: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """View cross-model event history with time range filtering.

        Returns events sorted newest-first with pagination. Defaults
        to the last 7 days if no time range is specified.
        """
        from datetime import datetime, timezone

        since_dt = None
        if since is not None:
            since_dt = datetime.fromisoformat(since)
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)

        until_dt = None
        if until is not None:
            until_dt = datetime.fromisoformat(until)
            if until_dt.tzinfo is None:
                until_dt = until_dt.replace(tzinfo=timezone.utc)

        inp = schemas.ChangelogInput(
            since=since_dt,
            until=until_dt,
            model_name=model_name,
            event_type=event_type,
            limit=limit,
            offset=offset,
        )
        return _changelog(inp, ledger).model_dump(mode="json")

    # ------------------------------------------------------------------
    # Resources (3)
    # ------------------------------------------------------------------

    @mcp.resource("ledger://overview")
    def overview() -> str:
        """Inventory statistics — model count, event count, type breakdown."""
        models = ledger.list()
        type_counts: dict[str, int] = {}
        total_events = 0
        for m in models:
            mt = m.model_type or "unknown"
            type_counts[mt] = type_counts.get(mt, 0) + 1
            total_events += len(ledger.history(m))

        data: dict[str, Any] = {
            "total_models": len(models),
            "total_events": total_events,
            "model_types": type_counts,
        }
        return json.dumps(data, indent=2)

    @mcp.resource("ledger://schema")
    def schema_resource() -> str:
        """JSON Schema definitions for all tool I/O models."""
        all_schemas: dict[str, Any] = {}
        for cls in [
            schemas.DiscoverInput,
            schemas.DiscoverOutput,
            schemas.RecordInput,
            schemas.RecordOutput,
            schemas.QueryInput,
            schemas.QueryOutput,
            schemas.InvestigateInput,
            schemas.InvestigateOutput,
            schemas.TraceInput,
            schemas.TraceOutput,
            schemas.ChangelogInput,
            schemas.ChangelogOutput,
        ]:
            all_schemas[cls.__name__] = cls.model_json_schema()  # type: ignore[attr-defined]
        return json.dumps(all_schemas, indent=2)

    @mcp.resource("ledger://backends")
    def backends_resource() -> str:
        """Active backend configuration."""
        backend_type = type(backend).__name__
        data: dict[str, Any] = {
            "backend": backend_type,
            "demo": demo,
        }
        return json.dumps(data, indent=2)

    return mcp


def _create_http_server(http_backend: Any) -> FastMCP:
    """Create MCP server that passes through to a remote REST API.

    Instead of going through the Ledger SDK (which can't fully work over
    HTTP), the tools call the REST API endpoints directly. The server-side
    REST API does all the computation.
    """
    client = http_backend._client
    mcp = FastMCP("model-ledger")

    @mcp.tool()
    def discover(
        source_type: str,
        models: list[dict] | None = None,
        connector_name: str | None = None,
        connector_config: dict | None = None,
        file_path: str | None = None,
        auto_connect: bool = True,
    ) -> dict:
        """Import models from external sources into the ledger.

        Supports inline model dicts, JSON files, or named connectors.
        Returns counts of models added/skipped and links created.
        """
        resp = client.post(
            "/discover",
            json={
                "source_type": source_type,
                "models": models,
                "connector_name": connector_name,
                "connector_config": connector_config,
                "file_path": file_path,
                "auto_connect": auto_connect,
            },
        )
        return resp.json()  # type: ignore[no-any-return]

    @mcp.tool()
    def record(
        model_name: str,
        event: str,
        payload: dict | None = None,
        actor: str = "user",
        owner: str | None = None,
        model_type: str | None = None,
        purpose: str | None = None,
    ) -> dict:
        """Register a new model or record an event on an existing model.

        Use event='registered' to create a new model. Any other event
        value appends to an existing model's history.
        """
        resp = client.post(
            "/record",
            json={
                "model_name": model_name,
                "event": event,
                "payload": payload or {},
                "actor": actor,
                "owner": owner,
                "model_type": model_type,
                "purpose": purpose,
            },
        )
        return resp.json()  # type: ignore[no-any-return]

    @mcp.tool()
    def investigate(
        model_name: str,
        detail: str = "summary",
        as_of: str | None = None,
    ) -> dict:
        """Deep-dive into a single model — history, metadata, dependencies.

        Returns owner, type, status, recent events, upstream/downstream
        dependencies, and group memberships.
        """
        params: dict[str, Any] = {"detail": detail}
        if as_of:
            params["as_of"] = as_of
        resp = client.get(f"/investigate/{model_name}", params=params)
        return resp.json()  # type: ignore[no-any-return]

    @mcp.tool()
    def query(
        text: str | None = None,
        platform: str | None = None,
        model_type: str | None = None,
        owner: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Search and filter the model inventory.

        Supports text search (fuzzy name/purpose match) and structured
        filters (platform, model_type, owner, status) with pagination.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if text:
            params["text"] = text
        if platform:
            params["platform"] = platform
        if model_type:
            params["model_type"] = model_type
        if owner:
            params["owner"] = owner
        if status:
            params["status"] = status
        resp = client.get("/query", params=params)
        return resp.json()  # type: ignore[no-any-return]

    @mcp.tool()
    def trace(
        name: str,
        direction: str = "both",
        depth: int | None = None,
    ) -> dict:
        """Traverse a model's dependency graph.

        Walks upstream (models this one depends on) and/or downstream
        (models that depend on this one). Returns dependency nodes with
        depth and relationship metadata.
        """
        params: dict[str, Any] = {"direction": direction}
        if depth is not None:
            params["depth"] = depth
        resp = client.get(f"/trace/{name}", params=params)
        return resp.json()  # type: ignore[no-any-return]

    @mcp.tool()
    def changelog(
        since: str | None = None,
        until: str | None = None,
        model_name: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """View cross-model event history with time range filtering.

        Returns events sorted newest-first with pagination. Defaults
        to the last 7 days if no time range is specified.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        if model_name:
            params["model_name"] = model_name
        if event_type:
            params["event_type"] = event_type
        resp = client.get("/changelog", params=params)
        return resp.json()  # type: ignore[no-any-return]

    @mcp.resource("ledger://overview")
    def overview() -> str:
        """Inventory statistics — model count, event count, type breakdown."""
        resp = client.get("/overview")
        return json.dumps(resp.json(), indent=2)

    @mcp.resource("ledger://schema")
    def schema_resource() -> str:
        """JSON Schema definitions for all tool I/O models."""
        all_schemas: dict[str, Any] = {}
        for cls in [
            schemas.DiscoverInput,
            schemas.DiscoverOutput,
            schemas.RecordInput,
            schemas.RecordOutput,
            schemas.QueryInput,
            schemas.QueryOutput,
            schemas.InvestigateInput,
            schemas.InvestigateOutput,
            schemas.TraceInput,
            schemas.TraceOutput,
            schemas.ChangelogInput,
            schemas.ChangelogOutput,
        ]:
            all_schemas[cls.__name__] = cls.model_json_schema()  # type: ignore[attr-defined]
        return json.dumps(all_schemas, indent=2)

    @mcp.resource("ledger://backends")
    def backends_resource() -> str:
        """Active backend configuration."""
        return json.dumps({"backend": "http", "url": str(client.base_url)}, indent=2)

    return mcp


def main() -> None:
    """Entry point for ``model-ledger mcp`` command.

    Parses --backend, --path, and --demo arguments, creates the server,
    and runs it on stdio transport.
    """
    import argparse

    parser = argparse.ArgumentParser(description="model-ledger MCP server")
    parser.add_argument(
        "--backend",
        choices=["memory", "sqlite", "json", "snowflake", "http"],
        default="memory",
        help="Storage backend (default: memory)",
    )
    parser.add_argument(
        "--path",
        default=None,
        help="Path for sqlite/json backend, or URL for http backend",
    )
    parser.add_argument(
        "--schema",
        default=None,
        help="Snowflake schema (e.g., MY_DB.MODEL_LEDGER)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Pre-populate with sample data",
    )

    args = parser.parse_args(sys.argv[1:])

    backend: LedgerBackend | None = None
    if args.backend == "sqlite":
        from model_ledger.backends.sqlite_ledger import SQLiteLedgerBackend

        path = args.path or "ledger.db"
        backend = SQLiteLedgerBackend(path)
    elif args.backend == "json":
        from model_ledger.backends.json_files import JsonFileLedgerBackend

        path = args.path or "./ledger-data"
        backend = JsonFileLedgerBackend(path)
    elif args.backend == "snowflake":
        # Delegate to CLI helper which handles snowflake-connector-python
        from model_ledger.cli.app import _snowflake_backend

        backend = _snowflake_backend(args.schema)
    elif args.backend == "http":
        from model_ledger.backends.http import HttpLedgerBackend

        url = args.path or os.environ.get("MODEL_LEDGER_URL")
        if not url:
            print("HTTP backend requires --path <url> or MODEL_LEDGER_URL env var", file=sys.stderr)
            sys.exit(1)
        backend = HttpLedgerBackend(url)
    # else: memory — use None (create_server default)

    server = create_server(backend=backend, demo=args.demo)
    server.run()
