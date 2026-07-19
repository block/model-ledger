# tests/test_backends/test_http_ledger_integration.py
"""End-to-end: ``Ledger(HttpLedgerBackend(url))`` against real REST handlers.

Regression tests for the remote-SDK path advertised in
docs/guides/backends.md. The mocked unit tests cannot catch payload-shape
mismatches between the SDK backend and the server's ``/record`` tool —
previously ``append_snapshot`` posted ``model_name: ""``, so the server
auto-registered a phantom model named ``""`` and attached every event to
it, while ``register()`` double-logged the registration event.

These tests drive the real ``create_app()`` handlers in-process via
Starlette's TestClient (a sync httpx.Client subclass), NOT mocks.
"""

from __future__ import annotations

import pytest

pytest.importorskip("httpx")
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from model_ledger.backends.http import HttpLedgerBackend
from model_ledger.core.exceptions import ModelNotFoundError
from model_ledger.core.ledger_models import Snapshot
from model_ledger.rest.app import create_app
from model_ledger.sdk.ledger import Ledger


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def backend(app):
    """A fully-constructed HttpLedgerBackend whose transport is the real app."""
    b = HttpLedgerBackend("http://testserver")
    b._client.close()
    b._client = TestClient(app)
    yield b
    b._client.close()


@pytest.fixture
def server_client(app):
    """Independent client for asserting server-side state."""
    return TestClient(app)


@pytest.fixture
def ledger(backend):
    return Ledger(backend=backend)


def _register(ledger):
    return ledger.register(
        name="remote-model",
        owner="risk-team",
        model_type="ml_model",
        tier="low",
        purpose="scoring",
    )


class TestRegisterOverHttp:
    def test_register_creates_no_phantom_model(self, ledger, server_client):
        _register(ledger)

        names = [m["name"] for m in server_client.get("/query").json()["models"]]
        assert "" not in names
        assert names == ["remote-model"]

    def test_register_logs_exactly_one_registered_event(self, ledger, server_client):
        _register(ledger)

        resp = server_client.get("/changelog", params={"model_name": "remote-model"})
        events = resp.json()["events"]
        registered = [e for e in events if e["event_type"] == "registered"]
        assert len(registered) == 1


class TestRecordOverHttp:
    def test_event_attaches_to_named_model(self, ledger, server_client):
        _register(ledger)
        ledger.record("remote-model", event="deployed", payload={"env": "prod"}, actor="ci")

        events = server_client.get("/changelog").json()["events"]
        deployed = [e for e in events if e["event_type"] == "deployed"]
        assert len(deployed) == 1
        assert deployed[0]["model_name"] == "remote-model"
        assert deployed[0]["payload"] == {"env": "prod"}

        # No phantom model appeared as a side effect of recording.
        names = [m["name"] for m in server_client.get("/query").json()["models"]]
        assert names == ["remote-model"]

    def test_ledger_list_round_trip(self, ledger):
        _register(ledger)
        ledger.record("remote-model", event="deployed", payload={}, actor="ci")

        assert [m.name for m in ledger.list()] == ["remote-model"]

    def test_append_snapshot_unknown_hash_fails_loudly(self, backend):
        """An unresolvable model_hash must raise, not corrupt the remote ledger."""
        snap = Snapshot(
            model_hash="0" * 32,
            actor="ci",
            event_type="deployed",
            payload={},
        )
        with pytest.raises(ModelNotFoundError):
            backend.append_snapshot(snap)


class TestGetSnapshotOverHttp:
    def test_get_snapshot_round_trips(self, ledger, backend):
        model = _register(ledger)
        ledger.record("remote-model", event="deployed", payload={"env": "prod"}, actor="ci")

        snaps = backend.list_snapshots(model.model_hash)
        assert snaps  # registration + deployed visible via changelog
        for snap in snaps:
            got = backend.get_snapshot(snap.snapshot_hash)
            assert got is not None
            assert got.snapshot_hash == snap.snapshot_hash
            assert got.event_type == snap.event_type
            assert got.model_hash == model.model_hash

    def test_get_snapshot_unknown_hash_returns_none(self, backend):
        assert backend.get_snapshot("f" * 32) is None


class TestServerRejectsEmptyModelName:
    """Defense in depth: old clients that still post ``model_name: ""``
    must fail loudly instead of silently corrupting the ledger."""

    def test_record_empty_model_name_is_rejected(self, server_client):
        resp = server_client.post(
            "/record",
            json={"model_name": "", "event": "deployed", "actor": "old-client"},
        )
        assert resp.status_code == 422

        # Nothing was registered.
        assert server_client.get("/query").json()["total"] == 0

    def test_record_empty_model_name_registered_is_rejected(self, server_client):
        resp = server_client.post(
            "/record",
            json={"model_name": "", "event": "registered", "actor": "old-client"},
        )
        assert resp.status_code == 422
        assert server_client.get("/query").json()["total"] == 0
