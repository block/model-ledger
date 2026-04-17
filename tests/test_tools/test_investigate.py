# tests/test_tools/test_investigate.py
"""Tests for the investigate tool — deep-dive into a single model."""

from __future__ import annotations

import pytest

from model_ledger.backends.ledger_memory import InMemoryLedgerBackend
from model_ledger.core.exceptions import ModelNotFoundError
from model_ledger.graph.models import DataNode
from model_ledger.sdk.ledger import Ledger
from model_ledger.tools.investigate import investigate
from model_ledger.tools.record import record
from model_ledger.tools.schemas import (
    EventSummary,
    InvestigateInput,
    InvestigateOutput,
    RecordInput,
)


@pytest.fixture
def ledger():
    return Ledger(backend=InMemoryLedgerBackend())


class TestBasicInvestigation:
    """Basic investigation returns name, owner, type, status."""

    def test_basic_fields_present(self, ledger):
        record(
            RecordInput(
                model_name="fraud_scoring",
                event="registered",
                owner="risk-team",
                model_type="ml_model",
                purpose="Fraud detection",
            ),
            ledger,
        )

        result = investigate(InvestigateInput(model_name="fraud_scoring"), ledger)

        assert isinstance(result, InvestigateOutput)
        assert result.name == "fraud_scoring"
        assert result.owner == "risk-team"
        assert result.model_type == "ml_model"
        assert result.status == "active"
        assert result.purpose == "Fraud detection"

    def test_created_at_present(self, ledger):
        record(
            RecordInput(
                model_name="fraud_scoring",
                event="registered",
                owner="risk-team",
                model_type="ml_model",
                purpose="Fraud detection",
            ),
            ledger,
        )

        result = investigate(InvestigateInput(model_name="fraud_scoring"), ledger)

        assert result.created_at is not None

    def test_total_events_counted(self, ledger):
        record(
            RecordInput(
                model_name="fraud_scoring",
                event="registered",
                owner="risk-team",
                model_type="ml_model",
                purpose="Fraud detection",
            ),
            ledger,
        )
        record(
            RecordInput(
                model_name="fraud_scoring",
                event="metadata_updated",
                payload={"accuracy": 0.92},
                actor="ds",
            ),
            ledger,
        )

        result = investigate(InvestigateInput(model_name="fraud_scoring"), ledger)

        assert result.total_events >= 3

    def test_days_since_last_event(self, ledger):
        record(
            RecordInput(
                model_name="fraud_scoring",
                event="registered",
                owner="risk-team",
                model_type="ml_model",
                purpose="Fraud detection",
            ),
            ledger,
        )

        result = investigate(InvestigateInput(model_name="fraud_scoring"), ledger)

        assert result.days_since_last_event is not None
        assert result.days_since_last_event == 0


class TestMetadataMerge:
    """Metadata from snapshot payloads is merged oldest-first."""

    def test_metadata_merged_from_payloads(self, ledger):
        record(
            RecordInput(
                model_name="fraud_scoring",
                event="registered",
                owner="risk-team",
                model_type="ml_model",
                purpose="Fraud detection",
            ),
            ledger,
        )
        record(
            RecordInput(
                model_name="fraud_scoring",
                event="metadata_updated",
                payload={"accuracy": 0.92},
                actor="ds",
            ),
            ledger,
        )
        record(
            RecordInput(
                model_name="fraud_scoring",
                event="metadata_updated",
                payload={"environment": "production"},
                actor="ops",
            ),
            ledger,
        )

        result = investigate(InvestigateInput(model_name="fraud_scoring"), ledger)

        assert result.metadata["accuracy"] == 0.92
        assert result.metadata["environment"] == "production"

    def test_newer_metadata_overwrites_older(self, ledger):
        record(
            RecordInput(
                model_name="fraud_scoring",
                event="registered",
                owner="risk-team",
                model_type="ml_model",
                purpose="Fraud detection",
            ),
            ledger,
        )
        record(
            RecordInput(
                model_name="fraud_scoring",
                event="metadata_updated",
                payload={"accuracy": 0.85},
                actor="ds",
            ),
            ledger,
        )
        record(
            RecordInput(
                model_name="fraud_scoring",
                event="metadata_updated",
                payload={"accuracy": 0.92},
                actor="ds",
            ),
            ledger,
        )

        result = investigate(InvestigateInput(model_name="fraud_scoring"), ledger)

        assert result.metadata["accuracy"] == 0.92


