"""Tag tool — create or move a tag to a model's latest snapshot."""

from __future__ import annotations

from model_ledger.core.ledger_models import Tag
from model_ledger.sdk.ledger import Ledger
from model_ledger.tools.schemas import TagInput, TagListOutput, TagOutput


def tag(input: TagInput, ledger: Ledger) -> TagOutput:
    """Create or move a tag pointing at the model's latest snapshot.

    Raises:
        ModelNotFoundError: If the model doesn't exist.
        ValueError: If the model has no snapshots to tag.
    """
    created = ledger.tag(input.model_name, input.tag_name)
    return _tag_to_output(input.model_name, created)


def list_tags(model_name: str, ledger: Ledger) -> TagListOutput:
    """Return all tags attached to a model."""
    ref = ledger.get(model_name)
    tags = ledger._backend.list_tags(ref.model_hash)
    return TagListOutput(
        model_name=model_name,
        tags=[_tag_to_output(model_name, t) for t in tags],
    )


def _tag_to_output(model_name: str, tag: Tag) -> TagOutput:
    return TagOutput(
        model_name=model_name,
        tag_name=tag.name,
        model_hash=tag.model_hash,
        snapshot_hash=tag.snapshot_hash,
        updated_at=tag.updated_at,
    )
