# tests/test_tools/test_tag.py
"""Tests for the tag tool — create tags and list tags on models."""

from __future__ import annotations

import pytest

from model_ledger.backends.ledger_memory import InMemoryLedgerBackend
from model_ledger.core.exceptions import ModelNotFoundError
from model_ledger.sdk.ledger import Ledger
from model_ledger.tools.schemas import TagInput, TagListOutput, TagOutput
from model_ledger.tools.tag import list_tags, tag


@pytest.fixture
def ledger():
    return Ledger(backend=InMemoryLedgerBackend())


@pytest.fixture
def registered_ledger(ledger):
    ledger.register(
        name="credit-scorecard",
        owner="risk-team",
        model_type="ml_model",
        tier="unclassified",
        purpose="Credit risk scoring",
    )
    return ledger


class TestTagTool:
    """tag() creates a tag pointing at the latest snapshot."""

    def test_tag_returns_output_with_all_fields(self, registered_ledger):
        inp = TagInput(model_name="credit-scorecard", tag_name="v1.0")
        result = tag(inp, registered_ledger)

        assert isinstance(result, TagOutput)
        assert result.model_name == "credit-scorecard"
        assert result.tag_name == "v1.0"
        assert result.model_hash  # non-empty
        assert result.snapshot_hash  # non-empty
        assert result.updated_at is not None

    def test_tag_points_at_latest_snapshot(self, registered_ledger):
        latest = registered_ledger._backend.latest_snapshot(
            registered_ledger.get("credit-scorecard").model_hash,
        )
        result = tag(TagInput(model_name="credit-scorecard", tag_name="latest"), registered_ledger)
        assert result.snapshot_hash == latest.snapshot_hash

    def test_tag_overwrites_existing(self, registered_ledger):
        tag(TagInput(model_name="credit-scorecard", tag_name="prod"), registered_ledger)

        # Record a new event so the latest snapshot changes
        model = registered_ledger.get("credit-scorecard")
        registered_ledger.record(model, event="validated", payload={"auc": 0.92}, actor="qa")

        # Move the tag forward
        result = tag(TagInput(model_name="credit-scorecard", tag_name="prod"), registered_ledger)
        latest = registered_ledger._backend.latest_snapshot(model.model_hash)
        assert result.snapshot_hash == latest.snapshot_hash

    def test_tag_nonexistent_model_raises(self, ledger):
        with pytest.raises(ModelNotFoundError):
            tag(TagInput(model_name="does-not-exist", tag_name="v1.0"), ledger)


class TestListTags:
    """list_tags() returns all tags for a model."""

    def test_empty_when_no_tags(self, registered_ledger):
        result = list_tags("credit-scorecard", registered_ledger)
        assert isinstance(result, TagListOutput)
        assert result.model_name == "credit-scorecard"
        assert result.tags == []

    def test_returns_all_tags(self, registered_ledger):
        tag(TagInput(model_name="credit-scorecard", tag_name="v1.0"), registered_ledger)
        tag(TagInput(model_name="credit-scorecard", tag_name="prod"), registered_ledger)

        result = list_tags("credit-scorecard", registered_ledger)
        assert len(result.tags) == 2
        names = {t.tag_name for t in result.tags}
        assert names == {"v1.0", "prod"}

    def test_nonexistent_model_raises(self, ledger):
        with pytest.raises(ModelNotFoundError):
            list_tags("does-not-exist", ledger)

    def test_tag_list_output_contains_full_tag_fields(self, registered_ledger):
        tag(TagInput(model_name="credit-scorecard", tag_name="v1.0"), registered_ledger)

        result = list_tags("credit-scorecard", registered_ledger)
        t = result.tags[0]
        assert t.model_name == "credit-scorecard"
        assert t.tag_name == "v1.0"
        assert t.model_hash
        assert t.snapshot_hash
        assert t.updated_at is not None
