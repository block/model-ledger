"""Introspector registry with lazy entry point discovery."""

from __future__ import annotations

from typing import Any

from model_ledger.core.exceptions import NoIntrospectorError
from model_ledger.introspect.protocol import Introspector

ENTRY_POINT_GROUP = "model_ledger.introspectors"

_registry: IntrospectorRegistry | None = None


class IntrospectorRegistry:
    def __init__(self) -> None:
        self._introspectors: list[Introspector] = []
        self._discovered = False

    def register(self, introspector: Introspector) -> None:
        """Register an introspector. Deduplicates by name. Prepends for priority."""
        self._introspectors = [i for i in self._introspectors if i.name != introspector.name]
        self._introspectors.insert(0, introspector)

    def find(self, obj: Any) -> Introspector:
        """Find first introspector that can handle obj."""
        self._ensure_discovered()
        for intro in self._introspectors:
            if intro.can_handle(obj):
                return intro
        raise NoIntrospectorError(type(obj))

    def get_by_name(self, name: str) -> Introspector:
        """Get introspector by name."""
        self._ensure_discovered()
        for intro in self._introspectors:
            if intro.name == name:
                return intro
        raise NoIntrospectorError(name)

    def _ensure_discovered(self) -> None:
        """Lazy-load entry points on first use."""
        if self._discovered:
            return
        self._discovered = True
        try:
            from importlib.metadata import entry_points

            eps = entry_points(group=ENTRY_POINT_GROUP)
            for ep in sorted(eps, key=lambda e: e.name):
                try:
                    cls = ep.load()
                    instance = cls()
                    if not any(i.name == instance.name for i in self._introspectors):
                        self._introspectors.append(instance)
                except Exception:
                    pass
        except Exception:
            pass


def get_registry() -> IntrospectorRegistry:
    """Get or create the global introspector registry."""
    global _registry
    if _registry is None:
        _registry = IntrospectorRegistry()
    return _registry


def reset_registry() -> None:
    """Reset the global registry. Used in tests."""
    global _registry
    _registry = None


def register_introspector(introspector: Introspector) -> None:
    """Convenience function to register an introspector globally."""
    get_registry().register(introspector)
