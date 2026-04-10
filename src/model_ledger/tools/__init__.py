"""Agent protocol tools — Pydantic I/O schemas and tool functions.

Re-exports all schemas and all tool functions.
"""

from model_ledger.tools.changelog import changelog
from model_ledger.tools.discover import discover
from model_ledger.tools.investigate import investigate
from model_ledger.tools.query import query
from model_ledger.tools.record import record
from model_ledger.tools.schemas import (
    ChangelogInput,
    ChangelogOutput,
    DependencyNode,
    DiscoverInput,
    DiscoverOutput,
    EventDetail,
    EventSummary,
    InvestigateInput,
    InvestigateOutput,
    ModelSummary,
    QueryInput,
    QueryOutput,
    RecordInput,
    RecordOutput,
    TraceInput,
    TraceOutput,
)
from model_ledger.tools.trace import trace

__all__ = [
    # Shared types
    "ModelSummary",
    "EventSummary",
    "EventDetail",
    "DependencyNode",
    # Tool functions
    "changelog",
    "discover",
    "investigate",
    "query",
    "record",
    "trace",
    # record
    "RecordInput",
    "RecordOutput",
    # query
    "QueryInput",
    "QueryOutput",
    # investigate
    "InvestigateInput",
    "InvestigateOutput",
    # trace
    "TraceInput",
    "TraceOutput",
    # changelog
    "ChangelogInput",
    "ChangelogOutput",
    # discover
    "DiscoverInput",
    "DiscoverOutput",
]
