"""Tests for SnowflakeLedgerBackend — v0.4.0 LedgerBackend protocol."""

import re
from datetime import datetime, timezone
from typing import Any

import pytest

from model_ledger.core.ledger_models import ModelRef, Snapshot, Tag


class MockCollectResult:
    def __init__(self, rows):
        self._rows = rows

    def collect(self):
        return self._rows


class MockLedgerSession:
    """In-memory mock that tracks SQL calls and stores data."""

    def __init__(self):
        self._models: dict[str, dict[str, Any]] = {}
        self._snapshots: list[dict[str, Any]] = []
        self._tags: dict[tuple[str, str], dict[str, Any]] = {}

    def sql(self, query: str, params: Any = None) -> MockCollectResult:
        upper = query.upper().strip()

        if upper.startswith("CREATE"):
            return MockCollectResult([])

        if "MERGE INTO" in upper and ".MODELS " in upper:
            # Handle batched MERGE with UNION ALL
            for m in re.finditer(
                r"SELECT\s+'([^']+)'\s+AS\s+model_hash,\s+'([^']+)'\s+AS\s+name,\s+'([^']+)'\s+AS\s+owner,\s+'([^']+)'\s+AS\s+model_type,\s+'([^']+)'\s+AS\s+model_origin,\s+'([^']+)'\s+AS\s+tier",
                query,
                re.DOTALL,
            ):
                self._models[m.group(1)] = {
                    "MODEL_HASH": m.group(1),
                    "NAME": m.group(2),
                    "OWNER": m.group(3),
                    "MODEL_TYPE": m.group(4),
                    "MODEL_ORIGIN": m.group(5),
                    "TIER": m.group(6),
                    "PURPOSE": "",
                    "STATUS": "active",
                    "CREATED_AT": datetime(2025, 1, 1, tzinfo=timezone.utc),
                }
            return MockCollectResult([])

        if ".MODELS" in upper and "MODEL_HASH =" in upper:
            m = re.search(r"MODEL_HASH\s*=\s*'([^']+)'", query)
            if m and m.group(1) in self._models:
                return MockCollectResult([self._models[m.group(1)]])
            return MockCollectResult([])

        if ".MODELS" in upper and "NAME =" in upper:
            m = re.search(r"NAME\s*=\s*'([^']+)'", query)
            if m:
                for model in self._models.values():
                    if model["NAME"] == m.group(1):
                        return MockCollectResult([model])
            return MockCollectResult([])

        if ".MODELS" in upper and "ORDER BY" in upper and "SELECT" in upper:
            return MockCollectResult(sorted(self._models.values(), key=lambda x: x["NAME"]))

        if "INSERT" in upper and "SNAPSHOTS" in upper:
            # Handle batched SELECT ... UNION ALL SELECT format
            for m in re.finditer(
                r"SELECT\s+'([^']+)',\s*'([^']+)',\s*(NULL|'[^']*'),\s*'([^']+)',\s*'([^']+)',\s*'([^']+)',\s*(NULL|'[^']*')",
                query,
                re.DOTALL,
            ):
                self._snapshots.append(
                    {
                        "SNAPSHOT_HASH": m.group(1),
                        "MODEL_HASH": m.group(2),
                        "PARENT_HASH": None if m.group(3) == "NULL" else m.group(3).strip("'"),
                        "TIMESTAMP": datetime(2025, 1, 1, tzinfo=timezone.utc),
                        "ACTOR": m.group(5),
                        "EVENT_TYPE": m.group(6),
                        "SOURCE": None if m.group(7) == "NULL" else m.group(7).strip("'"),
                        "PAYLOAD": {},
                        "TAGS": {},
                    }
                )
            return MockCollectResult([])

        if "SNAPSHOTS" in upper and "MODEL_HASH =" in upper and "ORDER BY" in upper:
            m = re.search(r"MODEL_HASH\s*=\s*'([^']+)'", query)
            if m:
                matching = [s for s in self._snapshots if s["MODEL_HASH"] == m.group(1)]
                if "EVENT_TYPE =" in upper:
                    et = re.search(r"EVENT_TYPE\s*=\s*'([^']+)'", query)
                    if et:
                        matching = [s for s in matching if s["EVENT_TYPE"] == et.group(1)]
                return MockCollectResult(matching)
            return MockCollectResult([])

        if "SNAPSHOTS" in upper and "DESC LIMIT 1" in upper:
            m = re.search(r"MODEL_HASH\s*=\s*'([^']+)'", query)
            if m:
                matching = [s for s in self._snapshots if s["MODEL_HASH"] == m.group(1)]
                return MockCollectResult(matching[-1:])
            return MockCollectResult([])

        if "MERGE INTO" in upper and "TAGS" in upper:
            m = re.search(
                r"SELECT\s+'([^']+)'\s+AS\s+model_hash,\s+'([^']+)'\s+AS\s+name,\s+'([^']+)'\s+AS\s+snapshot_hash",
                query,
                re.DOTALL,
            )
            if m:
                self._tags[(m.group(1), m.group(2))] = {
                    "MODEL_HASH": m.group(1),
                    "NAME": m.group(2),
                    "SNAPSHOT_HASH": m.group(3),
                    "UPDATED_AT": datetime(2025, 1, 1, tzinfo=timezone.utc),
                }
            return MockCollectResult([])

        if "TAGS" in upper and "MODEL_HASH =" in upper and "NAME =" in upper:
            mh = re.search(r"MODEL_HASH\s*=\s*'([^']+)'", query)
            nm = re.search(r"NAME\s*=\s*'([^']+)'", query)
            if mh and nm:
                key = (mh.group(1), nm.group(1))
                if key in self._tags:
                    return MockCollectResult([self._tags[key]])
            return MockCollectResult([])

        if "TAGS" in upper and "MODEL_HASH =" in upper and "ORDER BY" in upper:
            mh = re.search(r"MODEL_HASH\s*=\s*'([^']+)'", query)
            if mh:
                return MockCollectResult([v for k, v in self._tags.items() if k[0] == mh.group(1)])
            return MockCollectResult([])

        return MockCollectResult([])


