"""Tests for Ledger SDK — tool-shaped API for v0.3.0."""

from datetime import datetime, timedelta, timezone

import pytest

from model_ledger.backends.ledger_memory import InMemoryLedgerBackend
from model_ledger.sdk.ledger import Ledger, ModelNotFoundError


@pytest.fixture
def ledger():
    return Ledger(backend=InMemoryLedgerBackend())


class TestRegister:
    def test_register_model(self, ledger):
        model = ledger.register(
            name="fraud-detector",
            owner="ml-team",
            model_type="ml_model",
            tier="high",
            purpose="Detect fraud",
        )
        assert model.name == "fraud-detector"
        assert model.model_hash

    def test_register_idempotent(self, ledger):
        m1 = ledger.register(
            name="a",
            owner="b",
            model_type="ml",
            tier="high",
            purpose="x",
        )
        m2 = ledger.register(
            name="a",
            owner="b",
            model_type="ml",
            tier="high",
            purpose="x",
        )
        assert m1.model_hash == m2.model_hash

    def test_register_creates_snapshot(self, ledger):
        model = ledger.register(
            name="a",
            owner="b",
            model_type="ml",
            tier="high",
            purpose="x",
        )
        snaps = ledger.history(model)
        assert len(snaps) == 1
        assert snaps[0].event_type == "registered"

    def test_register_with_model_origin(self, ledger):
        model = ledger.register(
            name="vendor-model",
            owner="vendor-co",
            model_type="vendor",
            tier="high",
            purpose="Credit scoring",
            model_origin="vendor",
        )
        assert model.model_origin == "vendor"

    def test_register_stores_metadata_on_modelref(self, ledger):
        ref = ledger.register(
            name="Credit Scorecard v2",
            owner="risk-team",
            model_type="ml_model",
            tier="high",
            purpose="Credit risk scoring",
            actor="test",
            metadata={"version": "2.0", "region": "us"},
        )
        assert ref.metadata == {"version": "2.0", "region": "us"}
        # persists across backend round-trip
        retrieved = ledger.get("Credit Scorecard v2")
        assert retrieved.metadata == {"version": "2.0", "region": "us"}

    def test_register_defaults_to_empty_metadata(self, ledger):
        ref = ledger.register(
            name="Fraud Scorecard",
            owner="risk-team",
            model_type="ml_model",
            tier="medium",
            purpose="Legacy model",
            actor="test",
        )
        assert ref.metadata == {}


class TestRecord:
    def test_record_snapshot(self, ledger):
        model = ledger.register(
            name="a",
            owner="b",
            model_type="ml",
            tier="high",
            purpose="x",
        )
        snap = ledger.record(
            model,
            event="introspected",
            source="ml_platform",
            payload={"features": ["f1"]},
            actor="test",
        )
        assert snap.event_type == "introspected"
        assert snap.payload == {"features": ["f1"]}

    def test_record_with_model_name(self, ledger):
        ledger.register(
            name="a",
            owner="b",
            model_type="ml",
            tier="high",
            purpose="x",
        )
        snap = ledger.record("a", event="tested", payload={}, actor="ci")
        assert snap.model_hash


class TestTag:
    def test_tag_model(self, ledger):
        model = ledger.register(
            name="a",
            owner="b",
            model_type="ml",
            tier="high",
            purpose="x",
        )
        snap = ledger.record(
            model,
            event="deployed",
            payload={},
            actor="ci",
        )
        tag = ledger.tag(model, "active")
        assert tag.snapshot_hash == snap.snapshot_hash

    def test_tag_moves(self, ledger):
        model = ledger.register(
            name="a",
            owner="b",
            model_type="ml",
            tier="high",
            purpose="x",
        )
        ledger.record(model, event="v1", payload={}, actor="x")
        ledger.tag(model, "active")
        s2 = ledger.record(model, event="v2", payload={}, actor="x")
        tag = ledger.tag(model, "active")
        assert tag.snapshot_hash == s2.snapshot_hash


