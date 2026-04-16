# tests/test_connectors/test_github_connector.py
"""Tests for github_connector factory."""

import base64
from unittest.mock import MagicMock, patch

from model_ledger.connectors.github import github_connector
from model_ledger.graph.models import DataNode, DataPort
from model_ledger.graph.protocol import SourceConnector


def _mock_gh_api(responses):
    """Build a side_effect function that returns different responses per URL.

    Patterns are checked longest-first so more specific paths win over
    shorter prefixes (e.g. "project_a/config.yaml" before "contents/projects").
    """

    def handler(url, **kwargs):
        resp = MagicMock()
        for pattern, data in sorted(responses.items(), key=lambda x: len(x[0]), reverse=True):
            if pattern in url:
                resp.status_code = 200
                resp.json.return_value = data
                return resp
        resp.status_code = 404
        resp.json.return_value = None
        return resp

    return handler


def _b64(content: str) -> str:
    return base64.b64encode(content.encode()).decode()


def _parser(project_name: str, content: str) -> DataNode | None:
    """Simple test parser: treat content as a comma-separated list of outputs."""
    outputs = [DataPort(t.strip()) for t in content.split(",") if t.strip()]
    return DataNode(name=project_name, platform="test", outputs=outputs)


def test_returns_source_connector():
    with patch("model_ledger.connectors.github.httpx") as mock_httpx:
        mock_httpx.get.return_value = MagicMock(status_code=200, json=lambda: [])
        c = github_connector(
            name="test",
            repos=["org/repo"],
            project_path="projects",
            config_file="config.yaml",
            parser=_parser,
        )
        assert isinstance(c, SourceConnector)
        assert c.name == "test"


def test_discovers_projects():
    with patch("model_ledger.connectors.github.httpx") as mock_httpx:
        mock_httpx.get.side_effect = _mock_gh_api(
            {
                "contents/projects": [
                    {"name": "project_a", "type": "dir"},
                    {"name": "project_b", "type": "dir"},
                    {"name": "README.md", "type": "file"},
                ],
                "project_a/config.yaml": {"content": _b64("table_a,table_b")},
                "project_b/config.yaml": {"content": _b64("table_c")},
            }
        )
        c = github_connector(
            name="pipelines",
            repos=["org/repo"],
            project_path="projects",
            config_file="config.yaml",
            parser=_parser,
        )
        nodes = c.discover()
        assert len(nodes) == 2
        assert nodes[0].name == "project_a"
        assert len(nodes[0].outputs) == 2
        assert nodes[1].name == "project_b"


def test_parser_returns_none_skips():
    def skip_parser(name, content):
        return None

    with patch("model_ledger.connectors.github.httpx") as mock_httpx:
        mock_httpx.get.side_effect = _mock_gh_api(
            {
                "contents/projects": [{"name": "proj", "type": "dir"}],
                "proj/config.yaml": {"content": _b64("data")},
            }
        )
        c = github_connector(
            name="test",
            repos=["org/repo"],
            project_path="projects",
            config_file="config.yaml",
            parser=skip_parser,
        )
        assert c.discover() == []


def test_missing_config_file_skips():
    with patch("model_ledger.connectors.github.httpx") as mock_httpx:
        mock_httpx.get.side_effect = _mock_gh_api(
            {
                "contents/projects": [{"name": "proj", "type": "dir"}],
            }
        )
        c = github_connector(
            name="test",
            repos=["org/repo"],
            project_path="projects",
            config_file="config.yaml",
            parser=_parser,
        )
        assert c.discover() == []


def test_empty_repo():
    with patch("model_ledger.connectors.github.httpx") as mock_httpx:
        mock_httpx.get.return_value = MagicMock(status_code=200, json=lambda: [])
        c = github_connector(
            name="test",
            repos=["org/repo"],
            project_path="projects",
            config_file="config.yaml",
            parser=_parser,
        )
        assert c.discover() == []


def test_auth_header():
    with patch("model_ledger.connectors.github.httpx") as mock_httpx:
        mock_httpx.get.return_value = MagicMock(status_code=200, json=lambda: [])
        c = github_connector(
            name="test",
            repos=["org/repo"],
            project_path="projects",
            config_file="config.yaml",
            parser=_parser,
            token="ghp_secret",
        )
        c.discover()
        call_kwargs = mock_httpx.get.call_args
        assert "Bearer ghp_secret" in str(call_kwargs)
