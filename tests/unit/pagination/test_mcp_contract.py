import inspect
import json
import sys
import time
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken
from mcp.server.fastmcp.tools import Tool

import postgres_mcp.server as server
from postgres_mcp.pagination.cursors import InMemoryCursorStore
from postgres_mcp.query_limits.config import QueryBudgetConfig
from postgres_mcp.query_limits.results import BoundedQueryResult
from postgres_mcp.security.errors import to_public_error
from postgres_mcp.sql import SqlDriver


@pytest.fixture
def paging(monkeypatch):
    monkeypatch.setattr(server, "query_budget_config", QueryBudgetConfig(enabled=True))
    monkeypatch.setattr(server, "pagination_enabled", True, raising=False)
    monkeypatch.setattr(server, "pagination_default_page_size", 100, raising=False)
    monkeypatch.setattr(server, "pagination_max_page_size", 1000, raising=False)
    monkeypatch.setattr(server, "cursor_store", InMemoryCursorStore(), raising=False)
    errors = []
    original = server.format_exception_response

    def capture(operation, error):
        errors.append(to_public_error(error).code)
        return original(operation, error)

    monkeypatch.setattr(server, "format_exception_response", capture)
    driver = AsyncMock(spec=SqlDriver)

    async def execute(query, **kwargs):
        return [SqlDriver.RowResult({"verified": True} if "pg_catalog" in str(query) else {"id": 1})]

    driver.execute_query.side_effect = execute

    async def bounded(query, *, params, max_rows, timeout_seconds, **kwargs):
        limit, offset = params
        rows = [{"id": i} for i in range(offset + 1, min(offset + limit + 1, 301))]
        return BoundedQueryResult(rows, len(rows), False, None, 1, timeout_seconds)

    driver.execute_bounded_query.side_effect = bounded

    @asynccontextmanager
    async def get_driver(database=None):
        assert database in (None, "app")
        yield driver

    monkeypatch.setattr(server, "get_sql_driver", get_driver)
    return driver, errors


@pytest.mark.asyncio
async def test_legacy_call_is_not_paginated(monkeypatch, paging):
    driver, errors = paging
    monkeypatch.setattr(server, "query_budget_config", QueryBudgetConfig())
    response = await server.execute_sql("SELECT id FROM users", "app")
    assert response[0].text == "[{'id': 1}]"
    driver.execute_query.assert_awaited_once_with("SELECT id FROM users")
    driver.execute_bounded_query.assert_not_called()
    assert not errors
    parameters = inspect.signature(server.execute_sql).parameters
    assert list(parameters) == ["sql", "database", "max_rows", "timeout_seconds", "page_size", "pagination"]
    assert parameters["sql"].default.default == "all"
    assert parameters["pagination"].default == "none"
    assert "fetch_query_page" in {tool.name for tool in server.mcp._tool_manager.list_tools()}


@pytest.mark.asyncio
async def test_page_size_without_mode_is_invalid(paging):
    driver, errors = paging
    await server.execute_sql("SELECT id FROM users", page_size=100)
    assert errors == ["INVALID_QUERY_OPTIONS"]
    driver.execute_query.assert_not_called()
    driver.execute_bounded_query.assert_not_called()


def test_fetch_page_accepts_only_cursor_and_page_size():
    tool = next(tool for tool in server.mcp._tool_manager.list_tools() if tool.name == "fetch_query_page")
    assert set(tool.parameters["properties"]) == {"cursor", "page_size"}
    assert tool.parameters["required"] == ["cursor"]
    assert tool.parameters["properties"]["page_size"]["default"] is None
    assert tool.annotations.readOnlyHint is True
    assert list(inspect.signature(server.fetch_query_page).parameters) == ["cursor", "page_size"]


async def startup(monkeypatch, env):
    monkeypatch.setattr(sys, "argv", ["postgres_mcp"])
    for key in list(server.os.environ):
        if key.startswith("DATABASE_"):
            monkeypatch.delenv(key)
    for key, value in {"DATABASE_URI": "postgresql://u:p@localhost/app", **env}.items():
        monkeypatch.setenv(key, value)
    for name in (
        "database_config",
        "registry",
        "current_access_mode",
        "query_budget_config",
        "query_admission",
        "pagination_enabled",
        "pagination_default_page_size",
        "pagination_max_page_size",
        "cursor_store",
    ):
        if hasattr(server, name):
            monkeypatch.setattr(server, name, getattr(server, name))
    monkeypatch.setattr(server.mcp._tool_manager, "_tools", dict(server.mcp._tool_manager._tools))
    with patch.object(server.db_connection, "pool_connect", AsyncMock()), patch.object(server.mcp, "run_stdio_async", AsyncMock()):
        await server.main()


@pytest.mark.asyncio
async def test_paging_disabled_rejected(monkeypatch, paging):
    driver, errors = paging
    await startup(monkeypatch, {"DATABASE_PAGINATION_ENABLED": "false"})
    await server.execute_sql("SELECT id FROM users ORDER BY id", pagination="offset")
    await server.fetch_query_page("unknown")
    assert errors == ["INVALID_QUERY_OPTIONS", "INVALID_QUERY_OPTIONS"]
    driver.execute_bounded_query.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("guardrails_enabled", [False, True])
