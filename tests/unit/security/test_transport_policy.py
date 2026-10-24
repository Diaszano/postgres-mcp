import asyncio
import socket
import sys
from contextlib import nullcontext
from unittest.mock import AsyncMock
from unittest.mock import patch

import httpx
import pytest
import uvicorn
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent
from starlette.testclient import TestClient


@pytest.fixture(autouse=True)
def clear_http_env(monkeypatch):
    for key in ("MCP_HTTP_AUTH_TOKEN", "MCP_HTTP_ALLOWED_HOSTS", "MCP_HTTP_ALLOWED_ORIGINS"):
        monkeypatch.delenv(key, raising=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("transport", ["sse", "streamable-http"])
async def test_default_http_bind_is_loopback(monkeypatch, transport):
    from postgres_mcp import server

    monkeypatch.setattr(sys, "argv", ["postgres_mcp", "postgresql://localhost/db", f"--transport={transport}"])
    runner = "run_sse_async" if transport == "sse" else "run_streamable_http_async"
    with patch.object(server.db_connection, "pool_connect", AsyncMock()), patch.object(server.mcp, runner, AsyncMock()) as run:
        await server.main()
    run.assert_awaited_once()
    assert server.mcp.settings.host == "localhost"
    assert server.mcp.settings.transport_security is not None
    assert server.mcp.settings.transport_security.enable_dns_rebinding_protection


@pytest.mark.asyncio
@pytest.mark.parametrize("transport", ["sse", "streamable-http"])
async def test_public_bind_without_auth_policy_rejected(monkeypatch, transport):
    from postgres_mcp import server

    monkeypatch.setattr(sys, "argv", ["postgres_mcp", "postgresql://localhost/db", f"--transport={transport}", f"--{transport}-host=0.0.0.0"])
    with (
        patch.object(server.db_connection, "pool_connect", AsyncMock()) as connect,
        patch.object(server.mcp, "run_sse_async", AsyncMock()) as sse,
        patch.object(server.mcp, "run_streamable_http_async", AsyncMock()) as http,
        pytest.raises(SystemExit) as error,
    ):
        await server.main()
    assert error.value.code == 2
    connect.assert_not_awaited()
    sse.assert_not_awaited()
    http.assert_not_awaited()


@pytest.mark.asyncio
async def test_stdio_unaffected(monkeypatch):
    from postgres_mcp import server

    monkeypatch.setenv("MCP_HTTP_AUTH_TOKEN", "invalid")
    monkeypatch.setattr(sys, "argv", ["postgres_mcp", "postgresql://localhost/db"])
    with patch.object(server.db_connection, "pool_connect", AsyncMock()), patch.object(server.mcp, "run_stdio_async", AsyncMock()) as run:
        await server.main()
    run.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("transport", ["sse", "streamable-http"])
async def test_public_bind_uses_authenticated_runner(monkeypatch, transport, auth_env):
    from postgres_mcp import server

    for key, value in auth_env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(sys, "argv", ["postgres_mcp", "postgresql://localhost/db", f"--transport={transport}", f"--{transport}-host=0.0.0.0"])
    with (
        patch.object(server.db_connection, "pool_connect", AsyncMock()),
        patch.object(server, "run_authenticated_http", AsyncMock()) as run,
        patch.object(server.mcp, "run_sse_async", AsyncMock()) as sse,
        patch.object(server.mcp, "run_streamable_http_async", AsyncMock()) as http,
    ):
        await server.main()
    assert server.mcp.settings.host == "0.0.0.0"
    run.assert_awaited_once()
    assert run.await_args is not None
    assert run.await_args.args[0] is server.mcp
    assert run.await_args.args[1] == transport
    sse.assert_not_awaited()
    http.assert_not_awaited()


@pytest.fixture
def auth_env():
    return {
        "MCP_HTTP_AUTH_TOKEN": "test-bearer-token-with-at-least-32-characters",
        "MCP_HTTP_ALLOWED_HOSTS": "mcp.example.test",
        "MCP_HTTP_ALLOWED_ORIGINS": "https://client.example.test",
    }


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.0.2.1", "example.test", "127.0.0.1.example.test", "", "localhost."])
def test_non_loopback_requires_auth(host):
    from postgres_mcp.security.transport import HttpAuthConfig
    from postgres_mcp.security.transport import validate_http_deployment

    with pytest.raises(ValueError, match="Authenticated HTTP configuration is required"):
        validate_http_deployment("sse", host, HttpAuthConfig.from_env({}))


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "127.1.2.3", "::1"])
def test_loopback_allowed(host):
    from postgres_mcp.security.transport import HttpAuthConfig
    from postgres_mcp.security.transport import validate_http_deployment

    validate_http_deployment("streamable-http", host, HttpAuthConfig.from_env({}))


