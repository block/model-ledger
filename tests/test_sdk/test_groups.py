"""Tests for model group methods."""

import pytest

from model_ledger import Ledger
from model_ledger.graph.models import DataNode


@pytest.fixture
def ledger():
    ledger = Ledger()
    ledger.add(
        [
            DataNode("feature_pipeline", platform="etl", outputs=["scores"]),
            DataNode("scoring_model", platform="ml", inputs=["scores"], outputs=["alerts"]),
            DataNode("alert_queue", platform="alerting", inputs=["alerts"]),
        ]
    )
    ledger.connect()
    return ledger


class TestRegisterGroup:
    def test_creates_model_ref(self, ledger):
        group = ledger.register_group(
            name="Credit Scorecard",
            owner="risk-team",
            model_type="ml_model",
            tier="high",
            purpose="Credit risk scoring pipeline",
            members=["feature_pipeline", "scoring_model", "alert_queue"],
            actor="system",
        )
        assert group.name == "Credit Scorecard"
        assert group.owner == "risk-team"
        assert group.model_type == "ml_model"
        assert group.tier == "high"

    def test_links_members(self, ledger):
        ledger.register_group(
            name="Credit Scorecard",
            owner="risk-team",
            model_type="ml_model",
            tier="high",
            purpose="Credit risk scoring pipeline",
            members=["feature_pipeline", "scoring_model"],
            actor="system",
        )
        deps = ledger.dependencies("Credit Scorecard", direction="upstream")
        upstream_names = [d["model"].name for d in deps]
        assert "feature_pipeline" in upstream_names
        assert "scoring_model" in upstream_names

    def test_relationship_is_member_of(self, ledger):
        ledger.register_group(
            name="Credit Scorecard",
            owner="risk-team",
            model_type="ml_model",
            tier="high",
            purpose="Credit risk scoring pipeline",
            members=["feature_pipeline"],
            actor="system",
        )
        deps = ledger.dependencies("Credit Scorecard", direction="upstream")
        assert deps[0]["relationship"] == "member_of"

    def test_empty_members(self, ledger):
        group = ledger.register_group(
            name="Empty Group",
            owner="test",
            model_type="ml_model",
            tier="low",
            purpose="test",
            members=[],
            actor="test",
        )
        assert group.name == "Empty Group"
        assert ledger.members("Empty Group") == []

    def test_trace_includes_group(self, ledger):
        ledger.register_group(
            name="Credit Scorecard",
            owner="risk-team",
            model_type="ml_model",
            tier="high",
            purpose="Credit risk scoring pipeline",
            members=["feature_pipeline", "scoring_model", "alert_queue"],
            actor="system",
        )
        trace = ledger.trace("Credit Scorecard")
        assert trace[0] == "feature_pipeline"
        assert trace[-1] == "Credit Scorecard"


class TestMembers:
    def test_returns_member_models(self, ledger):
        ledger.register_group(
            name="Credit Scorecard",
            owner="risk-team",
            model_type="ml_model",
            tier="high",
            purpose="Credit risk scoring pipeline",
            members=["feature_pipeline", "scoring_model"],
            actor="system",
        )
        members = ledger.members("Credit Scorecard")
        member_names = [m.name for m in members]
        assert "feature_pipeline" in member_names
        assert "scoring_model" in member_names

    def test_non_group_returns_empty(self, ledger):
        assert ledger.members("feature_pipeline") == []


class TestGroups:
    def test_returns_parent_groups(self, ledger):
        ledger.register_group(
            name="Credit Scorecard",
            owner="risk-team",
            model_type="ml_model",
            tier="high",
            purpose="Credit risk scoring pipeline",
            members=["feature_pipeline"],
            actor="system",
        )
        parent_groups = ledger.groups("feature_pipeline")
        group_names = [g.name for g in parent_groups]
        assert "Credit Scorecard" in group_names

    def test_model_in_no_group(self, ledger):
        assert ledger.groups("feature_pipeline") == []

    def test_model_in_multiple_groups(self, ledger):
        ledger.register_group(
            name="Group A",
            owner="t",
            model_type="ml_model",
            tier="low",
            purpose="test",
            members=["feature_pipeline"],
            actor="t",
        )
        ledger.register_group(
            name="Group B",
            owner="t",
            model_type="ml_model",
            tier="low",
            purpose="test",
            members=["feature_pipeline"],
            actor="t",
        )
        parent_groups = ledger.groups("feature_pipeline")
        group_names = [g.name for g in parent_groups]
        assert "Group A" in group_names
        assert "Group B" in group_names