async def test_success_metadata_and_text(monkeypatch, paging, guardrails_enabled):
    monkeypatch.setattr(server, "query_budget_config", QueryBudgetConfig(enabled=guardrails_enabled))
    response = await server.execute_sql("SELECT id FROM users ORDER BY id", "app", max_rows=250, page_size=100, pagination="offset")
    payload = json.loads(response[0].text)
    assert response[0].type == "text"
    assert payload["rows"] == [{"id": i} for i in range(1, 101)]
    assert {
        key: payload[key] for key in ("returned_rows", "total_returned_rows", "max_rows", "page_size", "truncated", "has_more", "expires_in_seconds")
    } == {
        "returned_rows": 100,
        "total_returned_rows": 100,
        "max_rows": 250,
        "page_size": 100,
        "truncated": True,
        "has_more": True,
        "expires_in_seconds": 300,
    }
    assert payload["next_cursor"]
    second = json.loads((await server.fetch_query_page(payload["next_cursor"], 100))[0].text)
    assert second["total_returned_rows"] == 200
    assert second["next_cursor"] != payload["next_cursor"]
    final = json.loads((await server.fetch_query_page(second["next_cursor"]))[0].text)
    assert final["total_returned_rows"] == 250
    assert final["returned_rows"] == 50
    assert final["has_more"] is False
    assert final["next_cursor"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "options,code",
    [
        ({"pagination": "cursor"}, "INVALID_QUERY_OPTIONS"),
        ({"page_size": True}, "INVALID_QUERY_OPTIONS"),
        ({"page_size": 0}, "INVALID_QUERY_OPTIONS"),
        ({"page_size": 1001}, "LIMIT_EXCEEDED"),
    ],
)
async def test_invalid_options_rejected_before_checkout(paging, options, code):
    driver, errors = paging
    await server.execute_sql("SELECT id FROM users ORDER BY id", **{"pagination": "offset", **options})
    assert errors == [code]
    driver.execute_bounded_query.assert_not_called()


@pytest.mark.asyncio
async def test_continuation_principal_and_page_cap(paging):
    _, errors = paging
    alice = AuthenticatedUser(AccessToken(token="secret", client_id="configured-http-client", scopes=[]))
    context = auth_context_var.set(alice)
    try:
        first = json.loads((await server.execute_sql("SELECT id FROM users ORDER BY id", pagination="offset"))[0].text)
        await server.fetch_query_page(first["next_cursor"], 1001)
        assert errors[-1] == "LIMIT_EXCEEDED"
        auth_context_var.set(AuthenticatedUser(AccessToken(token="other-secret", client_id="configured-http-client", scopes=[])))
        await server.fetch_query_page(first["next_cursor"])
        assert errors[-1] == "CURSOR_INVALID"
        auth_context_var.set(None)
        await server.fetch_query_page(first["next_cursor"])
        assert errors[-1] == "CURSOR_INVALID"
        auth_context_var.set(alice)
        assert json.loads((await server.fetch_query_page(first["next_cursor"]))[0].text)["total_returned_rows"] == 200
    finally:
        auth_context_var.reset(context)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "env",
    [
        {"DATABASE_PAGINATION_ENABLED": "maybe"},
        {"DATABASE_PAGINATION_DEFAULT_PAGE_SIZE": "0"},
        {"DATABASE_PAGINATION_MAX_PAGE_SIZE": "-1"},
        {"DATABASE_PAGINATION_CURSOR_TTL_SECONDS": "1.5"},
        {"DATABASE_PAGINATION_MAX_ACTIVE_CURSORS": "true"},
        {"DATABASE_PAGINATION_DEFAULT_PAGE_SIZE": "101", "DATABASE_PAGINATION_MAX_PAGE_SIZE": "100"},
    ],
)
async def test_invalid_pagination_config_fails_startup(monkeypatch, env):
    with pytest.raises(SystemExit) as error:
        await startup(monkeypatch, env)
    assert error.value.code == 2


@pytest.mark.asyncio
async def test_configured_defaults_caps_expiry_and_capacity(monkeypatch, paging):
    _, errors = paging
    await startup(
        monkeypatch,
        {
            "DATABASE_QUERY_GUARDRAILS_ENABLED": "true",
            "DATABASE_PAGINATION_DEFAULT_PAGE_SIZE": "2",
            "DATABASE_PAGINATION_MAX_PAGE_SIZE": "3",
            "DATABASE_PAGINATION_CURSOR_TTL_SECONDS": "17",
            "DATABASE_PAGINATION_MAX_ACTIVE_CURSORS": "1",
        },
    )
    sql = "SELECT id FROM users ORDER BY id"
    first = json.loads((await server.execute_sql(sql, pagination="offset"))[0].text)
    assert first["page_size"] == 2
    assert first["expires_in_seconds"] == 17
    second = json.loads((await server.execute_sql(sql, pagination="offset"))[0].text)
    await server.fetch_query_page(first["next_cursor"])
    assert errors[-1] == "CURSOR_INVALID"
    await server.fetch_query_page(second["next_cursor"], 4)
    assert errors[-1] == "LIMIT_EXCEEDED"
    assert json.loads((await server.fetch_query_page(second["next_cursor"], 3))[0].text)["returned_rows"] == 3
    expiring = json.loads((await server.execute_sql(sql, pagination="offset"))[0].text)
    monkeypatch.setattr(server.cursor_store, "_clock", lambda: time.monotonic() + 18)
    await server.fetch_query_page(expiring["next_cursor"])
    assert errors[-1] == "CURSOR_EXPIRED"
    assert not Tool.from_function(server.execute_sql).parameters.get("required")
