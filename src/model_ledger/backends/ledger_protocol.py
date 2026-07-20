"""LedgerBackend protocol — v0.3.0 storage interface."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Protocol, runtime_checkable

from model_ledger.core.ledger_models import ModelRef, Snapshot, Tag

# The duck-typing floor for validate_backend. Deliberately a SUBSET of the
# protocol: handwritten third-party backends that skip optional methods
# (list_snapshots_before, tag methods) must keep constructing — the goal is
# to catch obviously-wrong arguments early, not to enforce completeness.
_CORE_BACKEND_METHODS = (
    "save_model",
    "get_model_by_name",
    "list_models",
    "append_snapshot",
    "list_snapshots",
)


def validate_backend(backend: object | None) -> None:
    """Raise ``TypeError`` early if ``backend`` is clearly not a ``LedgerBackend``.

    Catches the common mistake of passing a ``Ledger`` (or a database path)
    where a storage backend is expected — which would otherwise fail deep
    inside the first operation with a confusing ``AttributeError``. Uses a
    core-method duck check rather than full-protocol ``isinstance`` so
    partial custom backends are not rejected.
    """
    if backend is None:
        return
    from model_ledger.sdk.ledger import Ledger

    if isinstance(backend, Ledger):
        raise TypeError(
            "backend must implement the LedgerBackend protocol; got Ledger"
            " — pass the Ledger's storage backend (e.g. SQLiteLedgerBackend), not the Ledger itself"
        )
    if isinstance(backend, str | os.PathLike):
        raise TypeError(
            f"backend must implement the LedgerBackend protocol; got {type(backend).__name__}"
            " — construct a backend from the path first (e.g. SQLiteLedgerBackend(path))"
        )
    missing = [m for m in _CORE_BACKEND_METHODS if not callable(getattr(backend, m, None))]
    if missing:
        raise TypeError(
            f"backend must implement the LedgerBackend protocol; got {type(backend).__name__}"
            f" (missing {', '.join(missing)})"
        )


@runtime_checkable
class LedgerBackend(Protocol):
    def save_model(self, model: ModelRef) -> None: ...
    def get_model(self, model_hash: str) -> ModelRef | None: ...
    def get_model_by_name(self, name: str) -> ModelRef | None: ...
    def list_models(self, **filters: str) -> list[ModelRef]: ...
    def update_model(self, model: ModelRef) -> None: ...

    def append_snapshot(self, snapshot: Snapshot) -> None: ...
    def get_snapshot(self, snapshot_hash: str) -> Snapshot | None: ...
    def list_snapshots(self, model_hash: str, **filters: str) -> list[Snapshot]: ...
    def latest_snapshot(self, model_hash: str, tag: str | None = None) -> Snapshot | None: ...

    def list_snapshots_before(
        self,
        model_hash: str,
        before: datetime,
        event_type: str | None = None,
    ) -> list[Snapshot]: ...

    def set_tag(self, tag: Tag) -> None: ...
    def get_tag(self, model_hash: str, name: str) -> Tag | None: ...
    def list_tags(self, model_hash: str) -> list[Tag]: ...
