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


def test_alter_table_swallows_already_exists_error(monkeypatch):
    """The 'already exists' error during ALTER TABLE is swallowed; others bubble up."""
    from model_ledger.backends import snowflake as sf_module

    # Collect _exec_no_result calls; raise for the ALTER TABLE specifically.
    call_log: list[str] = []

    def fake_exec(session, sql: str, *args, **kwargs):
        call_log.append(sql)
        if "ALTER TABLE" in sql and "METADATA VARIANT" in sql:
            raise RuntimeError("Column 'METADATA' already exists")

    monkeypatch.setattr(sf_module, "_exec_no_result", fake_exec)

    from model_ledger.backends.snowflake import SnowflakeLedgerBackend

    # Construction triggers the DDL path. Should not raise.
    SnowflakeLedgerBackend(connection=object(), schema="TEST.LEDGER")
    # Confirm ALTER TABLE was attempted at least once
    assert any("ALTER TABLE" in sql for sql in call_log)


def test_alter_table_reraises_non_duplicate_error(monkeypatch):
    """Any error other than 'already exists' must propagate."""
    from model_ledger.backends import snowflake as sf_module

    def fake_exec(session, sql: str, *args, **kwargs):
        if "ALTER TABLE" in sql and "METADATA VARIANT" in sql:
            raise RuntimeError("insufficient privileges for ALTER TABLE")

    monkeypatch.setattr(sf_module, "_exec_no_result", fake_exec)

    from model_ledger.backends.snowflake import SnowflakeLedgerBackend

    with pytest.raises(RuntimeError, match="insufficient privileges"):
        SnowflakeLedgerBackend(connection=object(), schema="TEST.LEDGER")


def test_flush_dedups_model_buffer_by_hash():
    """register() and update_model() both buffer the same new model in one
    Ledger.add() pass. Without dedup, the MERGE inserts both copies because the
    target row doesn't exist yet (empty-target INSERT fires per source row),
    producing duplicate rows. _flush_models must collapse the buffer by
    model_hash so each model reaches the MERGE exactly once.
    """
    from model_ledger.backends.snowflake import SnowflakeLedgerBackend

    seen_hashes: list[str] = []

    class RecordingSession:
        """Captures every model_hash that appears in a MODELS MERGE source."""

        def sql(self, query: str, params: Any = None) -> MockCollectResult:
            if "MERGE INTO" in query.upper() and ".MODELS " in query.upper():
                for m in re.finditer(r"'([^']+)'\s+AS\s+model_hash", query):
                    seen_hashes.append(m.group(1))
            return MockCollectResult([])

    backend = SnowflakeLedgerBackend(schema="TEST_SCHEMA", connection=RecordingSession())
    model = ModelRef(
        name="fraud_scorer",
        owner="risk-team",
        model_type="scoring_model",
        tier="unclassified",
        purpose="",
    )
    backend.save_model(model)  # register() path
    backend.save_model(model)  # update_model() path (same hash)
    backend.flush()

    assert seen_hashes.count(model.model_hash) == 1, (
        f"model written {seen_hashes.count(model.model_hash)}x to MERGE source, expected 1"
    )


class FakeCompositeSummarySession:
    """Captures every SQL statement; returns canned rows for the summary query."""

    def __init__(self, rows=None):
        self.queries: list[str] = []
        self._rows = rows or []

    def sql(self, query: str, params: Any = None) -> MockCollectResult:
        self.queries.append(query)
        if "WITH composites AS" in query:
            return MockCollectResult(self._rows)
        return MockCollectResult([])


