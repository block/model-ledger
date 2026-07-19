"""LedgerBackend protocol — v0.3.0 storage interface."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from model_ledger.core.ledger_models import ModelRef, Snapshot, Tag


def validate_backend(backend: object | None) -> None:
    """Raise ``TypeError`` early if ``backend`` is not a ``LedgerBackend``.

    Catches the common mistake of passing a ``Ledger`` (or a database path)
    where a storage backend is expected — which would otherwise fail deep
    inside the first operation with a confusing ``AttributeError``.
    """
    if backend is None or isinstance(backend, LedgerBackend):
        return
    from model_ledger.sdk.ledger import Ledger

    hint = ""
    if isinstance(backend, Ledger):
        hint = (
            " — pass the Ledger's storage backend (e.g. SQLiteLedgerBackend), not the Ledger itself"
        )
    elif isinstance(backend, str):
        hint = " — construct a backend from the path first (e.g. SQLiteLedgerBackend(path))"
    raise TypeError(
        f"backend must implement the LedgerBackend protocol; got {type(backend).__name__}{hint}"
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
