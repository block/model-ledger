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

from datetime import timedelta

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


def _make_stack():
    """A server with an inspectable backend plus an HTTP-backed Ledger."""
    from model_ledger.backends.ledger_memory import InMemoryLedgerBackend

    server_backend = InMemoryLedgerBackend()
    server_app = create_app(backend=server_backend)
    b = HttpLedgerBackend("http://testserver")
    b._client.close()
    b._client = TestClient(server_app)
    return server_backend, server_app, b, Ledger(backend=b)


def _fresh_client(server_app):
    """A second client process: no local caches, same server."""
    b = HttpLedgerBackend("http://testserver")
    b._client.close()
    b._client = TestClient(server_app)
    return b, Ledger(backend=b)


def _age_server_events(server_backend, days=30):
    """Rewind server-side event timestamps, keeping content hashes consistent
    (in production an old snapshot's hash reflects its real timestamp)."""
    from model_ledger.core.ledger_models import _compute_snapshot_hash

    for s in server_backend._snapshots:
        object.__setattr__(s, "timestamp", s.timestamp - timedelta(days=days))
        object.__setattr__(
            s, "snapshot_hash", _compute_snapshot_hash(s.model_hash, s.timestamp, s.payload)
        )


class TestOldEventsVisibleOverHttp:
    """The changelog tool defaults to a 7-day window when no bounds are
    given. ``list_snapshots`` must fetch the full history, or every SDK
    behavior built on it silently breaks for models older than a week."""

    def test_list_snapshots_sees_month_old_events(self):
        server_backend, server_app, _, ledger = _make_stack()
        ledger.register(
            name="old-model", owner="risk", model_type="ml_model", tier="low", purpose="p"
        )
        _age_server_events(server_backend)

        fresh, _ = _fresh_client(server_app)
        ref = fresh.get_model_by_name("old-model")
        assert len(fresh.list_snapshots(ref.model_hash)) >= 1

    def test_latest_snapshot_and_tag_for_old_model(self):
        server_backend, server_app, _, ledger = _make_stack()
        ledger.register(
            name="old-model", owner="risk", model_type="ml_model", tier="low", purpose="p"
        )
        _age_server_events(server_backend)

        fresh, fresh_ledger = _fresh_client(server_app)
        ref = fresh.get_model_by_name("old-model")
        assert fresh.latest_snapshot(ref.model_hash) is not None
        # Ledger.tag resolves latest_snapshot — must not raise for a
        # perfectly healthy month-old model.
        fresh_ledger.tag("old-model", "v1")

    def test_get_snapshot_reconstructs_month_old_snapshot(self):
        server_backend, server_app, _, ledger = _make_stack()
        ledger.register(
            name="old-model", owner="risk", model_type="ml_model", tier="low", purpose="p"
        )
        _age_server_events(server_backend)
        old_server_hash = server_backend._snapshots[0].snapshot_hash

        fresh, _ = _fresh_client(server_app)
        fresh.get_model_by_name("old-model")  # populate name cache
        got = fresh.get_snapshot(old_server_hash)
        assert got is not None
        assert got.snapshot_hash == old_server_hash

    def test_reregistration_of_old_model_is_idempotent_with_real_event_id(self):
        from model_ledger.tools.record import record
        from model_ledger.tools.schemas import RecordInput

        server_backend, server_app, _, ledger = _make_stack()
        ledger.register(
            name="old-model", owner="risk", model_type="ml_model", tier="low", purpose="p"
        )
        _age_server_events(server_backend)

        _, fresh_ledger = _fresh_client(server_app)
        out = record(
            RecordInput(
                model_name="old-model",
                event="registered",
                payload={},
                actor="ci",
                owner="risk",
                model_type="ml_model",
                purpose="p",
            ),
            fresh_ledger,
        )
        registered = [s for s in server_backend._snapshots if s.event_type == "registered"]
        assert len(registered) == 1  # idempotent even when the event is old
        assert out.is_new_model is False
        # The returned event_id identifies a real server-side event.
        assert out.event_id in {s.snapshot_hash for s in server_backend._snapshots}

    def test_platform_filter_finds_month_old_model(self):
        from model_ledger.tools.query import query
        from model_ledger.tools.schemas import QueryInput

        server_backend, server_app, _, ledger = _make_stack()
        ledger.register(
            name="old-mlflow", owner="o", model_type="ml_model", tier="low", purpose="p"
        )
        ledger.record(
            "old-mlflow",
            event="discovered",
            payload={"platform": "mlflow"},
            actor="c",
            source="mlflow",
        )
        _age_server_events(server_backend)

        _, fresh_ledger = _fresh_client(server_app)
        res = query(QueryInput(platform="mlflow"), fresh_ledger)
        assert res.total == 1
        assert res.models[0].name == "old-mlflow"

    def test_platform_filter_finds_fresh_model_from_fresh_client(self):
        """Hash-resolution regression: hashes handed out by list_models must
        be resolvable by the same backend (list_snapshots via get_model),
        or batch_platforms sees zero snapshots for every model."""
        from model_ledger.tools.query import query
        from model_ledger.tools.schemas import QueryInput

        _, server_app, _, ledger = _make_stack()
        ledger.register(
            name="fresh-mlflow", owner="o", model_type="ml_model", tier="low", purpose="p"
        )
        ledger.record(
            "fresh-mlflow",
            event="discovered",
            payload={"platform": "mlflow"},
            actor="c",
            source="mlflow",
        )
        _, fresh_ledger = _fresh_client(server_app)
        res = query(QueryInput(platform="mlflow"), fresh_ledger)
        assert res.total == 1


