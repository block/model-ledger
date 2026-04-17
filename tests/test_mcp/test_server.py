"""Tests for the MCP server — tool and resource registration."""

from __future__ import annotations

import asyncio

import pytest

try:
    from mcp.server.fastmcp import FastMCP

    HAS_MCP = True
except ImportError:
    HAS_MCP = False

pytestmark = pytest.mark.skipif(not HAS_MCP, reason="mcp extra not installed")


@pytest.fixture
def server():
    from model_ledger.mcp.server import create_server

    return create_server(demo=False)


@pytest.fixture
def server_demo():
    from model_ledger.mcp.server import create_server

    return create_server(demo=True)


class TestCreateServer:
    """create_server() returns a properly configured FastMCP instance."""

    def test_returns_fastmcp_instance(self, server):
        assert isinstance(server, FastMCP)

    def test_server_name(self, server):
        assert server.name == "model-ledger"


class TestToolRegistration:
    """All tools are registered."""

    EXPECTED_TOOLS = {
        "discover",
        "record",
        "investigate",
        "query",
        "trace",
        "changelog",
        "tag",
        "list_tags",
    }

    def test_all_tools_registered(self, server):
        tools = asyncio.run(server.list_tools())
        tool_names = {t.name for t in tools}
        assert tool_names >= self.EXPECTED_TOOLS

    def test_expected_tool_count(self, server):
        tools = asyncio.run(server.list_tools())
        assert len(tools) == len(self.EXPECTED_TOOLS)

    def test_each_tool_has_description(self, server):
        tools = asyncio.run(server.list_tools())
        for tool in tools:
            assert tool.description, f"Tool {tool.name} has no description"


class TestResourceRegistration:
    """All 3 resources are registered."""

    EXPECTED_URIS = {
        "ledger://overview",
        "ledger://schema",
        "ledger://backends",
    }

    def test_all_resources_registered(self, server):
        resources = asyncio.run(server.list_resources())
        uris = {str(r.uri) for r in resources}
        assert uris >= self.EXPECTED_URIS

    def test_exactly_three_resources(self, server):
        resources = asyncio.run(server.list_resources())
        assert len(resources) == 3


class TestToolExecution:
    """Smoke-test that tools can be called (returns dict, not Pydantic)."""

    def test_record_tool_creates_model(self, server):
        result = asyncio.run(
            server.call_tool(
                "record",
                {
                    "model_name": "credit-scorecard",
                    "event": "registered",
                    "actor": "test",
                    "owner": "risk-team",
                    "model_type": "ml_model",
                },
            )
        )
        # call_tool returns list of content items; check first one has text
        assert len(result) > 0

    def test_query_tool_returns_results(self, server):
        # First register a model
        asyncio.run(
            server.call_tool(
                "record",
                {
                    "model_name": "fraud-detector",
                    "event": "registered",
                    "owner": "risk-team",
                    "model_type": "ml_model",
                },
            )
        )
        result = asyncio.run(server.call_tool("query", {}))
        assert len(result) > 0

    def test_tag_tool_creates_tag(self, server):
        asyncio.run(
            server.call_tool(
                "record",
                {
                    "model_name": "credit-scorecard",
                    "event": "registered",
                    "owner": "risk-team",
                    "model_type": "ml_model",
                },
            )
        )
        result = asyncio.run(
            server.call_tool(
                "tag",
                {"model_name": "credit-scorecard", "tag_name": "v1.0"},
            )
        )
        assert len(result) > 0

    def test_list_tags_tool_returns_tags(self, server):
        asyncio.run(
            server.call_tool(
                "record",
                {
                    "model_name": "credit-scorecard",
                    "event": "registered",
                    "owner": "risk-team",
                    "model_type": "ml_model",
                },
            )
        )
        asyncio.run(
            server.call_tool(
                "tag",
                {"model_name": "credit-scorecard", "tag_name": "v1.0"},
            )
        )
        result = asyncio.run(
            server.call_tool("list_tags", {"model_name": "credit-scorecard"}),
        )
        assert len(result) > 0


class TestResourceReading:
    """Smoke-test that resources can be read."""

    def test_overview_resource(self, server):
        result = asyncio.run(server.read_resource("ledger://overview"))
        # Returns bytes or str
        assert result is not None

    def test_schema_resource(self, server):
        result = asyncio.run(server.read_resource("ledger://schema"))
        assert result is not None

    def test_backends_resource(self, server):
        result = asyncio.run(server.read_resource("ledger://backends"))
        assert result is not None


class TestCustomBackend:
    """create_server accepts a custom backend."""

    def test_with_explicit_backend(self):
        from model_ledger.backends.ledger_memory import InMemoryLedgerBackend
        from model_ledger.mcp.server import create_server

        backend = InMemoryLedgerBackend()
        srv = create_server(backend=backend, demo=False)
        assert isinstance(srv, FastMCP)


class TestMainEntryPoint:
    """main() function exists and is importable."""

    def test_main_is_callable(self):
        from model_ledger.mcp.server import main

        assert callable(main)
