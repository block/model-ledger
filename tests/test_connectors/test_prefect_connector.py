"""Tests for prefect_connector factory."""

from unittest.mock import AsyncMock, MagicMock, patch

from model_ledger.connectors.prefect import prefect_connector
from model_ledger.graph.protocol import SourceConnector


def _make_deployment(name, tags=None, schedules=None, updated=None, entrypoint=None, version=None):
    dep = MagicMock()
    dep.name = name
    dep.tags = tags or []
    dep.schedules = schedules or []
    dep.updated = updated
    dep.entrypoint = entrypoint
    dep.version = version
    return dep


def _make_schedule(cron="0 4 * * *"):
    sched_obj = MagicMock()
    sched_obj.schedule.cron = cron
    return sched_obj


def _patch_prefect(deployments):
    """Patch get_client to return mock deployments."""
    client = AsyncMock()
    client.read_deployments = AsyncMock(side_effect=[deployments, []])
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return patch("model_ledger.connectors.prefect.get_client", return_value=client)


def test_returns_source_connector():
    with _patch_prefect([]):
        c = prefect_connector(name="test")
        assert isinstance(c, SourceConnector)
        assert c.name == "test"


def test_discovers_deployments():
    deps = [
        _make_deployment("scorer-prod", tags=["application:risk-ml", "repo:forge-risk"]),
        _make_deployment("etl-prod", tags=["application:data-eng"]),
    ]
    with _patch_prefect(deps):
        nodes = prefect_connector().discover()
    assert len(nodes) == 2
    assert nodes[0].name == "scorer-prod"
    assert nodes[0].metadata["application"] == "risk-ml"
    assert nodes[1].name == "etl-prod"


def test_deduplicates_by_name():
    deps = [
        _make_deployment("scorer-prod"),
        _make_deployment("scorer-prod"),
    ]
    with _patch_prefect(deps):
        nodes = prefect_connector().discover()
    assert len(nodes) == 1


def test_no_tag_filter_returns_all():
    deps = [
        _make_deployment("a", tags=["deploy_from:main"]),
        _make_deployment("b", tags=["deploy_from:user"]),
    ]
    with _patch_prefect(deps):
        nodes = prefect_connector(tag_filter=None).discover()
    assert len(nodes) == 2


def test_tag_filter_passed_to_api():
    client = AsyncMock()
    client.read_deployments = AsyncMock(return_value=[])
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    mock_filter = MagicMock()
    mock_tags = MagicMock()

    with (
        patch("model_ledger.connectors.prefect.get_client", return_value=client),
        patch("model_ledger.connectors.prefect.DeploymentFilter", mock_filter),
        patch("model_ledger.connectors.prefect.DeploymentFilterTags", mock_tags),
    ):
        prefect_connector(tag_filter=["deploy_from:main"]).discover()
        mock_tags.assert_called_once_with(all_=["deploy_from:main"])
        mock_filter.assert_called_once()


def test_extracts_schedule():
    deps = [_make_deployment("scheduled", schedules=[_make_schedule("0 6 * * *")])]
    with _patch_prefect(deps):
        nodes = prefect_connector().discover()
    assert nodes[0].metadata["schedule"] == "0 6 * * *"
    assert nodes[0].metadata["has_schedule"] is True


def test_no_schedule():
    deps = [_make_deployment("unscheduled", schedules=[])]
    with _patch_prefect(deps):
        nodes = prefect_connector().discover()
    assert nodes[0].metadata["schedule"] is None
    assert nodes[0].metadata["has_schedule"] is False


def test_extracts_source_updated_at():
    from datetime import datetime, timezone

    ts = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)
    deps = [_make_deployment("model", updated=ts)]
    with _patch_prefect(deps):
        nodes = prefect_connector().discover()
    assert nodes[0].metadata["source_updated_at"] == ts.isoformat()


def test_empty_result():
    with _patch_prefect([]):
        nodes = prefect_connector().discover()
    assert nodes == []
