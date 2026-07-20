"""Record tool — register a new model or record an event on an existing model."""

from __future__ import annotations

from model_ledger.sdk.ledger import Ledger
from model_ledger.tools.schemas import RecordInput, RecordOutput


def record(input: RecordInput, ledger: Ledger) -> RecordOutput:
    """Register a new model or record an event on an existing model.

    When ``input.event == "registered"``, creates the model via
    ``ledger.register()``, which logs exactly one ``registered`` event
    carrying ``input.payload``. Re-registering an existing model is
    idempotent: no duplicate event is appended.
    Otherwise, looks up the existing model and appends the event.

    Raises:
        ModelNotFoundError: If the model doesn't exist and the event
            is not ``"registered"``.
    """
    if input.event == "registered":
        existing = ledger.backend.get_model_by_name(input.model_name)
        if existing is None:
            model = ledger.register(
                name=input.model_name,
                owner=input.owner or "unknown",
                model_type=input.model_type or "unknown",
                tier=input.tier or "unclassified",
                purpose=input.purpose or "",
                actor=input.actor,
                payload=input.payload or None,
            )
            # register() appended the single canonical "registered" snapshot.
            snapshot = ledger.backend.latest_snapshot(model.model_hash)
            if snapshot is None:  # pragma: no cover — register always logs one
                raise RuntimeError("register() did not log a registration event")
            return RecordOutput(
                model_name=input.model_name,
                model_hash=model.model_hash,
                event_id=snapshot.snapshot_hash,
                timestamp=snapshot.timestamp,
                is_new_model=True,
            )

        # Idempotent re-registration: point at the existing registration
        # event instead of appending a duplicate.
        registered = ledger.backend.list_snapshots(existing.model_hash, event_type="registered")
        if registered:
            snapshot = max(registered, key=lambda s: s.timestamp)
        else:
            # Model exists but has no registration event (e.g. imported
            # data) — log one now so the audit trail is complete.
            snapshot = ledger.record(
                existing,
                event="registered",
                payload=input.payload,
                actor=input.actor,
            )
        return RecordOutput(
            model_name=input.model_name,
            model_hash=existing.model_hash,
            event_id=snapshot.snapshot_hash,
            timestamp=snapshot.timestamp,
            is_new_model=False,
        )

    # Non-registration event: model must already exist
    model = ledger.get(input.model_name)
    snapshot = ledger.record(
        model,
        event=input.event,
        payload=input.payload,
        actor=input.actor,
    )
    return RecordOutput(
        model_name=input.model_name,
        model_hash=model.model_hash,
        event_id=snapshot.snapshot_hash,
        timestamp=snapshot.timestamp,
        is_new_model=False,
    )