class TestCompositeSummarySQL:
    def _backend(self, rows=None):
        from model_ledger.backends.snowflake import SnowflakeLedgerBackend

        session = FakeCompositeSummarySession(rows)
        backend = SnowflakeLedgerBackend(schema="TEST_SCHEMA", connection=session)
        session.queries.clear()  # drop the _ensure_tables DDL
        return backend, session

    def test_single_statement_with_type_pushdown(self):
        backend, session = self._backend()
        backend.composite_summary(model_types=["ml_model", "heuristic"])
        assert len(session.queries) == 1, "composite_summary must issue exactly one statement"
        sql = session.queries[0]
        assert "MODEL_TYPE IN ('ml_model', 'heuristic')" in sql
        assert "V_COMPOSITES" not in sql, "must not depend on an externally-managed view"

    def test_default_model_type_is_composite(self):
        backend, session = self._backend()
        backend.composite_summary()
        assert "MODEL_TYPE IN ('composite')" in session.queries[0]

    def test_model_types_are_escaped(self):
        backend, session = self._backend()
        backend.composite_summary(model_types=["ty'pe"])
        assert "'ty''pe'" in session.queries[0]

    def test_replicates_sdk_replay_semantics_in_sql(self):
        """The single statement must encode the SDK fallback semantics."""
        backend, session = self._backend()
        backend.composite_summary()
        sql = session.queries[0]
        # membership baseline: member_of dependency links resolved against MODELS
        assert "'member_of'" in sql
        assert "upstream_hash" in sql
        # event overlay: latest op wins per (composite, member)
        assert "member_added" in sql and "member_removed" in sql
        assert "ROW_NUMBER() OVER" in sql
        # open observations: distinct-id set semantics, not raw event counts
        assert "observation_id" in sql
        assert "COUNT_IF(EVENT_TYPE = 'observation_resolved') = 0" in sql

    def test_row_mapping_and_null_coalescing(self):
        ts = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        rows = [
            {
                "NAME": "credit-scorecard",
                "OWNER": "risk-team",
                "TIER": "high",
                "STATUS": "active",
                "MODEL_TYPE": "composite",
                "MEMBER_COUNT": 3,
                "LAST_VALIDATED": ts,
                "OPEN_OBSERVATION_COUNT": 1,
                "METADATA": '{"source": "registry"}',
            },
            {
                "NAME": "empty-group",
                "OWNER": "ops-team",
                "TIER": "low",
                "STATUS": "active",
                "MODEL_TYPE": "composite",
                "MEMBER_COUNT": None,
                "LAST_VALIDATED": None,
                "OPEN_OBSERVATION_COUNT": None,
                "METADATA": None,
            },
        ]
        backend, _ = self._backend(rows)
        result = backend.composite_summary()
        assert result == [
            {
                "name": "credit-scorecard",
                "owner": "risk-team",
                "tier": "high",
                "status": "active",
                "model_type": "composite",
                "member_count": 3,
                "last_validated": ts,
                "open_observation_count": 1,
                "metadata": {"source": "registry"},
            },
            {
                "name": "empty-group",
                "owner": "ops-team",
                "tier": "low",
                "status": "active",
                "model_type": "composite",
                "member_count": 0,
                "last_validated": None,
                "open_observation_count": 0,
                "metadata": {},
            },
        ]

    def test_last_validated_string_coerced_to_datetime(self):
        rows = [
            {
                "NAME": "g",
                "OWNER": "o",
                "TIER": "t",
                "STATUS": "active",
                "MODEL_TYPE": "composite",
                "MEMBER_COUNT": 0,
                "LAST_VALIDATED": "2026-01-02T03:04:05+00:00",
                "OPEN_OBSERVATION_COUNT": 0,
                "METADATA": None,
            }
        ]
        backend, _ = self._backend(rows)
        result = backend.composite_summary()
        assert result[0]["last_validated"] == datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

    def test_flushes_buffered_writes_before_querying(self):
        from model_ledger.core.ledger_models import ModelRef

        backend, session = self._backend()
        backend.save_model(
            ModelRef(name="g", owner="o", model_type="composite", tier="high", purpose="")
        )
        backend.composite_summary()
        merge_idx = next(i for i, q in enumerate(session.queries) if "MERGE INTO" in q)
        select_idx = next(i for i, q in enumerate(session.queries) if "WITH composites AS" in q)
        assert merge_idx < select_idx

    def test_parity_with_in_memory_fallback(self):
        """Recorded-rows parity: the Snowflake mapping must produce exactly the
        dicts the SDK fallback produces for an equivalent event history.

        Scenario (mirrored between the in-memory ledger and the recorded rows):
        - 'credit-scorecard' seeded with one member via register_group (dep-link
          baseline), one member added via add_member, one added then removed
          (latest op wins -> excluded): member_count == 2
        - OBS-1 issued then resolved, OBS-2 issued: open_observation_count == 1
        - one validated event: last_validated == its timestamp
        """
        from model_ledger.sdk.ledger import Ledger

        ledger = Ledger()  # InMemoryLedgerBackend: no composite_summary -> fallback
        for name in ["feature_pipeline", "scoring_model", "alert_queue"]:
            ledger.register(
                name=name, owner="risk-team", model_type="ml_model", tier="high", purpose="x"
            )
        ledger.register_group(
            name="credit-scorecard",
            owner="risk-team",
            model_type="composite",
            tier="high",
            purpose="Credit risk scoring pipeline",
            members=["feature_pipeline"],
            actor="test",
            metadata={"source": "registry"},
        )
        ledger.add_member("credit-scorecard", "scoring_model", actor="test")
        ledger.add_member("credit-scorecard", "alert_queue", actor="test")
        ledger.remove_member("credit-scorecard", "alert_queue", actor="test")
        ledger.record_observation(
            "credit-scorecard", observation_id="OBS-1", observation="a", status="open", actor="t"
        )
        ledger.record_observation(
            "credit-scorecard", observation_id="OBS-2", observation="b", status="open", actor="t"
        )
        ledger.resolve_observation(
            "credit-scorecard", observation_id="OBS-1", resolution="fixed", actor="t"
        )
        ledger.record_validation("credit-scorecard", result="passed", actor="t")

        expected = ledger.composite_summary()
        assert len(expected) == 1
        assert expected[0]["member_count"] == 2
        assert expected[0]["open_observation_count"] == 1

        # Recorded rows: what the single-statement SQL returns for this history.
        rows = [
            {
                "NAME": "credit-scorecard",
                "OWNER": "risk-team",
                "TIER": "high",
                "STATUS": "active",
                "MODEL_TYPE": "composite",
                "MEMBER_COUNT": 2,
                "LAST_VALIDATED": expected[0]["last_validated"],
                "OPEN_OBSERVATION_COUNT": 1,
                "METADATA": '{"source": "registry"}',
            }
        ]
        backend, _ = self._backend(rows)
        assert backend.composite_summary() == expected
