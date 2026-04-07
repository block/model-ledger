# tests/test_connectors/test_rest_connector.py
"""Tests for rest_connector factory."""
import json
from unittest.mock import MagicMock, patch
from model_ledger.connectors.rest import rest_connector
from model_ledger.graph.protocol import SourceConnector


def _mock_response(data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status.return_value = None
    return resp


def test_returns_source_connector():
    with patch("model_ledger.connectors.rest.httpx") as mock_httpx:
        mock_httpx.get.return_value = _mock_response({"items": []})
        c = rest_connector(name="test", url="http://test/api",
                          items_path="items", name_field="name")
        assert isinstance(c, SourceConnector)
        assert c.name == "test"


def test_simple_discovery():
    with patch("model_ledger.connectors.rest.httpx") as mock_httpx:
        mock_httpx.get.return_value = _mock_response({
            "models": [
                {"name": "fraud_v3", "owner": "alice", "version": "3"},
                {"name": "risk_v1", "owner": "bob", "version": "1"},
            ]
        })
        c = rest_connector(name="mlflow", url="http://mlflow/api",
                          items_path="models", name_field="name")
        nodes = c.discover()
        assert len(nodes) == 2
        assert nodes[0].name == "fraud_v3"
        assert nodes[0].platform == "mlflow"
        assert nodes[0].metadata["owner"] == "alice"


def test_nested_items_path():
    with patch("model_ledger.connectors.rest.httpx") as mock_httpx:
        mock_httpx.get.return_value = _mock_response({
            "response": {"data": {"models": [{"name": "m1"}]}}
        })
        c = rest_connector(name="test", url="http://test/api",
                          items_path="response.data.models", name_field="name")
        nodes = c.discover()
        assert len(nodes) == 1
        assert nodes[0].name == "m1"


def test_headers_passed():
    with patch("model_ledger.connectors.rest.httpx") as mock_httpx:
        mock_httpx.get.return_value = _mock_response({"items": []})
        c = rest_connector(name="test", url="http://test/api",
                          items_path="items", name_field="name",
                          headers={"Authorization": "Bearer token123"})
        c.discover()
        call_kwargs = mock_httpx.get.call_args
        assert call_kwargs.kwargs["headers"]["Authorization"] == "Bearer token123"


def test_explicit_metadata_fields():
    with patch("model_ledger.connectors.rest.httpx") as mock_httpx:
        mock_httpx.get.return_value = _mock_response({
            "items": [{"name": "m1", "owner": "alice", "junk": "ignored"}]
        })
        c = rest_connector(name="test", url="http://test/api",
                          items_path="items", name_field="name",
                          metadata_fields={"owner": "owner"})
        nodes = c.discover()
        assert nodes[0].metadata["owner"] == "alice"
        assert "junk" not in nodes[0].metadata


def test_empty_result():
    with patch("model_ledger.connectors.rest.httpx") as mock_httpx:
        mock_httpx.get.return_value = _mock_response({"items": []})
        c = rest_connector(name="test", url="http://test/api",
                          items_path="items", name_field="name")
        assert c.discover() == []


def test_pagination_token():
    with patch("model_ledger.connectors.rest.httpx") as mock_httpx:
        mock_httpx.get.side_effect = [
            _mock_response({"items": [{"name": "m1"}], "next_token": "page2"}),
            _mock_response({"items": [{"name": "m2"}]}),
        ]
        c = rest_connector(name="test", url="http://test/api",
                          items_path="items", name_field="name",
                          pagination={"type": "token", "token_field": "next_token", "param": "page_token"})
        nodes = c.discover()
        assert len(nodes) == 2
        assert nodes[0].name == "m1"
        assert nodes[1].name == "m2"
