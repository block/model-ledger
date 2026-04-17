# tests/test_backends/test_http_backend.py
"""Tests for HttpLedgerBackend tag methods via a real in-process REST API."""

from __future__ import annotations

import pytest

pytest.importorskip("httpx")
pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from model_ledger.backends.http import HttpLedgerBackend
from model_ledger.core.exceptions import ModelNotFoundError
from model_ledger.core.ledger_models import Tag
from model_ledger.rest.app import create_app
from model_ledger.sdk.ledger import Ledger


@pytest.fixture
def http_backend():
    """HttpLedgerBackend that talks to an in-process FastAPI app.

    Uses Starlette's TestClient (a sync httpx.Client subclass) as the
    underlying client so we can exercise the real REST handlers in-process.
    """
    app = create_app()
    backend = HttpLedgerBackend.__new__(HttpLedgerBackend)
    backend._base_url = "http://testserver"
    backend._client = TestClient(app)
    backend._hash_to_name = {}
    yield backend
    backend._client.close()


@pytest.fixture
def registered_model(http_backend):
    """Register a model through the same HTTP API so tests have a target."""
    http_backend._client.post(
        "/record",
        json={
            "model_name": "credit-scorecard",
            "event": "registered",
            "actor": "alice",
            "owner": "risk-team",
            "model_type": "ml_model",
        },
    )
    return http_backend.get_model_by_name("credit-scorecard")


class TestSetTag:
    """set_tag calls POST /tag."""

    def test_set_tag_writes_through_api(self, http_backend, registered_model):
        # latest_snapshot via HTTP — uses changelog under the hood
        latest = http_backend.latest_snapshot(registered_model.model_hash)
        assert latest is not None

        tag = Tag(
            name="v1.0",
            model_hash=registered_model.model_hash,
            snapshot_hash=latest.snapshot_hash,
        )
        http_backend.set_tag(tag)

        # Verify through list_tags
        tags = http_backend.list_tags(registered_model.model_hash)
        assert len(tags) == 1
        assert tags[0].name == "v1.0"

    def test_set_tag_raises_when_model_hash_unknown(self, http_backend):
        tag = Tag(
            name="v1.0",
            model_hash="0" * 64,
            snapshot_hash="ffff",
        )
        with pytest.raises(ModelNotFoundError):
            http_backend.set_tag(tag)


class TestGetTag:
    """get_tag returns a specific tag or None."""

    def test_get_tag_returns_existing(self, http_backend, registered_model):
        latest = http_backend.latest_snapshot(registered_model.model_hash)
        http_backend.set_tag(
            Tag(
                name="prod",
                model_hash=registered_model.model_hash,
                snapshot_hash=latest.snapshot_hash,
            )
        )
        found = http_backend.get_tag(registered_model.model_hash, "prod")
        assert found is not None
        assert found.name == "prod"
        assert found.model_hash == registered_model.model_hash

    def test_get_tag_returns_none_when_missing(self, http_backend, registered_model):
        assert http_backend.get_tag(registered_model.model_hash, "nonexistent") is None

    def test_get_tag_returns_none_when_model_unknown(self, http_backend):
        assert http_backend.get_tag("0" * 64, "v1.0") is None


class TestListTags:
    """list_tags returns all tags for a model."""

    def test_list_tags_empty(self, http_backend, registered_model):
        assert http_backend.list_tags(registered_model.model_hash) == []

    def test_list_tags_all_fields_populated(self, http_backend, registered_model):
        latest = http_backend.latest_snapshot(registered_model.model_hash)
        http_backend.set_tag(
            Tag(
                name="v1.0",
                model_hash=registered_model.model_hash,
                snapshot_hash=latest.snapshot_hash,
            )
        )
        tags = http_backend.list_tags(registered_model.model_hash)
        assert len(tags) == 1
        t = tags[0]
        assert t.name == "v1.0"
        assert t.model_hash == registered_model.model_hash
        assert t.snapshot_hash == latest.snapshot_hash
        assert t.updated_at is not None

    def test_list_tags_returns_empty_when_model_unknown(self, http_backend):
        assert http_backend.list_tags("0" * 64) == []

    def test_list_tags_returns_multiple(self, http_backend, registered_model):
        latest = http_backend.latest_snapshot(registered_model.model_hash)
        for name in ("v1.0", "prod", "release"):
            http_backend.set_tag(
                Tag(
                    name=name,
                    model_hash=registered_model.model_hash,
                    snapshot_hash=latest.snapshot_hash,
                )
            )
        names = {t.name for t in http_backend.list_tags(registered_model.model_hash)}
        assert names == {"v1.0", "prod", "release"}


class TestLedgerTagOverHttp:
    """End-to-end: Ledger.tag() backed by HttpLedgerBackend is no longer a silent no-op."""

    def test_ledger_tag_writes_via_http(self, http_backend, registered_model):
        ledger = Ledger(backend=http_backend)
        created = ledger.tag("credit-scorecard", "v1.0")

        assert created.name == "v1.0"
        # Must be retrievable via list_tags (previously was a silent no-op)
        tags = http_backend.list_tags(registered_model.model_hash)
        assert {t.name for t in tags} == {"v1.0"}


