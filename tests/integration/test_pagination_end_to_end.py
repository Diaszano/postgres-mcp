"""Real pagination against disposable PostgreSQL; never accepts a database URI."""

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import pytest
import pytest_asyncio
from psycopg import sql

from postgres_mcp import server
from postgres_mcp.application.query_service import QueryExecutionService
from postgres_mcp.database_config import parse_database_config
from postgres_mcp.pagination.cursors import InMemoryCursorStore
from postgres_mcp.pagination.service import PaginationService
from postgres_mcp.security.errors import PublicToolError
from postgres_mcp.sql.database_catalog import DatabaseCatalog
from postgres_mcp.sql.database_registry import DatabaseRegistry

pytestmark = pytest.mark.asyncio
DATABASES = ("app_development", "app_testing")
QUERY = "SELECT id, label FROM pagination_e2e_items ORDER BY id"


@dataclass
class PaginationEnv:
    pg: Any
    registry: DatabaseRegistry
    store: InMemoryCursorStore
    service: PaginationService
    now: list[float]

    def assert_idle(self):
        assert all(self.registry.active_leases(name) == 0 for name in DATABASES)


@pytest_asyncio.fixture
async def pagination_env(multidb_postgres, monkeypatch):
    config = parse_database_config(
        {
            "DATABASE_URI": multidb_postgres.mcp_bootstrap_uri,
            "DATABASE_AUTO_DISCOVER": "true",
            "DATABASE_DEFAULT_DATABASE": "app_development",
            "DATABASE_POOL_MAX_SIZE": "1",
        },
        None,
        None,
    )
    registry = DatabaseRegistry(config, DatabaseCatalog(config))
    await registry.start()
    monkeypatch.setattr(server, "database_config", config)
    monkeypatch.setattr(server, "registry", registry)
    monkeypatch.setattr(server, "current_access_mode", server.AccessMode.RESTRICTED)
    now = [1000.0]
    store = InMemoryCursorStore(clock=lambda: now[0], ttl_seconds=300)
    service = PaginationService(QueryExecutionService(server.get_sql_driver, 2_097_152), store, 2_097_152)
    try:
        for name in DATABASES:
            with multidb_postgres.admin(name) as conn:
                conn.execute("CREATE TABLE pagination_e2e_items (id int PRIMARY KEY, label text NOT NULL)")
                conn.execute("INSERT INTO pagination_e2e_items SELECT id, %s FROM generate_series(250, 1, -1) AS id", (name,))
                conn.execute(sql.SQL("GRANT SELECT ON pagination_e2e_items TO {}").format(sql.Identifier(multidb_postgres.mcp_role)))
        yield PaginationEnv(multidb_postgres, registry, store, service, now)
    finally:
        await registry.close_all()
        for name in DATABASES:
            with multidb_postgres.admin(name) as conn:
                conn.execute("DROP TABLE IF EXISTS pagination_e2e_items")


@pytest.mark.parametrize("mode", ["offset", "keyset"])
async def test_static_fixture_offset_and_keyset(pagination_env, mode):
    env = pagination_env
    page = await env.service.first_page(QUERY, "app_testing", 500, 15, 100, mode, "alice")
    pages = [page]
    env.assert_idle()
    while page.next_cursor:
        page = await env.service.next_page(page.next_cursor, None, "alice")
        pages.append(page)
        env.assert_idle()
    ids = [row["id"] for page in pages for row in page.rows]
    assert ids == list(range(1, 251))
    assert len(set(ids)) == 250
    assert [page.returned_rows for page in pages] == [100, 100, 50]
    assert [page.total_returned_rows for page in pages] == [100, 200, 250]
    assert all(row["label"] == "app_testing" for page in pages for row in page.rows)
    assert page.has_more is False
    assert page.truncated is False
    assert page.limit_reached is None
    assert page.next_cursor is None
    assert page.expires_in_seconds == 0
    assert all(json.loads(page.to_text())["consistency"] == "best_effort" for page in pages)


