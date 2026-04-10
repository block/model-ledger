"""Record tool — register a new model or record an event on an existing model."""

from __future__ import annotations

from model_ledger.sdk.ledger import Ledger
from model_ledger.tools.schemas import RecordInput, RecordOutput


def record(input: RecordInput, ledger: Ledger) -> RecordOutput:
    """Register a new model or record an event on an existing model.

    When ``input.event == "registered"``, creates the model via
    ``ledger.register()`` then logs the registration event.
    Otherwise, looks up the existing model and appends the event.

    Raises:
        ModelNotFoundError: If the model doesn't exist and the event
            is not ``"registered"``.
    """
    if input.event == "registered":
        model = ledger.register(
            name=input.model_name,
            owner=input.owner or "unknown",
            model_type=input.model_type or "unknown",
            tier="unclassified",
            purpose=input.purpose or "",
            actor=input.actor,
        )
        snapshot = ledger.record(
            model,
            event="registered",
            payload=input.payload,
            actor=input.actor,
        )
        return RecordOutput(
            model_name=input.model_name,
            event_id=snapshot.snapshot_hash,
            timestamp=snapshot.timestamp,
            is_new_model=True,
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
        event_id=snapshot.snapshot_hash,
        timestamp=snapshot.timestamp,
        is_new_model=False,
    )