class TestSaveModelCanonicalHash:
    """save_model adopts the server's canonical model_hash.

    Client-side ModelRef hashes depend on a locally generated ``created_at``
    that differs from the server's — caching the client hash would make
    later tag writes round-trip to a nonexistent identity.
    """

    def test_save_model_mutates_ref_to_server_hash(self, http_backend):
        from datetime import datetime, timezone

        from model_ledger.core.ledger_models import ModelRef

        # Construct a ref with an *old* created_at so the client hash is
        # guaranteed to differ from whatever the server computes.
        ref = ModelRef(
            name="credit-scorecard",
            owner="risk-team",
            model_type="ml_model",
            tier="unclassified",
            purpose="Credit risk scoring",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        client_hash = ref.model_hash

        http_backend.save_model(ref)

        # Server stored its own hash (with its own created_at).
        server_side = http_backend.get_model_by_name("credit-scorecard")
        assert server_side is not None
        assert server_side.model_hash != client_hash

        # The incoming ref was reconciled to the server's canonical hash.
        assert ref.model_hash == server_side.model_hash

    def test_cache_stores_server_hash_not_client_hash(self, http_backend):
        from datetime import datetime, timezone

        from model_ledger.core.ledger_models import ModelRef

        ref = ModelRef(
            name="fraud-detector",
            owner="security-team",
            model_type="ml_model",
            tier="unclassified",
            purpose="Fraud detection",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        client_hash = ref.model_hash

        http_backend.save_model(ref)

        server_side = http_backend.get_model_by_name("fraud-detector")
        assert server_side.model_hash != client_hash

        # The hash-to-name cache contains the server hash only.
        assert http_backend._hash_to_name.get(server_side.model_hash) == "fraud-detector"
        # The stale client hash is NOT in the cache.
        assert client_hash not in http_backend._hash_to_name

    def test_tag_flow_survives_fresh_backend_instance(self, http_backend):
        """A fresh client (empty cache) tagging by name must round-trip."""
        from model_ledger.core.ledger_models import ModelRef

        ref = ModelRef(
            name="scoring-model",
            owner="data-team",
            model_type="ml_model",
            tier="unclassified",
            purpose="Score applicants",
        )
        http_backend.save_model(ref)

        # Simulate a new client sharing the same underlying transport.
        fresh_backend = HttpLedgerBackend.__new__(HttpLedgerBackend)
        fresh_backend._base_url = http_backend._base_url
        fresh_backend._client = http_backend._client
        fresh_backend._hash_to_name = {}

        ledger = Ledger(backend=fresh_backend)
        created = ledger.tag("scoring-model", "v1.0")
        assert created.name == "v1.0"

        model = fresh_backend.get_model_by_name("scoring-model")
        assert model is not None
        tags = fresh_backend.list_tags(model.model_hash)
        assert {t.name for t in tags} == {"v1.0"}


class TestSaveModelErrorPaths:
    """save_model fails loudly instead of silently caching bad state."""

    def test_http_error_raises_and_does_not_cache(self):
        """4xx/5xx responses must raise and leave the cache untouched."""
        import httpx

        from model_ledger.core.ledger_models import ModelRef

        def _always_500(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"detail": "boom"})

        backend = HttpLedgerBackend.__new__(HttpLedgerBackend)
        backend._base_url = "http://testserver"
        backend._client = httpx.Client(
            base_url="http://testserver",
            transport=httpx.MockTransport(_always_500),
        )
        backend._hash_to_name = {}

        ref = ModelRef(
            name="credit-scorecard",
            owner="risk-team",
            model_type="ml_model",
            tier="unclassified",
            purpose="Credit risk scoring",
        )
        with pytest.raises(httpx.HTTPStatusError):
            backend.save_model(ref)
        assert backend._hash_to_name == {}
        backend._client.close()

    def test_success_without_model_hash_raises(self):
        """A 2xx response missing model_hash is a protocol violation."""
        import httpx

        from model_ledger.core.ledger_models import ModelRef

        def _missing_hash(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "model_name": "credit-scorecard",
                    "event_id": "abc",
                    "timestamp": "2026-04-17T00:00:00+00:00",
                    "is_new_model": True,
                },
            )

        backend = HttpLedgerBackend.__new__(HttpLedgerBackend)
        backend._base_url = "http://testserver"
        backend._client = httpx.Client(
            base_url="http://testserver",
            transport=httpx.MockTransport(_missing_hash),
        )
        backend._hash_to_name = {}

        ref = ModelRef(
            name="credit-scorecard",
            owner="risk-team",
            model_type="ml_model",
            tier="unclassified",
            purpose="Credit risk scoring",
        )
        with pytest.raises(ValueError, match="model_hash"):
            backend.save_model(ref)
        assert backend._hash_to_name == {}
        backend._client.close()
