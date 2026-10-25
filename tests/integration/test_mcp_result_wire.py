import json
from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session

from postgres_mcp.mcp_response import error_result
from postgres_mcp.mcp_response import format_mcp_result
from postgres_mcp.mcp_response import success_result
from postgres_mcp.security.errors import PublicToolError


@pytest.mark.asyncio
async def test_tool_error_is_error_on_wire():
    server = FastMCP("test-wire-server")

    @server.tool()
    async def sample_fail():
        return error_result(
            PublicToolError("POOL_CAPACITY_EXCEEDED", "The database connection pool is at capacity.", retryable=True),
            request_id="trace-abc",
        )

    async with create_connected_server_and_client_session(server._mcp_server) as client:
        res = await client.call_tool("sample_fail", {})
        assert res.isError is True
        assert res.structuredContent is not None
        assert res.structuredContent["error"]["code"] == "POOL_CAPACITY_EXCEEDED"
        assert res.structuredContent["error"]["retryable"] is True
        assert res.structuredContent["error"]["request_id"] == "trace-abc"
        assert len(res.content) >= 1
        assert "The database connection pool is at capacity." in res.content[0].text


@pytest.mark.asyncio
async def test_structured_success_has_text_fallback():
    server = FastMCP("test-wire-server-success")

    @server.tool()
    async def sample_success():
        return success_result({"database": "app_db", "total": 42})

    async with create_connected_server_and_client_session(server._mcp_server) as client:
        res = await client.call_tool("sample_success", {})
        assert res.isError is False
        assert res.structuredContent == {"database": "app_db", "total": 42}
        assert len(res.content) == 1
        text_payload = json.loads(res.content[0].text)
        assert text_payload == {"database": "app_db", "total": 42}


@pytest.mark.asyncio
async def test_unexpected_exception_is_sanitized():
    server = FastMCP("test-wire-server-error")

    @server.tool()
    async def sample_throw():
        try:
            raise RuntimeError("Database connection password=supersecret failed")
        except Exception as exc:
            return format_mcp_result(exc)

    async with create_connected_server_and_client_session(server._mcp_server) as client:
        res = await client.call_tool("sample_throw", {})
        assert res.isError is True
        assert res.structuredContent["error"]["code"] == "INTERNAL_ERROR"
        assert "supersecret" not in res.content[0].text
        assert "supersecret" not in str(res.structuredContent)


def test_sdk_compatibility_pinned():
    lock_file = Path(__file__).parents[2] / "uv.lock"
    assert lock_file.exists(), "uv.lock must exist"
    lock_text = lock_file.read_text(encoding="utf-8")
    assert 'name = "mcp"' in lock_text
    assert 'name = "fastmcp"' not in lock_text or 'name = "mcp"' in lock_text
