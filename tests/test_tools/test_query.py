# tests/test_tools/test_query.py
"""Tests for the query tool — search and filter model inventory."""

from __future__ import annotations

import pytest

from model_ledger.backends.ledger_memory import InMemoryLedgerBackend
from model_ledger.sdk.ledger import Ledger
from model_ledger.tools.query import _model_to_summary, query
from model_ledger.tools.record import record
from model_ledger.tools.schemas import (
    ModelSummary,
    QueryInput,
    QueryOutput,
    RecordInput,
)


@pytest.fixture
def ledger():
    return Ledger(backend=InMemoryLedgerBackend())


def _register(ledger, name, owner="risk-team", model_type="ml_model", purpose=""):
    """Helper to register a model with minimal boilerplate."""
    record(
        RecordInput(
            model_name=name,
            event="registered",
            owner=owner,
            model_type=model_type,
            purpose=purpose,
        ),
        ledger,
    )


@pytest.fixture
def populated_ledger(ledger):
    """Ledger with 4 diverse models for filtering tests."""
    _register(
        ledger,
        "fraud-detector",
        owner="risk-team",
        model_type="ml_model",
        purpose="Detect fraud",
    )
    _register(
        ledger,
        "credit-scorecard",
        owner="risk-team",
        model_type="ml_model",
        purpose="Credit scoring",
    )
    _register(
        ledger,
        "pricing-rules",
        owner="finance-team",
        model_type="heuristic",
        purpose="Pricing logic",
    )
    _register(
        ledger,
        "churn-predictor",
        owner="growth-team",
        model_type="ml_model",
        purpose="Predict churn",
    )
    return ledger


class TestQueryListAll:
    """No filters — list all models."""

    def test_returns_all_models(self, populated_ledger):
        result = query(QueryInput(), populated_ledger)

        assert isinstance(result, QueryOutput)
        assert result.total == 4
        assert len(result.models) == 4
        assert result.has_more is False

    def test_each_model_is_model_summary(self, populated_ledger):
        result = query(QueryInput(), populated_ledger)

        for m in result.models:
            assert isinstance(m, ModelSummary)
            assert m.name
            assert m.event_count > 0


class TestQueryPagination:
    """Pagination via limit and offset."""

    def test_limit_returns_subset(self, populated_ledger):
        result = query(QueryInput(limit=2), populated_ledger)

        assert result.total == 4
        assert len(result.models) == 2
        assert result.has_more is True

    def test_second_page(self, populated_ledger):
        result = query(QueryInput(limit=2, offset=2), populated_ledger)

        assert result.total == 4
        assert len(result.models) == 2
        assert result.has_more is False

    def test_offset_beyond_total(self, populated_ledger):
        result = query(QueryInput(limit=10, offset=100), populated_ledger)

        assert result.total == 4
        assert len(result.models) == 0
        assert result.has_more is False


class TestQueryFilterByOwner:
    """Filter by owner field."""

    def test_filter_owner(self, populated_ledger):
        result = query(QueryInput(owner="risk-team"), populated_ledger)

        assert result.total == 2
        assert all(m.owner == "risk-team" for m in result.models)

    def test_filter_owner_no_match(self, populated_ledger):
        result = query(QueryInput(owner="nonexistent-team"), populated_ledger)

        assert result.total == 0
        assert result.models == []


class TestQueryFilterByModelType:
    """Filter by model_type field."""

    def test_filter_model_type(self, populated_ledger):
        result = query(QueryInput(model_type="heuristic"), populated_ledger)

        assert result.total == 1
        assert result.models[0].name == "pricing-rules"
        assert result.models[0].model_type == "heuristic"

    def test_filter_model_type_ml(self, populated_ledger):
        result = query(QueryInput(model_type="ml_model"), populated_ledger)

        assert result.total == 3


class TestQueryTextSearch:
    """Fuzzy text search on name and purpose."""

    def test_text_matches_name(self, populated_ledger):
        result = query(QueryInput(text="fraud"), populated_ledger)

        assert result.total == 1
        assert result.models[0].name == "fraud-detector"

    def test_text_matches_purpose(self, populated_ledger):
        result = query(QueryInput(text="scoring"), populated_ledger)

        assert result.total == 1
        assert result.models[0].name == "credit-scorecard"

    def test_text_case_insensitive(self, populated_ledger):
        result = query(QueryInput(text="FRAUD"), populated_ledger)

        assert result.total == 1
        assert result.models[0].name == "fraud-detector"

    def test_text_no_match(self, populated_ledger):
        result = query(QueryInput(text="nonexistent"), populated_ledger)

        assert result.total == 0
        assert result.models == []


class TestQueryEmptyInventory:
    """Empty inventory returns empty results."""

    def test_empty_inventory(self, ledger):
        result = query(QueryInput(), ledger)

        assert result.total == 0
        assert result.models == []
        assert result.has_more is False


class TestModelToSummary:
    """_model_to_summary helper builds ModelSummary from ModelRef."""

    def test_summary_fields(self, ledger):
        _register(
            ledger,
            "fraud-detector",
            owner="risk-team",
            model_type="ml_model",
            purpose="Detect fraud",
        )
        model = ledger.get("fraud-detector")
        summary = _model_to_summary(model, ledger)

        assert isinstance(summary, ModelSummary)
        assert summary.name == "fraud-detector"
        assert summary.owner == "risk-team"
        assert summary.model_type == "ml_model"
        assert summary.status == "active"
        assert summary.event_count >= 1
        assert summary.last_event is not None

    def test_summary_event_count_increases(self, ledger):
        _register(
            ledger,
            "scoring-model",
            owner="data-team",
            model_type="ml_model",
            purpose="Score",
        )
        # Add more events
        record(
            RecordInput(model_name="scoring-model", event="retrained", actor="pipeline"),
            ledger,
        )
        record(
            RecordInput(model_name="scoring-model", event="deployed", actor="deployer"),
            ledger,
        )

        model = ledger.get("scoring-model")
        summary = _model_to_summary(model, ledger)

        # register creates 2 snapshots (register call + record call in record tool),
        # plus retrained + deployed
        assert summary.event_count >= 3

    def test_summary_platform_from_source(self, ledger):
        _register(
            ledger,
            "platform-model",
            owner="data-team",
            model_type="ml_model",
            purpose="Test",
        )
        model = ledger.get("platform-model")
        # Record an event with a source
        ledger.record(
            model,
            event="discovered",
            payload={"platform": "mlflow"},
            actor="connector",
            source="mlflow",
        )

        summary = _model_to_summary(model, ledger)
        assert summary.platform == "mlflow"
