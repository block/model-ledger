"""SourceConnector protocol — the extension point for platform discovery."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from model_ledger.graph.models import DataNode


@runtime_checkable
class SourceConnector(Protocol):
    name: str

    def discover(self) -> list[DataNode]: ...
