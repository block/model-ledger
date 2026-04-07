"""Tests for model group methods."""
import pytest
from model_ledger import Ledger
from model_ledger.graph.models import DataNode


@pytest.fixture
def ledger():
    ledger = Ledger()
    ledger.add([
        DataNode("etl_job_checks", platform="etl_engine", outputs=["alerts"]),
        DataNode("alerting_checks", platform="alerting", inputs=["alerts"], outputs=["queue"]),
        DataNode("queue:checks", platform="case_mgmt", inputs=["queue"]),
    ])
    ledger.connect()
    return ledger


class TestRegisterGroup:
    def test_creates_model_ref(self, ledger):
        group = ledger.register_group(
            name="Remote Check Deposit", owner="TEAM", model_type="heuristic",
            tier="high", purpose="Cash check deposit TM",
            members=["etl_job_checks", "alerting_checks", "queue:checks"], actor="vignesh",
        )
        assert group.name == "Remote Check Deposit"
        assert group.owner == "TEAM"
        assert group.model_type == "heuristic"
        assert group.tier == "high"

    def test_links_members(self, ledger):
        ledger.register_group(
            name="Remote Check Deposit", owner="TEAM", model_type="heuristic",
            tier="high", purpose="Cash check deposit TM",
            members=["etl_job_checks", "alerting_checks"], actor="vignesh",
        )
        deps = ledger.dependencies("Remote Check Deposit", direction="upstream")
        upstream_names = [d["model"].name for d in deps]
        assert "etl_job_checks" in upstream_names
        assert "alerting_checks" in upstream_names

    def test_relationship_is_member_of(self, ledger):
        ledger.register_group(
            name="Remote Check Deposit", owner="TEAM", model_type="heuristic",
            tier="high", purpose="Cash check deposit TM",
            members=["etl_job_checks"], actor="vignesh",
        )
        deps = ledger.dependencies("Remote Check Deposit", direction="upstream")
        assert deps[0]["relationship"] == "member_of"

    def test_empty_members(self, ledger):
        group = ledger.register_group(
            name="Empty Group", owner="test", model_type="heuristic",
            tier="low", purpose="test", members=[], actor="test",
        )
        assert group.name == "Empty Group"
        assert ledger.members("Empty Group") == []

    def test_trace_includes_group(self, ledger):
        ledger.register_group(
            name="Remote Check Deposit", owner="TEAM", model_type="heuristic",
            tier="high", purpose="Cash check deposit TM",
            members=["etl_job_checks", "alerting_checks", "queue:checks"], actor="vignesh",
        )
        trace = ledger.trace("Remote Check Deposit")
        assert trace[0] == "etl_job_checks"
        assert trace[-1] == "Remote Check Deposit"


class TestMembers:
    def test_returns_member_models(self, ledger):
        ledger.register_group(
            name="Remote Check Deposit", owner="TEAM", model_type="heuristic",
            tier="high", purpose="Cash check deposit TM",
            members=["etl_job_checks", "alerting_checks"], actor="vignesh",
        )
        members = ledger.members("Remote Check Deposit")
        member_names = [m.name for m in members]
        assert "etl_job_checks" in member_names
        assert "alerting_checks" in member_names

    def test_non_group_returns_empty(self, ledger):
        assert ledger.members("etl_job_checks") == []


class TestGroups:
    def test_returns_parent_groups(self, ledger):
        ledger.register_group(
            name="Remote Check Deposit", owner="TEAM", model_type="heuristic",
            tier="high", purpose="Cash check deposit TM",
            members=["etl_job_checks"], actor="vignesh",
        )
        parent_groups = ledger.groups("etl_job_checks")
        group_names = [g.name for g in parent_groups]
        assert "Remote Check Deposit" in group_names

    def test_model_in_no_group(self, ledger):
        assert ledger.groups("etl_job_checks") == []

    def test_model_in_multiple_groups(self, ledger):
        ledger.register_group(
            name="Group A", owner="t", model_type="heuristic",
            tier="low", purpose="test", members=["etl_job_checks"], actor="t",
        )
        ledger.register_group(
            name="Group B", owner="t", model_type="heuristic",
            tier="low", purpose="test", members=["etl_job_checks"], actor="t",
        )
        parent_groups = ledger.groups("etl_job_checks")
        group_names = [g.name for g in parent_groups]
        assert "Group A" in group_names
        assert "Group B" in group_names
