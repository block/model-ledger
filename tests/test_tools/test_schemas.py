# tests/test_tools/test_schemas.py
"""Tests for agent protocol I/O schemas."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from model_ledger.tools.schemas import (
    ChangelogInput,
    ChangelogOutput,
    DependencyNode,
    DiscoverInput,
    DiscoverOutput,
    EventDetail,
    EventSummary,
    InvestigateInput,
    InvestigateOutput,
    ModelSummary,
    QueryInput,
    QueryOutput,
    RecordInput,
    RecordOutput,
    TraceInput,
    TraceOutput,
)

# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------


class TestModelSummary:
    def test_all_fields(self):
        ts = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        m = ModelSummary(
            name="credit-scorecard",
            owner="risk-team",
            model_type="ml_model",
            platform="sagemaker",
            status="active",
            last_event=ts,
            event_count=42,
        )
        assert m.name == "credit-scorecard"
        assert m.owner == "risk-team"
        assert m.model_type == "ml_model"
        assert m.platform == "sagemaker"
        assert m.status == "active"
        assert m.last_event == ts
        assert m.event_count == 42

    def test_optional_fields_none(self):
        m = ModelSummary(name="basic-model")
        assert m.owner is None
        assert m.model_type is None
        assert m.platform is None
        assert m.status is None
        assert m.last_event is None
        assert m.event_count == 0

    def test_json_roundtrip(self):
        ts = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        m = ModelSummary(
            name="credit-scorecard",
            owner="risk-team",
            model_type="ml_model",
            platform="sagemaker",
            status="active",
            last_event=ts,
            event_count=42,
        )
        data = m.model_dump(mode="json")
        reconstructed = ModelSummary(**data)
        assert reconstructed == m

    def test_json_schema_export(self):
        schema = ModelSummary.model_json_schema()
        assert schema["type"] == "object"
        assert "name" in schema["properties"]
        assert "event_count" in schema["properties"]


class TestEventSummary:
    def test_all_fields(self):
        ts = datetime(2026, 3, 1, 9, 0, 0, tzinfo=timezone.utc)
        e = EventSummary(
            event_type="validation",
            timestamp=ts,
            actor="alice",
            summary="Passed all checks",
        )
        assert e.event_type == "validation"
        assert e.timestamp == ts
        assert e.actor == "alice"
        assert e.summary == "Passed all checks"

    def test_optional_fields_none(self):
        e = EventSummary(event_type="registered")
        assert e.timestamp is None
        assert e.actor is None
        assert e.summary is None

    def test_json_roundtrip(self):
        ts = datetime(2026, 3, 1, 9, 0, 0, tzinfo=timezone.utc)
        e = EventSummary(event_type="validation", timestamp=ts, actor="alice")
        data = e.model_dump(mode="json")
        assert EventSummary(**data) == e


class TestEventDetail:
    def test_inherits_event_summary(self):
        ts = datetime(2026, 3, 1, 9, 0, 0, tzinfo=timezone.utc)
        d = EventDetail(
            event_type="validation",
            timestamp=ts,
            actor="alice",
            summary="OK",
            model_name="credit-scorecard",
            payload={"score": 0.95},
        )
        assert isinstance(d, EventSummary)
        assert d.model_name == "credit-scorecard"
        assert d.payload == {"score": 0.95}

    def test_defaults(self):
        d = EventDetail(event_type="registered")
        assert d.model_name is None
        assert d.payload == {}

    def test_json_roundtrip(self):
        d = EventDetail(
            event_type="deployed",
            model_name="fraud-detector",
            payload={"version": "2.1"},
        )
        data = d.model_dump(mode="json")
        assert EventDetail(**data) == d

    def test_json_schema_has_parent_fields(self):
        schema = EventDetail.model_json_schema()
        props = schema["properties"]
        assert "event_type" in props
        assert "model_name" in props
        assert "payload" in props


class TestDependencyNode:
    def test_all_fields(self):
        n = DependencyNode(
            name="feature-pipeline",
            platform="airflow",
            depth=2,
            relationship="upstream",
        )
        assert n.name == "feature-pipeline"
        assert n.platform == "airflow"
        assert n.depth == 2
        assert n.relationship == "upstream"

    def test_defaults(self):
        n = DependencyNode(name="scoring-model")
        assert n.platform is None
        assert n.depth == 0
        assert n.relationship is None

    def test_json_roundtrip(self):
        n = DependencyNode(name="etl-job", platform="spark", depth=1, relationship="downstream")
        data = n.model_dump(mode="json")
        assert DependencyNode(**data) == n


# ---------------------------------------------------------------------------
# RecordInput / RecordOutput
# ---------------------------------------------------------------------------


class TestRecordInput:
    def test_all_fields(self):
        r = RecordInput(
            model_name="credit-scorecard",
            event="deployed",
            payload={"version": "3.0"},
            actor="deployer",
            owner="risk-team",
            model_type="ml_model",
            purpose="Credit risk scoring",
        )
        assert r.model_name == "credit-scorecard"
        assert r.event == "deployed"
        assert r.payload == {"version": "3.0"}
        assert r.actor == "deployer"
        assert r.owner == "risk-team"
        assert r.model_type == "ml_model"
        assert r.purpose == "Credit risk scoring"

    def test_defaults(self):
        r = RecordInput(model_name="test-model", event="registered")
        assert r.payload == {}
        assert r.actor == "user"
        assert r.owner is None
        assert r.model_type is None
        assert r.purpose is None

    def test_json_roundtrip(self):
        r = RecordInput(model_name="test-model", event="registered")
        data = r.model_dump(mode="json")
        assert RecordInput(**data) == r

    def test_json_schema_export(self):
        schema = RecordInput.model_json_schema()
        assert "model_name" in schema["properties"]
        assert "event" in schema["properties"]
        required = schema.get("required", [])
        assert "model_name" in required
        assert "event" in required


class TestRecordOutput:
    def test_all_fields(self):
        ts = datetime(2026, 4, 1, 10, 0, 0, tzinfo=timezone.utc)
        r = RecordOutput(
            model_name="credit-scorecard",
            event_id="abc123",
            timestamp=ts,
            is_new_model=True,
        )
        assert r.model_name == "credit-scorecard"
        assert r.event_id == "abc123"
        assert r.timestamp == ts
        assert r.is_new_model is True

    def test_json_roundtrip(self):
        ts = datetime(2026, 4, 1, 10, 0, 0, tzinfo=timezone.utc)
        r = RecordOutput(model_name="test", event_id="x", timestamp=ts, is_new_model=False)
        data = r.model_dump(mode="json")
        assert RecordOutput(**data) == r


# ---------------------------------------------------------------------------
# QueryInput / QueryOutput
# ---------------------------------------------------------------------------


class TestQueryInput:
    def test_defaults(self):
        q = QueryInput()
        assert q.text is None
        assert q.platform is None
        assert q.model_type is None
        assert q.owner is None
        assert q.status is None
        assert q.limit == 50
        assert q.offset == 0

    def test_all_fields(self):
        q = QueryInput(
            text="fraud",
            platform="sagemaker",
            model_type="ml_model",
            owner="risk-team",
            status="active",
            limit=10,
            offset=5,
        )
        assert q.text == "fraud"
        assert q.limit == 10
        assert q.offset == 5

    def test_json_roundtrip(self):
        q = QueryInput(text="scoring", limit=25)
        data = q.model_dump(mode="json")
        assert QueryInput(**data) == q


class TestQueryOutput:
    def test_all_fields(self):
        m = ModelSummary(name="test-model", owner="alice")
        q = QueryOutput(total=1, models=[m], has_more=False)
        assert q.total == 1
        assert len(q.models) == 1
        assert q.has_more is False

    def test_empty_results(self):
        q = QueryOutput(total=0, models=[], has_more=False)
        assert q.models == []

    def test_json_roundtrip(self):
        m = ModelSummary(name="test-model", event_count=5)
        q = QueryOutput(total=100, models=[m], has_more=True)
        data = q.model_dump(mode="json")
        reconstructed = QueryOutput(**data)
        assert reconstructed.total == 100
        assert reconstructed.models[0].name == "test-model"
        assert reconstructed.has_more is True


# ---------------------------------------------------------------------------
# InvestigateInput / InvestigateOutput
# ---------------------------------------------------------------------------


class TestInvestigateInput:
    def test_defaults(self):
        i = InvestigateInput(model_name="credit-scorecard")
        assert i.model_name == "credit-scorecard"
        assert i.detail == "summary"
        assert i.as_of is None

    def test_all_fields(self):
        ts = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        i = InvestigateInput(model_name="test", detail="full", as_of=ts)
        assert i.detail == "full"
        assert i.as_of == ts

    def test_json_roundtrip(self):
        i = InvestigateInput(model_name="test", detail="full")
        data = i.model_dump(mode="json")
        assert InvestigateInput(**data) == i


class TestInvestigateOutput:
    def test_all_fields(self):
        ts = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        event = EventSummary(event_type="deployed", timestamp=ts)
        dep = DependencyNode(name="feature-pipeline", depth=1)
        o = InvestigateOutput(
            name="credit-scorecard",
            owner="risk-team",
            model_type="ml_model",
            purpose="Credit risk scoring",
            status="active",
            created_at=ts,
            metadata={"version": "3.0"},
            recent_events=[event],
            days_since_last_event=5,
            total_events=42,
            upstream=[dep],
            downstream=[],
            groups=["risk-models"],
            members=[],
        )
        assert o.name == "credit-scorecard"
        assert o.owner == "risk-team"
        assert o.total_events == 42
        assert len(o.upstream) == 1
        assert o.groups == ["risk-models"]

    def test_defaults(self):
        o = InvestigateOutput(name="basic-model")
        assert o.owner is None
        assert o.model_type is None
        assert o.purpose is None
        assert o.status is None
        assert o.created_at is None
        assert o.metadata == {}
        assert o.recent_events == []
        assert o.days_since_last_event is None
        assert o.total_events == 0
        assert o.upstream == []
        assert o.downstream == []
        assert o.groups == []
        assert o.members == []

    def test_json_roundtrip(self):
        ts = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        o = InvestigateOutput(
            name="test",
            owner="alice",
            created_at=ts,
            recent_events=[EventSummary(event_type="registered")],
            upstream=[DependencyNode(name="dep-a")],
        )
        data = o.model_dump(mode="json")
        reconstructed = InvestigateOutput(**data)
        assert reconstructed.name == "test"
        assert len(reconstructed.recent_events) == 1
        assert len(reconstructed.upstream) == 1

    def test_json_schema_export(self):
        schema = InvestigateOutput.model_json_schema()
        props = schema["properties"]
        assert "name" in props
        assert "recent_events" in props
        assert "upstream" in props
        assert "downstream" in props


# ---------------------------------------------------------------------------
# TraceInput / TraceOutput
# ---------------------------------------------------------------------------


class TestTraceInput:
    def test_defaults(self):
        t = TraceInput(name="credit-scorecard")
        assert t.name == "credit-scorecard"
        assert t.direction == "both"
        assert t.depth is None

    def test_all_fields(self):
        t = TraceInput(name="test", direction="upstream", depth=3)
        assert t.direction == "upstream"
        assert t.depth == 3

    def test_json_roundtrip(self):
        t = TraceInput(name="test", direction="downstream", depth=2)
        data = t.model_dump(mode="json")
        assert TraceInput(**data) == t


class TestTraceOutput:
    def test_all_fields(self):
        up = DependencyNode(name="data-source", depth=1, relationship="upstream")
        down = DependencyNode(name="dashboard", depth=1, relationship="downstream")
        t = TraceOutput(
            root="credit-scorecard",
            upstream=[up],
            downstream=[down],
            total_nodes=2,
        )
        assert t.root == "credit-scorecard"
        assert len(t.upstream) == 1
        assert len(t.downstream) == 1
        assert t.total_nodes == 2

    def test_defaults(self):
        t = TraceOutput(root="test")
        assert t.upstream == []
        assert t.downstream == []
        assert t.total_nodes == 0

    def test_json_roundtrip(self):
        t = TraceOutput(
            root="test",
            upstream=[DependencyNode(name="a", depth=1)],
            downstream=[DependencyNode(name="b", depth=1)],
            total_nodes=2,
        )
        data = t.model_dump(mode="json")
        reconstructed = TraceOutput(**data)
        assert reconstructed.root == "test"
        assert len(reconstructed.upstream) == 1
        assert len(reconstructed.downstream) == 1


# ---------------------------------------------------------------------------
# ChangelogInput / ChangelogOutput
# ---------------------------------------------------------------------------


class TestChangelogInput:
    def test_defaults(self):
        c = ChangelogInput()
        assert c.since is None
        assert c.until is None
        assert c.model_name is None
        assert c.event_type is None
        assert c.limit == 100
        assert c.offset == 0

    def test_all_fields(self):
        ts1 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        ts2 = datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
        c = ChangelogInput(
            since=ts1,
            until=ts2,
            model_name="credit-scorecard",
            event_type="deployed",
            limit=25,
            offset=10,
        )
        assert c.since == ts1
        assert c.until == ts2
        assert c.model_name == "credit-scorecard"
        assert c.event_type == "deployed"
        assert c.limit == 25
        assert c.offset == 10

    def test_json_roundtrip(self):
        c = ChangelogInput(model_name="test", limit=50)
        data = c.model_dump(mode="json")
        assert ChangelogInput(**data) == c


class TestChangelogOutput:
    def test_all_fields(self):
        event = EventDetail(
            event_type="deployed",
            model_name="credit-scorecard",
            payload={"version": "2.0"},
        )
        c = ChangelogOutput(
            total=1,
            events=[event],
            has_more=False,
            period="2026-01-01 to 2026-03-01",
        )
        assert c.total == 1
        assert len(c.events) == 1
        assert c.has_more is False
        assert c.period == "2026-01-01 to 2026-03-01"

    def test_defaults(self):
        c = ChangelogOutput(total=0, events=[], has_more=False)
        assert c.period is None

    def test_json_roundtrip(self):
        event = EventDetail(event_type="registered", model_name="test")
        c = ChangelogOutput(total=1, events=[event], has_more=False, period="all time")
        data = c.model_dump(mode="json")
        reconstructed = ChangelogOutput(**data)
        assert reconstructed.total == 1
        assert reconstructed.events[0].model_name == "test"


# ---------------------------------------------------------------------------
# DiscoverInput / DiscoverOutput
# ---------------------------------------------------------------------------


class TestDiscoverInput:
    def test_connector_source(self):
        d = DiscoverInput(
            source_type="connector",
            connector_name="sql-registry",
            connector_config={"query": "SELECT * FROM models"},
        )
        assert d.source_type == "connector"
        assert d.connector_name == "sql-registry"
        assert d.connector_config == {"query": "SELECT * FROM models"}
        assert d.auto_connect is True

    def test_file_source(self):
        d = DiscoverInput(source_type="file", file_path="/data/models.csv")
        assert d.source_type == "file"
        assert d.file_path == "/data/models.csv"

    def test_inline_source(self):
        models = [{"name": "test-model", "owner": "alice"}]
        d = DiscoverInput(source_type="inline", models=models)
        assert d.source_type == "inline"
        assert d.models == models

    def test_defaults(self):
        d = DiscoverInput(source_type="connector")
        assert d.connector_name is None
        assert d.connector_config is None
        assert d.file_path is None
        assert d.models is None
        assert d.auto_connect is True

    def test_auto_connect_false(self):
        d = DiscoverInput(source_type="inline", auto_connect=False)
        assert d.auto_connect is False

    def test_json_roundtrip(self):
        d = DiscoverInput(
            source_type="connector",
            connector_name="github",
            connector_config={"org": "my-org"},
            auto_connect=False,
        )
        data = d.model_dump(mode="json")
        assert DiscoverInput(**data) == d

    def test_json_schema_source_type_literal(self):
        schema = DiscoverInput.model_json_schema()
        source_prop = schema["properties"]["source_type"]
        # Should be constrained to the three valid values
        assert "enum" in source_prop or "anyOf" in source_prop or "const" in source_prop


class TestDiscoverOutput:
    def test_all_fields(self):
        m = ModelSummary(name="discovered-model", platform="airflow")
        d = DiscoverOutput(
            models_added=3,
            models_skipped=1,
            links_created=5,
            models=[m],
            errors=["Failed to parse row 7"],
        )
        assert d.models_added == 3
        assert d.models_skipped == 1
        assert d.links_created == 5
        assert len(d.models) == 1
        assert d.errors == ["Failed to parse row 7"]

    def test_defaults(self):
        d = DiscoverOutput(models_added=0, models_skipped=0, links_created=0)
        assert d.models == []
        assert d.errors == []

    def test_json_roundtrip(self):
        m = ModelSummary(name="test", event_count=0)
        d = DiscoverOutput(
            models_added=1,
            models_skipped=0,
            links_created=0,
            models=[m],
            errors=[],
        )
        data = d.model_dump(mode="json")
        reconstructed = DiscoverOutput(**data)
        assert reconstructed.models_added == 1
        assert reconstructed.models[0].name == "test"

    def test_json_schema_export(self):
        schema = DiscoverOutput.model_json_schema()
        props = schema["properties"]
        assert "models_added" in props
        assert "models" in props
        assert "errors" in props


# ---------------------------------------------------------------------------
# Cross-cutting: all schemas produce valid JSON Schema
# ---------------------------------------------------------------------------


ALL_SCHEMAS = [
    ModelSummary,
    EventSummary,
    EventDetail,
    DependencyNode,
    RecordInput,
    RecordOutput,
    QueryInput,
    QueryOutput,
    InvestigateInput,
    InvestigateOutput,
    TraceInput,
    TraceOutput,
    ChangelogInput,
    ChangelogOutput,
    DiscoverInput,
    DiscoverOutput,
]


@pytest.mark.parametrize("schema_cls", ALL_SCHEMAS, ids=lambda c: c.__name__)
def test_all_schemas_export_json_schema(schema_cls):
    """Every schema must produce a valid JSON Schema dict with type=object."""
    schema = schema_cls.model_json_schema()
    assert isinstance(schema, dict)
    assert schema.get("type") == "object"
    assert "properties" in schema
