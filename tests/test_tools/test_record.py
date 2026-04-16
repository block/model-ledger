# tests/test_tools/test_record.py
"""Tests for the record tool — register models and record events."""

from __future__ import annotations

import pytest

from model_ledger.backends.ledger_memory import InMemoryLedgerBackend
from model_ledger.core.exceptions import ModelNotFoundError
from model_ledger.sdk.ledger import Ledger
from model_ledger.tools.record import record
from model_ledger.tools.schemas import RecordInput, RecordOutput


@pytest.fixture
def ledger():
    return Ledger(backend=InMemoryLedgerBackend())


class TestRecordRegisterNewModel:
    """event='registered' should create a new model and log the registration."""

    def test_register_returns_new_model(self, ledger):
        inp = RecordInput(
            model_name="credit-scorecard",
            event="registered",
            actor="alice",
            owner="risk-team",
            model_type="ml_model",
            purpose="Credit risk scoring",
        )
        result = record(inp, ledger)

        assert isinstance(result, RecordOutput)
        assert result.is_new_model is True
        assert result.model_name == "credit-scorecard"
        assert result.event_id  # non-empty string
        assert result.timestamp is not None

    def test_registered_model_is_retrievable(self, ledger):
        inp = RecordInput(
            model_name="fraud-detector",
            event="registered",
            actor="bob",
            owner="security-team",
            model_type="ml_model",
            purpose="Detect fraudulent transactions",
        )
        record(inp, ledger)

        model = ledger.get("fraud-detector")
        assert model.name == "fraud-detector"
        assert model.owner == "security-team"
        assert model.model_type == "ml_model"
        assert model.purpose == "Detect fraudulent transactions"


class TestRecordEventOnExistingModel:
    """Non-registration events on existing models."""

    def test_record_event_existing_model(self, ledger):
        # First register the model
        register_inp = RecordInput(
            model_name="credit-scorecard",
            event="registered",
            actor="alice",
            owner="risk-team",
            model_type="ml_model",
            purpose="Credit risk scoring",
        )
        record(register_inp, ledger)

        # Now record a new event on it
        event_inp = RecordInput(
            model_name="credit-scorecard",
            event="validated",
            payload={"result": "passed", "validator": "mr-framework"},
            actor="validator-bot",
        )
        result = record(event_inp, ledger)

        assert isinstance(result, RecordOutput)
        assert result.is_new_model is False
        assert result.model_name == "credit-scorecard"
        assert result.event_id  # non-empty
        assert result.timestamp is not None

    def test_record_with_arbitrary_payload(self, ledger):
        # Register the model
        record(
            RecordInput(
                model_name="scoring-model",
                event="registered",
                actor="alice",
                owner="data-team",
                model_type="ml_model",
                purpose="Score applicants",
            ),
            ledger,
        )

        # Record event with rich payload (docs, metrics, links)
        payload = {
            "metrics": {"auc": 0.92, "precision": 0.87, "recall": 0.91},
            "docs": {"validation_report": "https://docs.example.com/report-42"},
            "links": ["https://mlflow.example.com/runs/abc123"],
            "tags": ["quarterly-review", "q1-2026"],
        }
        result = record(
            RecordInput(
                model_name="scoring-model",
                event="performance-review",
                payload=payload,
                actor="monitoring-agent",
            ),
            ledger,
        )

        assert result.is_new_model is False
        assert result.event_id

        # Verify the payload was persisted via ledger history
        history = ledger.history("scoring-model")
        perf_events = [s for s in history if s.event_type == "performance-review"]
        assert len(perf_events) == 1
        assert perf_events[0].payload["metrics"]["auc"] == 0.92


class TestRecordNonexistentModel:
    """Non-registration events on models that don't exist should raise."""

    def test_raises_model_not_found(self, ledger):
        inp = RecordInput(
            model_name="does-not-exist",
            event="deployed",
            payload={"version": "1.0"},
            actor="deployer",
        )
        with pytest.raises(ModelNotFoundError):
            record(inp, ledger)
