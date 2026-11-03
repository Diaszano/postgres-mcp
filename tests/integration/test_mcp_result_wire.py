# pyright: reportPrivateUsage=false

import json
from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session

import postgres_mcp.server as app
from postgres_mcp.database_config import parse_database_config
from postgres_mcp.mcp_response import error_result
from postgres_mcp.mcp_response import format_mcp_result
from postgres_mcp.mcp_response import success_result
from postgres_mcp.security.errors import PublicToolError
from postgres_mcp.sql.database_catalog import DatabaseCatalog
from postgres_mcp.sql.database_registry import DatabaseRegistry
from tests.type_helpers import text_at


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
        assert "The database connection pool is at capacity." in text_at(res.content)


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
        text_payload = json.loads(text_at(res.content))
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
        assert res.structuredContent is not None
        assert res.structuredContent["error"]["code"] == "INTERNAL_ERROR"
        assert "supersecret" not in text_at(res.content)
        assert "supersecret" not in str(res.structuredContent)


@pytest.mark.asyncio
async def test_restricted_database_tools_work_over_mcp_wire(multidb_postgres, monkeypatch):
    config = parse_database_config(
        {
            "DATABASE_URI": multidb_postgres.mcp_bootstrap_uri,
            "DATABASE_AUTO_DISCOVER": "true",
            "DATABASE_DEFAULT_DATABASE": "app_development",
        },
        None,
        None,
    )
    registry = DatabaseRegistry(config, DatabaseCatalog(config))
    await registry.start()
    monkeypatch.setattr(app, "database_config", config)
    monkeypatch.setattr(app, "registry", registry)
    monkeypatch.setattr(app, "current_access_mode", app.AccessMode.RESTRICTED)

    wire_server = FastMCP("postgres-mcp-integration")
    wire_server.add_tool(app.list_databases)
    wire_server.add_tool(app.execute_sql)
    try:
        async with create_connected_server_and_client_session(wire_server._mcp_server) as client:
            tools = await client.list_tools()
            assert {tool.name for tool in tools.tools} == {"list_databases", "execute_sql"}

            databases = await client.call_tool("list_databases", {})
            assert databases.isError is False
            assert "app_development" in text_at(databases.content)

            select = await client.call_tool("execute_sql", {"sql": "SELECT 1 AS value"})
            assert select.isError is False
            assert select.structuredContent is not None
            assert "result" in select.structuredContent
            assert "1" in text_at(select.content)

            write = await client.call_tool(
                "execute_sql",
                {"sql": "INSERT INTO development_marker (id, label) VALUES (2, 'blocked')"},
            )
            assert write.isError is True
            assert write.structuredContent is not None, write.model_dump_json()
            assert write.structuredContent["error"]["code"] == "SQL_VALIDATION_FAILED"
            assert write.structuredContent["result"][0]["type"] == "text"
            assert multidb_postgres.mcp_password not in str(write.structuredContent)
            assert multidb_postgres.mcp_password not in str(write.content)
            with multidb_postgres.admin("app_development") as conn:
                assert conn.execute("SELECT count(*) FROM development_marker").fetchone()[0] == 1
    finally:
        await registry.close_all()


def test_sdk_compatibility_pinned():
    lock_file = Path(__file__).parents[2] / "uv.lock"
    assert lock_file.exists(), "uv.lock must exist"
    lock_text = lock_file.read_text(encoding="utf-8")
    assert 'name = "mcp"' in lock_text
    assert 'name = "fastmcp"' not in lock_text or 'name = "mcp"' in lock_text
