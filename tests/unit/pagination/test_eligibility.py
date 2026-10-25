from unittest.mock import AsyncMock

import pytest

from postgres_mcp.pagination.eligibility import inspect_pageable_select
from postgres_mcp.security.errors import SQLValidationError
from postgres_mcp.sql import SafeSqlDriver
from postgres_mcp.sql import SqlDriver


async def inspect(sql, driver, mode="keyset"):
    return await inspect_pageable_select(sql, mode, driver)


def catalog_driver(verified=True):
    driver = AsyncMock(spec=SqlDriver)
    driver.execute_query.return_value = [SqlDriver.RowResult(cells={"verified": verified})]
    return driver


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sql,verified",
    [
        ("SELECT id FROM users", True),
        ("SELECT id FROM users ORDER BY id", False),
        ("SELECT nullable_key FROM users ORDER BY nullable_key", False),
    ],
)
async def test_rejects_missing_unstable_order(sql, verified):
    with pytest.raises(SQLValidationError):
        await inspect(sql, catalog_driver(verified))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sql",
    [
        "SELECT id FROM users ORDER BY id",
        "SELECT u.id, u.name FROM public.users AS u WHERE u.id > 1 ORDER BY u.id ASC",
        'SELECT "ID" FROM "odd schema"."Users" ORDER BY "ID"',
    ],
)
async def test_keyset_accepts_only_simple_unique_ascending_column(sql):
    result = await inspect(sql, catalog_driver())
    assert result.key_column in {"id", "ID"}
    assert result.sql


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sql",
    [
        "WITH gone AS (DELETE FROM users RETURNING *) SELECT id FROM users ORDER BY id",
        "SELECT id FROM users ORDER BY id; SELECT 1",
        "SELECT id FROM users ORDER BY id FOR UPDATE",
        "SELECT id FROM users ORDER BY id LIMIT 10",
        "SELECT id FROM users ORDER BY id OFFSET 2",
        "SELECT DISTINCT id FROM users ORDER BY id",
        "SELECT id FROM users UNION SELECT id FROM admins ORDER BY id",
        "SELECT u.id FROM users u JOIN admins a ON a.id = u.id ORDER BY u.id",
        "SELECT id FROM users ORDER BY id DESC",
        "SELECT id FROM users ORDER BY id, name",
        "SELECT id FROM users ORDER BY lower(name)",
        "SELECT count(*) FROM users ORDER BY id",
        "SELECT id FROM users WHERE EXISTS (SELECT 1) ORDER BY id",
        "SELECT id FROM users WHERE random() > 0 ORDER BY id",
        "SELECT id AS other FROM users ORDER BY id",
        "SELECT name FROM users ORDER BY id",
        "SELECT * FROM users ORDER BY 1",
    ],
)
async def test_unsafe_ast_fails_closed(sql):
    driver = catalog_driver()
    with pytest.raises(SQLValidationError):
        await inspect(sql, driver)
    driver.execute_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_database_catalog_scoped():
    authorized = catalog_driver()
    unauthorized = catalog_driver(False)
    await inspect("SELECT id FROM private.users ORDER BY id", authorized)
    authorized.execute_query.assert_awaited_once()
    with pytest.raises(SQLValidationError):
        await inspect("SELECT id FROM private.users ORDER BY id", unauthorized)
    unauthorized.execute_query.assert_awaited_once()
    query = authorized.execute_query.call_args.args[0]
    assert "pg_catalog.pg_index" in query
    assert "private" in query
    assert "users" in query
    assert "id" in query
    assert authorized.execute_query.call_args.kwargs["force_readonly"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("verified", [False, None, "true", 1])
async def test_requires_positive_catalog_proof(verified):
    with pytest.raises(SQLValidationError):
        await inspect("SELECT id FROM users ORDER BY id", catalog_driver(verified))


@pytest.mark.asyncio
async def test_safe_driver_keeps_restricted_validation():
    raw = catalog_driver()
    result = await inspect("SELECT id FROM users ORDER BY id", SafeSqlDriver(raw))
    assert result.key_column == "id"
    assert raw.execute_query.call_args.kwargs["force_readonly"] is True


@pytest.mark.asyncio
async def test_offset_requires_same_proven_total_order():
    assert (await inspect("SELECT id FROM users ORDER BY id", catalog_driver(), "offset")).key_column == "id"
    with pytest.raises(SQLValidationError):
        await inspect("SELECT id FROM users ORDER BY id", catalog_driver(False), "offset")
    with pytest.raises(SQLValidationError):
        await inspect("SELECT id FROM users ORDER BY id", catalog_driver(), "other")