class TestQuery:
    def test_get_by_name(self, ledger):
        ledger.register(
            name="my-model",
            owner="team",
            model_type="ml",
            tier="high",
            purpose="x",
        )
        result = ledger.get("my-model")
        assert result.name == "my-model"

    def test_get_nonexistent_raises(self, ledger):
        with pytest.raises(ModelNotFoundError):
            ledger.get("nonexistent")

    def test_list_all(self, ledger):
        ledger.register(
            name="a",
            owner="t",
            model_type="ml",
            tier="high",
            purpose="x",
        )
        ledger.register(
            name="b",
            owner="t",
            model_type="heuristic",
            tier="low",
            purpose="y",
        )
        assert len(ledger.list()) == 2

    def test_list_filtered(self, ledger):
        ledger.register(
            name="a",
            owner="t",
            model_type="ml",
            tier="high",
            purpose="x",
        )
        ledger.register(
            name="b",
            owner="t",
            model_type="heuristic",
            tier="low",
            purpose="y",
        )
        assert len(ledger.list(model_type="ml")) == 1


class TestHistory:
    def test_history_returns_newest_first(self, ledger):
        model = ledger.register(
            name="a",
            owner="b",
            model_type="ml",
            tier="high",
            purpose="x",
        )
        ledger.record(
            model,
            event="introspected",
            payload={"v": 1},
            actor="x",
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        ledger.record(
            model,
            event="validated",
            payload={"v": 2},
            actor="x",
            timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        snaps = ledger.history(model)
        assert snaps[0].timestamp > snaps[1].timestamp

    def test_latest(self, ledger):
        model = ledger.register(
            name="a",
            owner="b",
            model_type="ml",
            tier="high",
            purpose="x",
        )
        ledger.record(
            model,
            event="v1",
            payload={},
            actor="x",
            timestamp=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        ledger.record(
            model,
            event="v2",
            payload={},
            actor="x",
            timestamp=datetime(2099, 1, 2, tzinfo=timezone.utc),
        )
        latest = ledger.latest(model)
        assert latest.event_type == "v2"


class TestDependencies:
    def test_link_dependency_creates_two_snapshots(self, ledger):
        ledger.register(
            name="feature-a",
            owner="team",
            model_type="signal",
            tier="unclassified",
            purpose="velocity feature",
        )
        ledger.register(
            name="fraud-model",
            owner="team",
            model_type="ml_model",
            tier="high",
            purpose="Detect fraud",
        )
        up_snap, down_snap = ledger.link_dependency(
            "feature-a",
            "fraud-model",
            relationship="consumes",
            actor="scanner:ml_platform",
        )
        assert up_snap.event_type == "has_dependent"
        assert up_snap.payload["downstream"] == "fraud-model"
        assert up_snap.payload["relationship"] == "consumes"
        assert down_snap.event_type == "depends_on"
        assert down_snap.payload["upstream"] == "feature-a"

    def test_dependencies_upstream(self, ledger):
        ledger.register(
            name="signal-x",
            owner="t",
            model_type="signal",
            tier="unclassified",
            purpose="x",
        )
        ledger.register(
            name="model-a",
            owner="t",
            model_type="ml_model",
            tier="high",
            purpose="x",
        )
        ledger.link_dependency(
            "signal-x",
            "model-a",
            relationship="consumes",
            actor="test",
        )
        deps = ledger.dependencies("model-a", direction="upstream")
        assert len(deps) == 1
        assert deps[0]["model"].name == "signal-x"
        assert deps[0]["relationship"] == "consumes"
        assert deps[0]["direction"] == "upstream"

    def test_dependencies_downstream(self, ledger):
        ledger.register(
            name="signal-x",
            owner="t",
            model_type="signal",
            tier="unclassified",
            purpose="x",
        )
        ledger.register(
            name="model-a",
            owner="t",
            model_type="ml_model",
            tier="high",
            purpose="x",
        )
        ledger.link_dependency(
            "signal-x",
            "model-a",
            relationship="consumes",
            actor="test",
        )
        deps = ledger.dependencies("signal-x", direction="downstream")
        assert len(deps) == 1
        assert deps[0]["model"].name == "model-a"

    def test_dependencies_both_directions(self, ledger):
        ledger.register(
            name="signal-x",
            owner="t",
            model_type="signal",
            tier="unclassified",
            purpose="x",
        )
        ledger.register(
            name="model-a",
            owner="t",
            model_type="ml_model",
            tier="high",
            purpose="x",
        )
        ledger.register(
            name="rule-b",
            owner="t",
            model_type="heuristic",
            tier="medium",
            purpose="x",
        )
        ledger.link_dependency("signal-x", "model-a", actor="test")
        ledger.link_dependency("model-a", "rule-b", actor="test")
        deps = ledger.dependencies("model-a", direction="both")
        assert len(deps) == 2


class TestInventoryAt:
    def test_returns_models_created_before_date(self, ledger):
        ledger.register(
            name="early",
            owner="t",
            model_type="ml",
            tier="h",
            purpose="x",
        )
        snaps = ledger.history("early")
        early_time = snaps[0].timestamp

        result = ledger.inventory_at(early_time + timedelta(seconds=1))
        assert len(result) == 1
        assert result[0].name == "early"

    def test_excludes_models_created_after_date(self, ledger):
        ledger.register(
            name="early",
            owner="t",
            model_type="ml",
            tier="h",
            purpose="x",
        )
        # inventory_at far future should include it
        result_now = ledger.inventory_at(datetime(2099, 1, 1, tzinfo=timezone.utc))
        assert any(m.name == "early" for m in result_now)

    def test_excludes_not_found_models(self, ledger):
        model = ledger.register(
            name="gone",
            owner="t",
            model_type="ml",
            tier="h",
            purpose="x",
        )
        ledger.record(
            model,
            event="not_found",
            source="ml_platform",
            payload={},
            actor="scanner:ml_platform",
        )
        result = ledger.inventory_at(
            datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        assert not any(m.name == "gone" for m in result)

    def test_not_found_then_rediscovered(self, ledger):
        model = ledger.register(
            name="back",
            owner="t",
            model_type="ml",
            tier="h",
            purpose="x",
        )
        ledger.record(
            model,
            event="not_found",
            source="ml_platform",
            payload={},
            actor="scanner:ml_platform",
        )
        ledger.record(
            model,
            event="scan_confirmed",
            source="ml_platform",
            payload={},
            actor="scanner:ml_platform",
        )
        result = ledger.inventory_at(
            datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        assert any(m.name == "back" for m in result)


class TestCompositeMembers:
    def test_add_member_creates_snapshot_and_link(self, ledger):
        ledger.register(
            name="scoring-model",
            owner="risk-team",
            model_type="ml_model",
            tier="high",
            purpose="Score risk",
        )
        ledger.register_group(
            name="risk-pipeline",
            owner="risk-team",
            model_type="composite",
            tier="high",
            purpose="End-to-end risk scoring",
            members=[],
            actor="test",
        )
        snap = ledger.add_member("risk-pipeline", "scoring-model", role="scorer", actor="test")
        assert snap.event_type == "member_added"
        assert snap.payload["member_name"] == "scoring-model"
        assert snap.payload["role"] == "scorer"
        assert any(m.name == "scoring-model" for m in ledger.members("risk-pipeline"))

    def test_add_member_without_role(self, ledger):
        ledger.register(
            name="etl-job",
            owner="data-team",
            model_type="pipeline",
            tier="low",
            purpose="Extract data",
        )
        ledger.register_group(
            name="detection-rule",
            owner="risk-team",
            model_type="composite",
            tier="medium",
            purpose="Detect anomalies",
            members=[],
            actor="test",
        )
        snap = ledger.add_member("detection-rule", "etl-job", actor="test")
        assert snap.event_type == "member_added"
        assert "role" not in snap.payload

    def test_remove_member_creates_snapshot(self, ledger):
        ledger.register(
            name="old-model",
            owner="risk-team",
            model_type="ml_model",
            tier="high",
            purpose="Legacy scorer",
        )
        ledger.register_group(
            name="risk-pipeline",
            owner="risk-team",
            model_type="composite",
            tier="high",
            purpose="End-to-end risk scoring",
            members=["old-model"],
            actor="test",
        )
        snap = ledger.remove_member(
            "risk-pipeline",
            "old-model",
            reason="Replaced by new version",
            actor="test",
        )
        assert snap.event_type == "member_removed"
        assert snap.payload["member_name"] == "old-model"
        assert snap.payload["reason"] == "Replaced by new version"

    def test_members_excludes_removed(self, ledger):
        ledger.register(
            name="model-a",
            owner="t",
            model_type="ml",
            tier="h",
            purpose="x",
        )
        ledger.register(
            name="model-b",
            owner="t",
            model_type="ml",
            tier="h",
            purpose="x",
        )
        ledger.register_group(
            name="pipeline",
            owner="t",
            model_type="composite",
            tier="h",
            purpose="x",
            members=["model-a", "model-b"],
            actor="test",
        )
        ledger.remove_member("pipeline", "model-a", actor="test")
        current = ledger.members("pipeline")
        names = [m.name for m in current]
        assert "model-a" not in names
        assert "model-b" in names

    def test_members_re_add_after_remove(self, ledger):
        ledger.register(
            name="model-a",
            owner="t",
            model_type="ml",
            tier="h",
            purpose="x",
        )
        ledger.register_group(
            name="pipeline",
            owner="t",
            model_type="composite",
            tier="h",
            purpose="x",
            members=["model-a"],
            actor="test",
        )
        ledger.remove_member("pipeline", "model-a", actor="test")
        ledger.add_member("pipeline", "model-a", actor="test")
        current = ledger.members("pipeline")
        assert any(m.name == "model-a" for m in current)

    def test_membership_at_before_removal(self, ledger):
        ledger.register(
            name="model-a",
            owner="t",
            model_type="ml",
            tier="h",
            purpose="x",
        )
        ledger.register_group(
            name="pipeline",
            owner="t",
            model_type="composite",
            tier="h",
            purpose="x",
            members=[],
            actor="test",
        )
        ledger.add_member("pipeline", "model-a", actor="test")
        # Get the timestamp of the add event
        history = ledger.history("pipeline")
        add_events = [s for s in history if s.event_type == "member_added"]
        add_time = add_events[0].timestamp

        ledger.remove_member("pipeline", "model-a", actor="test")

        # Before removal: model-a should be present (query at exact add timestamp)
        members_before = ledger.membership_at("pipeline", add_time)
        assert any(m.name == "model-a" for m in members_before)

        # After removal: model-a should be gone
        members_after = ledger.membership_at(
            "pipeline",
            datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        assert not any(m.name == "model-a" for m in members_after)

    def test_membership_at_empty_group(self, ledger):
        ledger.register_group(
            name="empty-group",
            owner="t",
            model_type="composite",
            tier="h",
            purpose="x",
            members=[],
            actor="test",
        )
        result = ledger.membership_at(
            "empty-group",
            datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        assert result == []

    def test_membership_at_with_register_group_members(self, ledger):
        """membership_at should include members added via register_group()."""
        ledger.register(
            name="model-x",
            owner="t",
            model_type="ml",
            tier="h",
            purpose="x",
        )
        ledger.register_group(
            name="group-rg",
            owner="t",
            model_type="composite",
            tier="h",
            purpose="x",
            members=["model-x"],
            actor="test",
        )
        result = ledger.membership_at(
            "group-rg",
            datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        assert any(m.name == "model-x" for m in result)


class TestMemberChangedPropagation:
    def test_record_on_member_propagates_to_composite(self, ledger):
        ledger.register(
            name="scoring-model",
            owner="t",
            model_type="ml",
            tier="h",
            purpose="x",
        )
        ledger.register_group(
            name="risk-pipeline",
            owner="t",
            model_type="composite",
            tier="h",
            purpose="x",
            members=[],
            actor="test",
        )
        ledger.add_member("risk-pipeline", "scoring-model", actor="test")

        ledger.record(
            "scoring-model",
            event="retrained",
            payload={"accuracy": 0.95},
            actor="ml-platform",
        )

        history = ledger.history("risk-pipeline")
        changed = [s for s in history if s.event_type == "member_changed"]
        assert len(changed) == 1
        assert changed[0].payload["member_name"] == "scoring-model"
        assert changed[0].payload["original_event_type"] == "retrained"

    def test_propagation_does_not_recurse(self, ledger):
        """member_changed on a composite should NOT propagate further."""
        ledger.register(
            name="model-a",
            owner="t",
            model_type="ml",
            tier="h",
            purpose="x",
        )
        ledger.register_group(
            name="inner-composite",
            owner="t",
            model_type="composite",
            tier="h",
            purpose="x",
            members=[],
            actor="test",
        )
        ledger.add_member("inner-composite", "model-a", actor="test")
        ledger.register_group(
            name="outer-composite",
            owner="t",
            model_type="composite",
            tier="h",
            purpose="x",
            members=[],
            actor="test",
        )
        ledger.add_member("outer-composite", "inner-composite", actor="test")

        ledger.record(
            "model-a",
            event="retrained",
            payload={"accuracy": 0.9},
            actor="test",
        )

        # inner-composite should get member_changed
        inner_history = ledger.history("inner-composite")
        inner_changed = [s for s in inner_history if s.event_type == "member_changed"]
        assert len(inner_changed) == 1

        # outer-composite should NOT get member_changed (no recursion)
        outer_history = ledger.history("outer-composite")
        outer_changed = [s for s in outer_history if s.event_type == "member_changed"]
        assert len(outer_changed) == 0

    def test_no_propagation_when_no_groups(self, ledger):
        """Models without parent groups should not cause errors."""
        ledger.register(
            name="standalone",
            owner="t",
            model_type="ml",
            tier="h",
            purpose="x",
        )
        snap = ledger.record(
            "standalone",
            event="validated",
            payload={"result": "passed"},
            actor="test",
        )
        assert snap.event_type == "validated"

    def test_governance_events_do_not_propagate(self, ledger):
        """Observations/validations on a composite should not propagate to grandparents."""
        ledger.register_group(
            name="inner",
            owner="t",
            model_type="composite",
            tier="h",
            purpose="x",
            members=[],
            actor="test",
        )
        ledger.register_group(
            name="outer",
            owner="t",
            model_type="composite",
            tier="h",
            purpose="x",
            members=[],
            actor="test",
        )
        ledger.add_member("outer", "inner", actor="test")

        ledger.record_observation(
            "inner",
            observation_id="OBS-1",
            observation="Something",
            status="open",
            actor="test",
        )
        ledger.record_validation("inner", result="passed", actor="test")

        outer_history = ledger.history("outer")
        changed = [s for s in outer_history if s.event_type == "member_changed"]
        assert len(changed) == 0

    def test_no_propagation_after_member_removed(self, ledger):
        ledger.register(
            name="model-x",
            owner="t",
            model_type="ml",
            tier="h",
            purpose="x",
        )
        ledger.register_group(
            name="comp",
            owner="t",
            model_type="composite",
            tier="h",
            purpose="x",
            members=[],
            actor="test",
        )
        ledger.add_member("comp", "model-x", actor="test")
        ledger.remove_member("comp", "model-x", actor="test")

        # Record a domain event on the removed member
        ledger.record("model-x", event="retrained", payload={}, actor="test")

        comp_history = ledger.history("comp")
        changed_after_removal = [s for s in comp_history if s.event_type == "member_changed"]
        assert len(changed_after_removal) == 0


class TestGovernanceMethods:
    @pytest.fixture
    def composite(self, ledger):
        return ledger.register_group(
            name="risk-pipeline",
            owner="risk-team",
            model_type="composite",
            tier="high",
            purpose="End-to-end risk scoring",
            members=[],
            actor="test",
        )

    def test_record_observation(self, ledger, composite):
        snap = ledger.record_observation(
            "risk-pipeline",
            observation_id="OBS-001",
            observation="Feature drift detected in scoring input",
            status="open",
            severity="P2",
            actor="validation-team",
            metadata={"pillar": "Input Data Validation"},
        )
        assert snap.event_type == "observation_issued"
        assert snap.payload["observation_id"] == "OBS-001"
        assert snap.payload["observation"] == "Feature drift detected in scoring input"
        assert snap.payload["status"] == "open"
        assert snap.payload["severity"] == "P2"
        assert snap.payload["pillar"] == "Input Data Validation"

    def test_record_observation_without_severity(self, ledger, composite):
        snap = ledger.record_observation(
            "risk-pipeline",
            observation_id="OBS-002",
            observation="Documentation outdated",
            status="open",
            actor="test",
        )
        assert "severity" not in snap.payload

    def test_resolve_observation(self, ledger, composite):
        ledger.record_observation(
            "risk-pipeline",
            observation_id="OBS-001",
            observation="Feature drift detected",
            status="open",
            actor="test",
        )
        snap = ledger.resolve_observation(
            "risk-pipeline",
            observation_id="OBS-001",
            resolution="Retrained model with updated features",
            actor="model-owner",
        )
        assert snap.event_type == "observation_resolved"
        assert snap.payload["observation_id"] == "OBS-001"
        assert snap.payload["resolution"] == "Retrained model with updated features"

    def test_record_validation(self, ledger, composite):
        snap = ledger.record_validation(
            "risk-pipeline",
            result="conditional",
            actor="validation-team",
            metadata={
                "report_url": "https://example.com/report",
                "observation_count": 3,
            },
        )
        assert snap.event_type == "validated"
        assert snap.payload["result"] == "conditional"
        assert snap.payload["report_url"] == "https://example.com/report"
        assert snap.payload["observation_count"] == 3


class TestCompositeSummary:
    def test_summary_returns_all_composites(self, ledger):
        ledger.register_group(
            name="pipeline-a",
            owner="team-a",
            model_type="composite",
            tier="high",
            purpose="Pipeline A",
            members=[],
            actor="test",
        )
        ledger.register_group(
            name="pipeline-b",
            owner="team-b",
            model_type="composite",
            tier="medium",
            purpose="Pipeline B",
            members=[],
            actor="test",
        )
        ledger.register(
            name="standalone-model",
            owner="t",
            model_type="ml_model",
            tier="low",
            purpose="x",
        )
        summary = ledger.composite_summary()
        names = [s["name"] for s in summary]
        assert "pipeline-a" in names
        assert "pipeline-b" in names
        assert "standalone-model" not in names

    def test_summary_includes_member_count(self, ledger):
        ledger.register(
            name="model-a",
            owner="t",
            model_type="ml",
            tier="h",
            purpose="x",
        )
        ledger.register(
            name="model-b",
            owner="t",
            model_type="ml",
            tier="h",
            purpose="x",
        )
        ledger.register_group(
            name="pipeline",
            owner="t",
            model_type="composite",
            tier="h",
            purpose="x",
            members=[],
            actor="test",
        )
        ledger.add_member("pipeline", "model-a", actor="test")
        ledger.add_member("pipeline", "model-b", actor="test")
        summary = ledger.composite_summary()
        pipeline = next(s for s in summary if s["name"] == "pipeline")
        assert pipeline["member_count"] == 2

    def test_summary_includes_last_validated(self, ledger):
        ledger.register_group(
            name="pipeline",
            owner="t",
            model_type="composite",
            tier="h",
            purpose="x",
            members=[],
            actor="test",
        )
        ledger.record_validation("pipeline", result="passed", actor="test")
        summary = ledger.composite_summary()
        pipeline = next(s for s in summary if s["name"] == "pipeline")
        assert pipeline["last_validated"] is not None

    def test_summary_includes_open_observation_count(self, ledger):
        ledger.register_group(
            name="pipeline",
            owner="t",
            model_type="composite",
            tier="h",
            purpose="x",
            members=[],
            actor="test",
        )
        ledger.record_observation(
            "pipeline",
            observation_id="OBS-1",
            observation="Issue one",
            status="open",
            actor="test",
        )
        ledger.record_observation(
            "pipeline",
            observation_id="OBS-2",
            observation="Issue two",
            status="open",
            actor="test",
        )
        ledger.resolve_observation(
            "pipeline",
            observation_id="OBS-1",
            resolution="Fixed",
            actor="test",
        )
        summary = ledger.composite_summary()
        pipeline = next(s for s in summary if s["name"] == "pipeline")
        assert pipeline["open_observation_count"] == 1

    def test_summary_no_composites(self, ledger):
        summary = ledger.composite_summary()
        assert summary == []

    def test_composite_summary_default_filters_composite_type(self, ledger):
        """Default behavior: only model_type='composite' returned."""
        ledger.register_group(
            name="Group A",
            owner="team-a",
            model_type="composite",
            tier="high",
            purpose="test",
            members=[],
            actor="t",
        )
        ledger.register_group(
            name="Group B",
            owner="team-b",
            model_type="ml_model",
            tier="high",
            purpose="test",
            members=[],
            actor="t",
        )
        summary = ledger.composite_summary()
        names = {row["name"] for row in summary}
        assert "Group A" in names
        assert "Group B" not in names

    def test_composite_summary_custom_model_types(self, ledger):
        """Passing model_types includes matching types."""
        ledger.register_group(
            name="Group A",
            owner="team-a",
            model_type="composite",
            tier="high",
            purpose="test",
            members=[],
            actor="t",
        )
        ledger.register_group(
            name="Group B",
            owner="team-b",
            model_type="ml_model",
            tier="high",
            purpose="test",
            members=[],
            actor="t",
        )
        ledger.register_group(
            name="Group C",
            owner="team-c",
            model_type="heuristic",
            tier="high",
            purpose="test",
            members=[],
            actor="t",
        )
        summary = ledger.composite_summary(model_types=["ml_model", "heuristic"])
        names = {row["name"] for row in summary}
        assert "Group A" not in names
        assert "Group B" in names
        assert "Group C" in names


class TestInvestigateComposite:
    def test_investigate_composite_includes_governance(self, ledger):
        from model_ledger.tools.investigate import investigate
        from model_ledger.tools.schemas import InvestigateInput

        ledger.register(
            name="model-a",
            owner="t",
            model_type="ml",
            tier="h",
            purpose="x",
        )
        ledger.register_group(
            name="pipeline",
            owner="risk-team",
            model_type="composite",
            tier="high",
            purpose="Risk scoring",
            members=[],
            actor="test",
        )
        ledger.add_member("pipeline", "model-a", actor="test")
        ledger.record_observation(
            "pipeline",
            observation_id="OBS-1",
            observation="Drift detected",
            status="open",
            severity="P2",
            actor="test",
        )
        ledger.record_validation(
            "pipeline",
            result="conditional",
            actor="test",
        )

        result = investigate(InvestigateInput(model_name="pipeline"), ledger)
        assert result.last_validated is not None
        assert result.open_observation_count == 1