@pytest.fixture
def backend():
    from model_ledger.backends.snowflake import SnowflakeLedgerBackend

    return SnowflakeLedgerBackend(schema="TEST_SCHEMA", connection=MockLedgerSession())


def _make_model(name="test-model", model_hash="abc123"):
    return ModelRef(
        model_hash=model_hash,
        name=name,
        owner="test-owner",
        model_type="ml_model",
        model_origin="internal",
        tier="high",
        purpose="testing",
        status="active",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


def test_save_and_get_model(backend):
    model = _make_model()
    backend.save_model(model)
    ref = backend.get_model("abc123")
    assert ref is not None
    assert ref.name == "test-model"
    assert ref.model_type == "ml_model"


def test_get_model_by_name(backend):
    backend.save_model(_make_model())
    ref = backend.get_model_by_name("test-model")
    assert ref is not None
    assert ref.model_hash == "abc123"


def test_get_model_not_found(backend):
    assert backend.get_model("nonexistent") is None


def test_list_models(backend):
    backend.save_model(_make_model("model-a", "h1"))
    backend.save_model(_make_model("model-b", "h2"))
    assert len(backend.list_models()) == 2


def test_append_and_list_snapshots(backend):
    snap = Snapshot(
        snapshot_hash="snap1",
        model_hash="m1",
        timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        actor="scanner",
        event_type="registered",
        source="alerting",
        payload={"rule_count": 42},
    )
    backend.append_snapshot(snap)
    snaps = backend.list_snapshots("m1")
    assert len(snaps) == 1
    assert snaps[0].event_type == "registered"


def test_list_snapshots_by_event_type(backend):
    for et in ["registered", "enriched", "not_found"]:
        backend.append_snapshot(
            Snapshot(
                snapshot_hash=f"s-{et}",
                model_hash="m1",
                timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
                actor="scanner",
                event_type=et,
                source="alerting",
            )
        )
    assert len(backend.list_snapshots("m1", event_type="enriched")) == 1


def test_set_and_get_tag(backend):
    tag = Tag(
        model_hash="m1",
        name="latest",
        snapshot_hash="snap1",
        updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    backend.set_tag(tag)
    result = backend.get_tag("m1", "latest")
    assert result is not None
    assert result.snapshot_hash == "snap1"


def test_get_tag_not_found(backend):
    assert backend.get_tag("m1", "nonexistent") is None


def test_list_tags(backend):
    for name in ["latest", "prod"]:
        backend.set_tag(
            Tag(
                model_hash="m1",
                name=name,
                snapshot_hash=f"s-{name}",
                updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            )
        )
    assert len(backend.list_tags("m1")) == 2