@pytest.mark.parametrize(
    "key,value",
    [
        ("MCP_HTTP_AUTH_TOKEN", ""),
        ("MCP_HTTP_AUTH_TOKEN", "short-secret"),
        ("MCP_HTTP_AUTH_TOKEN", " " + "secret" * 8),
        ("MCP_HTTP_AUTH_TOKEN", "secret" * 8 + "\n"),
        ("MCP_HTTP_AUTH_TOKEN", "é" * 40),
        ("MCP_HTTP_ALLOWED_HOSTS", "*"),
        ("MCP_HTTP_ALLOWED_HOSTS", "example.test:*"),
        ("MCP_HTTP_ALLOWED_HOSTS", "https://example.test"),
        ("MCP_HTTP_ALLOWED_HOSTS", "user:password@example.test"),
        ("MCP_HTTP_ALLOWED_HOSTS", "example.test:99999"),
        ("MCP_HTTP_ALLOWED_HOSTS", "example.test,"),
        ("MCP_HTTP_ALLOWED_ORIGINS", "http://example.test"),
        ("MCP_HTTP_ALLOWED_ORIGINS", "https://example.test/path"),
        ("MCP_HTTP_ALLOWED_ORIGINS", "https://example.test?secret=value"),
        ("MCP_HTTP_ALLOWED_ORIGINS", "https://user:password@example.test"),
        ("MCP_HTTP_ALLOWED_ORIGINS", "https://*.example.test"),
        ("MCP_HTTP_ALLOWED_ORIGINS", "null"),
    ],
)
def test_invalid_auth_config_is_sanitized(auth_env, key, value):
    from postgres_mcp.security.transport import HttpAuthConfig

    auth_env[key] = value
    with pytest.raises(ValueError) as error:
        HttpAuthConfig.from_env(auth_env)
    assert str(error.value) == "Invalid HTTP authentication configuration."
    if value:
        assert value not in str(error.value)


@pytest.mark.parametrize("key", ["MCP_HTTP_AUTH_TOKEN", "MCP_HTTP_ALLOWED_HOSTS", "MCP_HTTP_ALLOWED_ORIGINS"])
def test_partial_auth_config_rejected(auth_env, key):
    from postgres_mcp.security.transport import HttpAuthConfig

    del auth_env[key]
    with pytest.raises(ValueError, match="Invalid HTTP authentication configuration"):
        HttpAuthConfig.from_env(auth_env)


@pytest.mark.asyncio
@pytest.mark.parametrize("transport", ["sse", "streamable-http"])
async def test_verified_authenticated_ingress(auth_env, transport):
    """Exercise MCP 1.25.0's real middleware, context principal and transport checks."""
    from postgres_mcp.security.transport import HttpAuthConfig
    from postgres_mcp.security.transport import authenticated_http_app
    from postgres_mcp.security.transport import validate_http_deployment

    auth = HttpAuthConfig.from_env(auth_env)
    validate_http_deployment(transport, "0.0.0.0", auth)
    assert auth_env["MCP_HTTP_AUTH_TOKEN"] not in repr(auth)
    server = FastMCP("auth-spike", stateless_http=True, json_response=True)

    @server.tool()
    def principal() -> str:
        token = get_access_token()
        assert token is not None
        return token.client_id

    app = authenticated_http_app(server, transport, auth)
    path = "/mcp" if transport == "streamable-http" else "/sse"
    headers = {"Authorization": f"Bearer {auth_env['MCP_HTTP_AUTH_TOKEN']}", "Origin": "https://client.example.test"}
    lifespan = server.session_manager.run() if transport == "streamable-http" else nullcontext()
    async with (
        lifespan,
        httpx.AsyncClient(transport=httpx.ASGITransport(app, raise_app_exceptions=False), base_url="https://mcp.example.test") as client,
    ):
        assert (await client.get(path)).status_code == 401
        assert (await client.get(path, headers={"Authorization": "Bearer incorrect"})).status_code == 401
        assert (await client.get(path, headers={**headers, "Host": "attacker.example.test"})).status_code == 421
        assert (await client.get(path, headers={**headers, "Origin": "https://attacker.example.test"})).status_code == 403
        if transport == "sse":
            assert (await client.post("/messages/?session_id=missing")).status_code == 401
            # A valid SSE GET streams indefinitely; a missing message session exposes authenticated POST handling.
            assert (await client.post("/messages/?session_id=missing", headers={**headers, "Content-Type": "application/json"})).status_code == 400
        else:
            response = await client.post(
                path,
                headers={**headers, "Accept": "application/json, text/event-stream"},
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "principal", "arguments": {}}},
            )
            assert response.status_code == 200
            assert response.json()["result"]["content"][0]["text"] == "configured-http-client"
    assert get_access_token() is None


def test_authenticated_app_preserves_lifespan(auth_env):
    from postgres_mcp.security.transport import HttpAuthConfig
    from postgres_mcp.security.transport import authenticated_http_app

    server = FastMCP("lifespan-spike", stateless_http=True)
    app = authenticated_http_app(server, "streamable-http", HttpAuthConfig.from_env(auth_env))
    with TestClient(app, base_url="https://mcp.example.test") as client:
        assert client.get("/mcp").status_code == 401


@pytest.mark.asyncio
async def test_verified_sse_principal(auth_env):
    from postgres_mcp.security.transport import HttpAuthConfig
    from postgres_mcp.security.transport import authenticated_http_app

    server = FastMCP("sse-auth-spike")

    @server.tool()
    def principal() -> str:
        token = get_access_token()
        assert token is not None
        return token.client_id

    app = authenticated_http_app(server, "sse", HttpAuthConfig.from_env(auth_env))
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        runner = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False))
        task = asyncio.create_task(runner.serve(sockets=[listener]))
        try:
            async with asyncio.timeout(5):
                while not runner.started:
                    if task.done():
                        await task
                    await asyncio.sleep(0.01)
                headers = {
                    "Authorization": f"Bearer {auth_env['MCP_HTTP_AUTH_TOKEN']}",
                    "Host": "mcp.example.test",
                    "Origin": "https://client.example.test",
                }
                async with (
                    sse_client(f"http://127.0.0.1:{listener.getsockname()[1]}/sse", headers=headers) as streams,
                    ClientSession(*streams) as session,
                ):
                    await session.initialize()
                    result = await session.call_tool("principal", {})
                    assert isinstance(result.content[0], TextContent)
                    assert result.content[0].text == "configured-http-client"
        finally:
            runner.should_exit = True
            await asyncio.wait_for(task, timeout=5)
