"""Third-party backends resolve via the model_ledger.backends entry-point group (ADR 0005)."""

from __future__ import annotations

import importlib.metadata

from model_ledger.backends import registry
from model_ledger.backends.ledger_memory import InMemoryLedgerBackend
from model_ledger.backends.ledger_protocol import LedgerBackend


class _StubBackend:
    """Stand-in for a downstream package's backend target."""

    def __init__(self, path: str | None = None) -> None:
        self.path = path


class _FakeEntryPoint:
    name = "stub"

    def load(self):
        return _StubBackend


def _fake_entry_points(*, group: str | None = None):
    return [_FakeEntryPoint()] if group == registry.ENTRY_POINT_GROUP else []


def test_load_backend_class_resolves_entry_point(monkeypatch):
    monkeypatch.setattr(importlib.metadata, "entry_points", _fake_entry_points)
    assert registry.load_backend_class("stub") is _StubBackend


def test_load_backend_class_unknown_returns_none(monkeypatch):
    monkeypatch.setattr(importlib.metadata, "entry_points", _fake_entry_points)
    assert registry.load_backend_class("nope") is None


def test_resolve_backend_instantiates_entry_point(monkeypatch):
    monkeypatch.setattr(importlib.metadata, "entry_points", _fake_entry_points)
    from model_ledger.cli.app import _resolve_backend

    backend = _resolve_backend("stub", "conn-str")
    assert isinstance(backend, _StubBackend)
    assert backend.path == "conn-str"


def test_inmemory_backend_satisfies_protocol():
    """Conformance: a real backend is recognized by the runtime-checkable protocol."""
    assert isinstance(InMemoryLedgerBackend(), LedgerBackend)
