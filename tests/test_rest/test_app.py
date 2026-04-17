# tests/test_rest/test_app.py
"""Tests for the FastAPI REST API wrapping tool functions."""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from model_ledger.rest.app import create_app


@pytest.fixture
def client():
    """TestClient backed by an in-memory ledger."""
    app = create_app()
    return TestClient(app)


class TestOverview:
    """GET /overview on an empty ledger."""

    def test_overview_empty(self, client):
        resp = client.get("/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_models"] == 0
        assert data["total_events"] == 0


class TestOverviewWithData:
    """GET /overview with a populated inventory uses count_all_snapshots dispatch."""

    def test_overview_counts_events(self, client):
        client.post(
            "/record",
            json={
                "model_name": "scoring-model",
                "event": "registered",
                "actor": "alice",
                "owner": "data-team",
                "model_type": "ml_model",
            },
        )
        client.post(
            "/record",
            json={
                "model_name": "scoring-model",
                "event": "retrained",
                "actor": "pipeline",
            },
        )

        resp = client.get("/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_models"] == 1
        assert data["total_events"] >= 2


class TestRecordEndpoint:
    """POST /record — register a model."""

    def test_register_model(self, client):
        resp = client.post(
            "/record",
            json={
                "model_name": "credit-scorecard",
                "event": "registered",
                "actor": "alice",
                "owner": "risk-team",
                "model_type": "ml_model",
                "purpose": "Credit risk scoring",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_name"] == "credit-scorecard"
        assert data["is_new_model"] is True
        assert data["event_id"]  # non-empty


class TestQueryAfterRegister:
    """GET /query — search after registering a model."""

    def test_query_finds_registered_model(self, client):
        client.post(
            "/record",
            json={
                "model_name": "fraud-detector",
                "event": "registered",
                "actor": "bob",
                "owner": "security-team",
                "model_type": "ml_model",
                "purpose": "Detect fraudulent transactions",
            },
        )

        resp = client.get("/query", params={"text": "fraud"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        names = [m["name"] for m in data["models"]]
        assert "fraud-detector" in names

    def test_query_empty_inventory(self, client):
        resp = client.get("/query")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["models"] == []


class TestInvestigateEndpoint:
    """GET /investigate/{model_name} — deep-dive into a model."""

    def test_investigate_registered_model(self, client):
        client.post(
            "/record",
            json={
                "model_name": "credit-scorecard",
                "event": "registered",
                "actor": "alice",
                "owner": "risk-team",
                "model_type": "ml_model",
                "purpose": "Credit risk scoring",
            },
        )

        resp = client.get("/investigate/credit-scorecard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "credit-scorecard"
        assert data["owner"] == "risk-team"
        assert data["total_events"] >= 1

    def test_investigate_404(self, client):
        resp = client.get("/investigate/nonexistent-model")
        assert resp.status_code == 404
        assert "nonexistent-model" in resp.json()["detail"]


class TestTraceEndpoint:
    """GET /trace/{name} — dependency tracing."""

    def test_trace_registered_model(self, client):
        client.post(
            "/record",
            json={
                "model_name": "scoring-model",
                "event": "registered",
                "actor": "alice",
                "owner": "data-team",
                "model_type": "ml_model",
            },
        )

        resp = client.get("/trace/scoring-model")
        assert resp.status_code == 200
        data = resp.json()
        assert data["root"] == "scoring-model"

    def test_trace_404(self, client):
        resp = client.get("/trace/nonexistent")
        assert resp.status_code == 404


class TestChangelogEndpoint:
    """GET /changelog — event timeline."""

    def test_changelog_with_events(self, client):
        client.post(
            "/record",
            json={
                "model_name": "scoring-model",
                "event": "registered",
                "actor": "alice",
                "owner": "data-team",
                "model_type": "ml_model",
            },
        )

        resp = client.get("/changelog")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["events"]) >= 1


class TestDiscoverEndpoint:
    """POST /discover — bulk ingestion."""

    def test_discover_inline(self, client):
        resp = client.post(
            "/discover",
            json={
                "source_type": "inline",
                "models": [
                    {"name": "pipeline-a", "platform": "airflow"},
                    {"name": "pipeline-b", "platform": "airflow"},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["models_added"] == 2
