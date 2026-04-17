# tests/test_tools/test_changelog.py
"""Tests for the changelog tool — cross-model event timeline."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from model_ledger.backends.ledger_memory import InMemoryLedgerBackend
from model_ledger.sdk.ledger import Ledger
from model_ledger.tools.changelog import changelog
from model_ledger.tools.record import record
from model_ledger.tools.schemas import (
    ChangelogInput,
    ChangelogOutput,
    EventDetail,
    RecordInput,
)


@pytest.fixture
def ledger():
    return Ledger(backend=InMemoryLedgerBackend())


def _seed(ledger):
    """Create 3 models with events matching the task spec."""
    for name in ["model_a", "model_b", "model_c"]:
        record(
            RecordInput(
                model_name=name,
                event="registered",
                owner="team",
                model_type="ml_model",
                purpose="test",
            ),
            ledger,
        )
    record(RecordInput(model_name="model_a", event="retrained", actor="pipeline"), ledger)
    record(RecordInput(model_name="model_b", event="deployed", actor="ci"), ledger)


class TestAllEvents:
    """No filters — all events returned."""

    def test_returns_all_events(self, ledger):
        _seed(ledger)

        result = changelog(ChangelogInput(), ledger)

        assert isinstance(result, ChangelogOutput)
        assert result.total >= 5
        assert len(result.events) >= 5
        for ev in result.events:
            assert isinstance(ev, EventDetail)
            assert ev.model_name is not None
            assert ev.event_type

    def test_period_defaults_to_last_7_days(self, ledger):
        _seed(ledger)

        result = changelog(ChangelogInput(), ledger)

        assert result.period is not None
        assert "7 days" in result.period


class TestFilterByModelName:
    """Filter by model_name — only that model's events."""

    def test_filter_single_model(self, ledger):
        _seed(ledger)

        result = changelog(ChangelogInput(model_name="model_a"), ledger)

        assert result.total >= 1
        for ev in result.events:
            assert ev.model_name == "model_a"

    def test_filter_model_with_extra_events(self, ledger):
        _seed(ledger)

        result = changelog(ChangelogInput(model_name="model_a"), ledger)

        event_types = [ev.event_type for ev in result.events]
        assert "registered" in event_types
        assert "retrained" in event_types


class TestFilterByEventType:
    """Filter by event_type — only matching events."""

    def test_filter_retrained(self, ledger):
        _seed(ledger)

        result = changelog(ChangelogInput(event_type="retrained"), ledger)

        assert result.total >= 1
        for ev in result.events:
            assert ev.event_type == "retrained"
        model_names = [ev.model_name for ev in result.events]
        assert "model_a" in model_names

    def test_filter_deployed(self, ledger):
        _seed(ledger)

        result = changelog(ChangelogInput(event_type="deployed"), ledger)

        assert result.total >= 1
        for ev in result.events:
            assert ev.event_type == "deployed"

    def test_filter_event_type_no_match(self, ledger):
        _seed(ledger)

        result = changelog(ChangelogInput(event_type="nonexistent"), ledger)

        assert result.total == 0
        assert result.events == []


class TestPagination:
    """Pagination with limit/offset and has_more."""

    def test_limit_returns_subset(self, ledger):
        _seed(ledger)

        result = changelog(ChangelogInput(limit=2), ledger)

        assert len(result.events) == 2
        assert result.has_more is True
        assert result.total >= 5

    def test_offset_skips(self, ledger):
        _seed(ledger)

        full = changelog(ChangelogInput(), ledger)
        page2 = changelog(ChangelogInput(limit=2, offset=2), ledger)

        assert page2.total == full.total
        page1 = changelog(ChangelogInput(limit=2, offset=0), ledger)
        page1_ids = [(e.model_name, e.timestamp) for e in page1.events]
        page2_ids = [(e.model_name, e.timestamp) for e in page2.events]
        assert page1_ids != page2_ids

    def test_offset_beyond_total(self, ledger):
        _seed(ledger)

        result = changelog(ChangelogInput(limit=10, offset=1000), ledger)

        assert result.total >= 5
        assert len(result.events) == 0
        assert result.has_more is False


class TestNewestFirstOrdering:
    """Events sorted by timestamp descending (newest first)."""

    def test_newest_first(self, ledger):
        _seed(ledger)

        result = changelog(ChangelogInput(), ledger)

        timestamps = [ev.timestamp for ev in result.events]
        for i in range(len(timestamps) - 1):
            assert timestamps[i] >= timestamps[i + 1], (
                f"Event {i} ({timestamps[i]}) should be >= event {i + 1} ({timestamps[i + 1]})"
            )


class TestEmptyInventory:
    """Empty inventory returns total=0."""

    def test_empty_returns_zero(self, ledger):
        result = changelog(ChangelogInput(), ledger)

        assert result.total == 0
        assert result.events == []
        assert result.has_more is False


class TestChangelogBatchDispatch:
    """Changelog produces correct output via fallback batch dispatch."""

    def test_fallback_dispatch_returns_events(self, ledger):
        _seed(ledger)
        assert not hasattr(ledger._backend, "changelog_page")

        result = changelog(ChangelogInput(), ledger)

        assert result.total >= 5
        for ev in result.events:
            assert isinstance(ev, EventDetail)

    def test_model_name_filter_via_fallback(self, ledger):
        _seed(ledger)

        result = changelog(ChangelogInput(model_name="model_a"), ledger)

        for ev in result.events:
            assert ev.model_name == "model_a"

    def test_pagination_via_fallback(self, ledger):
        _seed(ledger)

        page1 = changelog(ChangelogInput(limit=2, offset=0), ledger)
        page2 = changelog(ChangelogInput(limit=2, offset=2), ledger)

        assert page1.total == page2.total
        p1_ids = [(e.model_name, e.timestamp) for e in page1.events]
        p2_ids = [(e.model_name, e.timestamp) for e in page2.events]
        assert p1_ids != p2_ids


class TestTimeRangeFiltering:
    """Time range filtering with since/until."""

    def test_since_filters_old_events(self, ledger):
        _seed(ledger)

        future = datetime.now(timezone.utc) + timedelta(hours=1)
        result = changelog(ChangelogInput(since=future), ledger)

        assert result.total == 0

    def test_until_filters_future_events(self, ledger):
        _seed(ledger)

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        result = changelog(ChangelogInput(until=past), ledger)

        assert result.total == 0

    def test_both_since_and_until_period_string(self, ledger):
        _seed(ledger)

        since = datetime(2026, 1, 1, tzinfo=timezone.utc)
        until = datetime(2026, 12, 31, tzinfo=timezone.utc)
        result = changelog(ChangelogInput(since=since, until=until), ledger)

        assert result.period is not None
        assert "2026-01-01" in result.period
        assert "2026-12-31" in result.period
