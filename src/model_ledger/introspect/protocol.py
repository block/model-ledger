"""Introspector protocol — the interface all introspectors must implement."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from model_ledger.introspect.models import IntrospectionResult


@runtime_checkable
class Introspector(Protocol):
    """Extracts metadata from a model object or config."""

    name: str

    def can_handle(self, obj: Any) -> bool: ...
    def introspect(self, obj: Any) -> IntrospectionResult: ...