@pytest.mark.parametrize("mode", ["offset", "keyset"])
async def test_midstream_insertion_documents_best_effort(pagination_env, mode):
    env = pagination_env
    first = await env.service.first_page(QUERY, "app_testing", 500, 15, 100, mode, None)
    assert first.next_cursor is not None
    with env.pg.admin("app_testing") as conn:
        conn.execute("INSERT INTO pagination_e2e_items VALUES (0, 'inserted before boundary'), (251, 'inserted after boundary')")
    page = first
    ids = [row["id"] for row in first.rows]
    while page.next_cursor:
        page = await env.service.next_page(page.next_cursor, None, None)
        ids.extend(row["id"] for row in page.rows)
        env.assert_idle()
    # Independent statements see the new tail; offset also repeats the shifted boundary.
    expected = list(range(1, 101)) + list(range(100 if mode == "offset" else 101, 252))
    assert ids == expected
    assert 0 not in ids
    assert ids[-1] == 251
    assert ids.count(100) == (2 if mode == "offset" else 1)
    assert page.consistency == "best_effort"


async def test_cursor_expiry_restart_and_replay(pagination_env):
    env = pagination_env
    first = await env.service.first_page(QUERY, "app_testing", 500, 15, 100, "keyset", "alice")
    token = first.next_cursor
    assert token is not None
    second = await env.service.next_page(token, None, "alice")
    assert second.rows[0]["id"] == 101
    with pytest.raises(PublicToolError) as replay:
        await env.service.next_page(token, None, "alice")
    assert replay.value.code == "CURSOR_INVALID"
    assert second.next_cursor is not None
    restarted = PaginationService(QueryExecutionService(server.get_sql_driver, 2_097_152), InMemoryCursorStore(), 2_097_152)
    with pytest.raises(PublicToolError) as lost:
        await restarted.next_page(second.next_cursor, None, "alice")
    assert lost.value.code == "CURSOR_INVALID"
    env.now[0] += 300
    with pytest.raises(PublicToolError) as expired:
        await env.service.next_page(second.next_cursor, None, "alice")
    assert expired.value.code == "CURSOR_EXPIRED"
    env.assert_idle()


@pytest.mark.parametrize("mode", ["offset", "keyset"])
async def test_cross_database_parallel_continuations(pagination_env, mode):
    env = pagination_env
    pages = await asyncio.gather(*(env.service.first_page(QUERY, name, 500, 15, 100, mode, "alice") for name in DATABASES))
    rows = [page.rows[:] for page in pages]
    env.assert_idle()
    while any(page.next_cursor for page in pages):
        assert all(page.next_cursor is not None for page in pages)
        pages = await asyncio.gather(*(env.service.next_page(page.next_cursor, None, "alice") for page in pages))
        for collected, page in zip(rows, pages, strict=True):
            collected.extend(page.rows)
        env.assert_idle()
    for name, collected, page in zip(DATABASES, rows, pages, strict=True):
        assert [row["id"] for row in collected] == list(range(1, 251))
        assert {row["label"] for row in collected} == {name}
        assert page.database == name


@pytest.mark.parametrize("mode", ["offset", "keyset"])
async def test_truncated_total_budget(pagination_env, mode):
    env = pagination_env
    page = await env.service.first_page(QUERY, "app_testing", 150, 15, 100, mode, None)
    assert page.next_cursor is not None
    final = await env.service.next_page(page.next_cursor, None, None)
    assert [row["id"] for row in page.rows + final.rows] == list(range(1, 151))
    result = json.loads(final.to_text())
    assert result["total_returned_rows"] == result["max_rows"] == 150
    assert result["returned_rows"] == 50
    assert result["truncated"] is True
    assert result["has_more"] is False
    assert result["limit_reached"] == "max_rows"
    assert result["next_cursor"] is None
    env.assert_idle()


async def test_failed_continuation_preserves_unconsumed_cursor(pagination_env):
    env = pagination_env
    first = await env.service.first_page(QUERY, "app_testing", 500, 1, 100, "keyset", "alice")
    assert first.next_cursor is not None
    with env.pg.admin("app_testing") as blocker:
        blocker.execute("BEGIN")
        blocker.execute("LOCK TABLE pagination_e2e_items IN ACCESS EXCLUSIVE MODE")
        try:
            with pytest.raises(PublicToolError) as timeout:
                await env.service.next_page(first.next_cursor, None, "alice")
            assert timeout.value.code == "QUERY_TIMEOUT"
            env.assert_idle()
        finally:
            blocker.execute("ROLLBACK")
    resumed = await env.service.next_page(first.next_cursor, None, "alice")
    assert [row["id"] for row in resumed.rows] == list(range(101, 201))
    assert resumed.total_returned_rows == 200
    with pytest.raises(PublicToolError) as replay:
        await env.service.next_page(first.next_cursor, None, "alice")
    assert replay.value.code == "CURSOR_INVALID"
    env.assert_idle()