class TestRecentEvents:
    """Recent events list with event_type."""

    def test_recent_events_included(self, ledger):
        record(
            RecordInput(
                model_name="fraud_scoring",
                event="registered",
                owner="risk-team",
                model_type="ml_model",
                purpose="Fraud detection",
            ),
            ledger,
        )
        record(
            RecordInput(
                model_name="fraud_scoring",
                event="metadata_updated",
                payload={"accuracy": 0.92},
                actor="ds",
            ),
            ledger,
        )

        result = investigate(InvestigateInput(model_name="fraud_scoring"), ledger)

        assert len(result.recent_events) > 0
        for ev in result.recent_events:
            assert isinstance(ev, EventSummary)
            assert ev.event_type  # non-empty

        event_types = [e.event_type for e in result.recent_events]
        assert "registered" in event_types
        assert "metadata_updated" in event_types

    def test_summary_limits_to_10_events(self, ledger):
        record(
            RecordInput(
                model_name="fraud_scoring",
                event="registered",
                owner="risk-team",
                model_type="ml_model",
                purpose="Fraud detection",
            ),
            ledger,
        )
        for i in range(15):
            record(
                RecordInput(
                    model_name="fraud_scoring",
                    event="retrained",
                    payload={"iteration": i},
                    actor="pipeline",
                ),
                ledger,
            )

        result = investigate(
            InvestigateInput(model_name="fraud_scoring", detail="summary"),
            ledger,
        )

        assert len(result.recent_events) == 10

    def test_full_detail_returns_all_events(self, ledger):
        record(
            RecordInput(
                model_name="fraud_scoring",
                event="registered",
                owner="risk-team",
                model_type="ml_model",
                purpose="Fraud detection",
            ),
            ledger,
        )
        for i in range(15):
            record(
                RecordInput(
                    model_name="fraud_scoring",
                    event="retrained",
                    payload={"iteration": i},
                    actor="pipeline",
                ),
                ledger,
            )

        result = investigate(
            InvestigateInput(model_name="fraud_scoring", detail="full"),
            ledger,
        )

        assert len(result.recent_events) > 10


class TestNonexistentModel:
    """Nonexistent model raises ModelNotFoundError."""

    def test_raises_model_not_found(self, ledger):
        with pytest.raises(ModelNotFoundError):
            investigate(InvestigateInput(model_name="does_not_exist"), ledger)


class TestInvestigateBatchDispatch:
    """Investigate produces correct output via fallback batch dispatch."""

    def test_dependencies_via_fallback(self, ledger):
        ledger.add(
            [
                DataNode("data_source", platform="database", outputs=["raw"]),
                DataNode("scoring_model", platform="ml", inputs=["raw"], outputs=["scores"]),
                DataNode("alert_queue", platform="alerting", inputs=["scores"]),
            ]
        )
        ledger.connect()

        assert not hasattr(ledger._backend, "batch_dependencies")

        result = investigate(InvestigateInput(model_name="scoring_model"), ledger)

        upstream_names = [d.name for d in result.upstream]
        downstream_names = [d.name for d in result.downstream]
        assert "data_source" in upstream_names
        assert "alert_queue" in downstream_names

    def test_no_dependencies_via_fallback(self, ledger):
        record(
            RecordInput(
                model_name="standalone",
                event="registered",
                owner="team",
                model_type="ml_model",
                purpose="test",
            ),
            ledger,
        )

        result = investigate(InvestigateInput(model_name="standalone"), ledger)

        assert result.upstream == []
        assert result.downstream == []


class TestDependencies:
    """Upstream and downstream dependencies from the graph."""

    def test_shows_upstream_downstream(self, ledger):
        ledger.add(
            [
                DataNode("feature_pipeline", platform="etl", outputs=["scores"]),
                DataNode(
                    "fraud_scoring",
                    platform="ml",
                    inputs=["scores"],
                    outputs=["alerts"],
                ),
                DataNode("alert_queue", platform="alerting", inputs=["alerts"]),
            ]
        )
        ledger.connect()

        result = investigate(InvestigateInput(model_name="fraud_scoring"), ledger)

        upstream_names = [d.name for d in result.upstream]
        downstream_names = [d.name for d in result.downstream]

        assert "feature_pipeline" in upstream_names
        assert "alert_queue" in downstream_names

    def test_no_graph_returns_empty_lists(self, ledger):
        """Model with no graph connections returns empty dependency lists."""
        record(
            RecordInput(
                model_name="standalone_model",
                event="registered",
                owner="risk-team",
                model_type="ml_model",
                purpose="Standalone model",
            ),
            ledger,
        )

        result = investigate(InvestigateInput(model_name="standalone_model"), ledger)

        assert result.upstream == []
        assert result.downstream == []