class TestRegistrationFidelityOverHttp:
    """Registration over HTTP must carry the same information as a local
    backend: the caller's payload lands on the single registered event,
    and the tier lands on the model row."""

    def test_registration_payload_lands_on_registered_event(self):
        from model_ledger.tools.record import record
        from model_ledger.tools.schemas import RecordInput

        server_backend, _, _, ledger = _make_stack()
        record(
            RecordInput(
                model_name="m1",
                event="registered",
                payload={"framework": "xgboost", "version": "2.1"},
                actor="ci",
                owner="risk",
                model_type="ml_model",
                purpose="scoring",
            ),
            ledger,
        )
        registered = [s for s in server_backend._snapshots if s.event_type == "registered"]
        assert len(registered) == 1
        assert registered[0].payload.get("framework") == "xgboost"
        assert registered[0].payload.get("version") == "2.1"

    def test_register_payload_kwarg_lands_on_registered_event(self):
        server_backend, _, _, ledger = _make_stack()
        ledger.register(
            name="m2",
            owner="risk",
            model_type="ml_model",
            tier="low",
            purpose="p",
            payload={"framework": "lightgbm"},
        )
        registered = [s for s in server_backend._snapshots if s.event_type == "registered"]
        assert len(registered) == 1
        assert registered[0].payload.get("framework") == "lightgbm"

    def test_tier_survives_http_registration(self):
        server_backend, _, _, ledger = _make_stack()
        ledger.register(
            name="tiered", owner="risk", model_type="ml_model", tier="high", purpose="p"
        )
        assert server_backend.get_model_by_name("tiered").tier == "high"

    def test_actor_survives_http_registration(self):
        server_backend, _, _, ledger = _make_stack()
        ledger.register(
            name="acted",
            owner="risk",
            model_type="ml_model",
            tier="low",
            purpose="p",
            actor="pipeline-bot",
        )
        registered = [s for s in server_backend._snapshots if s.event_type == "registered"]
        assert registered[0].actor == "pipeline-bot"


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

    def test_record_whitespace_only_model_name_is_rejected(self, server_client):
        resp = server_client.post(
            "/record",
            json={"model_name": "   ", "event": "registered", "actor": "old-client"},
        )
        assert resp.status_code == 422
        assert server_client.get("/query").json()["total"] == 0
