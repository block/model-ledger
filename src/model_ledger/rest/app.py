"""FastAPI application wrapping the 6 model-ledger tool functions.

Usage::

    from model_ledger.rest.app import create_app

    app = create_app()              # in-memory backend
    app = create_app(demo=True)     # pre-loaded demo data (if available)

    # With a custom backend
    from model_ledger.backends.sqlite_ledger import SQLiteLedgerBackend
    app = create_app(backend=SQLiteLedgerBackend("inventory.db"))

Run with uvicorn::

    uvicorn model_ledger.rest.app:app --reload
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException

from model_ledger.backends import batch_fallbacks
from model_ledger.backends.ledger_protocol import LedgerBackend
from model_ledger.core.exceptions import ModelNotFoundError
from model_ledger.sdk.ledger import Ledger
from model_ledger.tools.changelog import changelog as changelog_fn
from model_ledger.tools.discover import discover as discover_fn
from model_ledger.tools.investigate import investigate as investigate_fn
from model_ledger.tools.query import query as query_fn
from model_ledger.tools.record import record as record_fn
from model_ledger.tools.schemas import (
    ChangelogInput,
    ChangelogOutput,
    DiscoverInput,
    DiscoverOutput,
    InvestigateOutput,
    QueryInput,
    QueryOutput,
    RecordInput,
    RecordOutput,
    TagInput,
    TagListOutput,
    TagOutput,
    TraceInput,
    TraceOutput,
)
from model_ledger.tools.tag import list_tags as list_tags_fn
from model_ledger.tools.tag import tag as tag_fn
from model_ledger.tools.trace import trace as trace_fn


def create_app(
    backend: LedgerBackend | None = None,
    demo: bool = False,
) -> FastAPI:
    """Create a FastAPI app wrapping the model-ledger tool functions.

    Args:
        backend: Optional ledger backend. Defaults to in-memory.
        demo: If True, pre-loads demo inventory data (requires Task 11).

    Returns:
        A configured FastAPI application.
    """
    ledger = Ledger(backend=backend)

    if demo:
        try:
            from model_ledger.datasets.demo import load_demo_inventory  # type: ignore[import-not-found]  # noqa: I001

            load_demo_inventory(ledger)
        except ImportError:
            pass  # demo dataset not yet available (Task 11)

    app = FastAPI(
        title="Model Ledger API",
        description="REST API for model inventory and governance",
        version="0.5.0",
    )

    @app.post("/record", response_model=RecordOutput)
    def record_endpoint(body: RecordInput) -> RecordOutput:
        try:
            return record_fn(body, ledger)
        except ModelNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/discover", response_model=DiscoverOutput)
    def discover_endpoint(body: DiscoverInput) -> DiscoverOutput:
        return discover_fn(body, ledger)

    @app.get("/investigate/{model_name}", response_model=InvestigateOutput)
    def investigate_endpoint(model_name: str) -> InvestigateOutput:
        from model_ledger.tools.schemas import InvestigateInput

        try:
            return investigate_fn(InvestigateInput(model_name=model_name), ledger)
        except ModelNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/query", response_model=QueryOutput)
    def query_endpoint(
        text: str | None = None,
        platform: str | None = None,
        model_type: str | None = None,
        owner: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> QueryOutput:
        inp = QueryInput(
            text=text,
            platform=platform,
            model_type=model_type,
            owner=owner,
            status=status,
            limit=limit,
            offset=offset,
        )
        return query_fn(inp, ledger)

    @app.get("/trace/{name}", response_model=TraceOutput)
    def trace_endpoint(
        name: str,
        direction: str = "both",
        depth: int | None = None,
    ) -> TraceOutput:
        inp = TraceInput(name=name, direction=direction, depth=depth)  # type: ignore[arg-type]
        try:
            return trace_fn(inp, ledger)
        except ModelNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/changelog", response_model=ChangelogOutput)
    def changelog_endpoint(
        since: str | None = None,
        until: str | None = None,
        model_name: str | None = None,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> ChangelogOutput:
        since_dt = datetime.fromisoformat(since) if since else None
        until_dt = datetime.fromisoformat(until) if until else None
        inp = ChangelogInput(
            since=since_dt,
            until=until_dt,
            model_name=model_name,
            event_type=event_type,
            limit=limit,
            offset=offset,
        )
        try:
            return changelog_fn(inp, ledger)
        except ModelNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/tag", response_model=TagOutput)
    def tag_endpoint(body: TagInput) -> TagOutput:
        try:
            return tag_fn(body, ledger)
        except ModelNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/tags/{model_name}", response_model=TagListOutput)
    def list_tags_endpoint(model_name: str) -> TagListOutput:
        try:
            return list_tags_fn(model_name, ledger)
        except ModelNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/overview")
    def overview_endpoint() -> dict[str, Any]:
        models = ledger.list()
        backend = ledger._backend
        if hasattr(backend, "count_all_snapshots"):
            total_events = backend.count_all_snapshots()
        else:
            total_events = batch_fallbacks.count_all_snapshots(backend)
        return {
            "total_models": len(models),
            "total_events": total_events,
        }

    return app


app = create_app()
