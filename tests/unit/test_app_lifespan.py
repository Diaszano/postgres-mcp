from unittest.mock import AsyncMock

import pytest

from postgres_mcp.app import create_mcp_app
from postgres_mcp.runtime import AppRuntime


@pytest.mark.asyncio
async def test_two_app_instances_are_isolated():
    rt1 = AppRuntime(access_mode="restricted")
    rt2 = AppRuntime(access_mode="unrestricted")

    app1 = create_mcp_app(rt1)
    app2 = create_mcp_app(rt2)

    assert app1 is not app2
    assert rt1.access_mode != rt2.access_mode
    assert rt1.cursor_store is not rt2.cursor_store
    assert rt1.db_connection is not rt2.db_connection


@pytest.mark.asyncio
async def test_signal_and_shutdown_close_once():
    rt = AppRuntime()
    mock_reg = AsyncMock()
    rt.registry = mock_reg
    mock_pool = AsyncMock()
    rt.db_connection = mock_pool

    await rt.close()
    assert rt.shutdown_in_progress is True
    mock_reg.close.assert_awaited_once()
    mock_pool.close.assert_awaited_once()

    # Second call is idempotent
    await rt.close()
    mock_reg.close.assert_awaited_once()
    mock_pool.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_tools_resolve_runtime_from_context():
    rt = AppRuntime(access_mode="restricted")
    app = create_mcp_app(rt)
    assert app is not None


def test_stdio_sse_http_startup_unchanged():
    from postgres_mcp.security.transport import HttpAuthConfig
    from postgres_mcp.security.transport import validate_http_deployment

    auth = HttpAuthConfig(token="a" * 32, allowed_hosts=("localhost",), allowed_origins=("https://localhost",))
    validate_http_deployment("streamable-http", "127.0.0.1", auth)
    validate_http_deployment("stdio", "localhost", HttpAuthConfig())
