import pytest
import pytest_asyncio
from psycopg import sql

import postgres_mcp.server as server
from postgres_mcp.application.query_service import QueryExecutionService
from postgres_mcp.database_config import parse_database_config
from postgres_mcp.pagination.cursors import InMemoryCursorStore
from postgres_mcp.pagination.service import PaginationService
from postgres_mcp.security.errors import PublicToolError
from postgres_mcp.sql.database_catalog import DatabaseCatalog
from postgres_mcp.sql.database_registry import DatabaseRegistry


@pytest_asyncio.fixture
async def pagination(multidb_postgres, monkeypatch):
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
    catalog = DatabaseCatalog(config)
    registry = DatabaseRegistry(config, catalog)
    await registry.start()
    monkeypatch.setattr(server, "database_config", config)
    monkeypatch.setattr(server, "registry", registry)
    monkeypatch.setattr(server, "current_access_mode", server.AccessMode.RESTRICTED)
    with multidb_postgres.admin("app_testing") as conn:
        conn.execute("CREATE TABLE pagination_security_items (id int PRIMARY KEY, label text)")
        conn.execute("INSERT INTO pagination_security_items SELECT id, '; -- $1 %s 50%' FROM generate_series(1, 300) AS id")
        conn.execute(sql.SQL("GRANT SELECT ON pagination_security_items TO {}").format(sql.Identifier(multidb_postgres.mcp_role)))
    store = InMemoryCursorStore()
    service = PaginationService(QueryExecutionService(server.get_sql_driver, 2_097_152), store, 2_097_152)
    try:
        yield service, store, registry, catalog
    finally:
        await registry.close_all()
        with multidb_postgres.admin() as conn:
            conn.execute(sql.SQL("GRANT CONNECT ON DATABASE app_testing TO {}").format(sql.Identifier(multidb_postgres.mcp_role)))
        with multidb_postgres.admin("app_testing") as conn:
            conn.execute("DROP TABLE pagination_security_items")


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["offset", "keyset"])
async def test_no_connection_held_between_pages(pagination, mode):
    service, store, registry, _ = pagination
    page = await service.first_page("SELECT id FROM pagination_security_items ORDER BY id", "app_testing", 250, 15, 100, mode, "alice")
    rows = page.rows[:]
    consumed = page.next_cursor
    assert consumed is not None
    assert registry.active_leases("app_testing") == 0
    while page.next_cursor:
        consumed = page.next_cursor
        page = await service.next_page(consumed, None, "alice")
        rows.extend(page.rows)
        assert registry.active_leases("app_testing") == 0
    assert [row["id"] for row in rows] == list(range(1, 251))
    assert page.total_returned_rows == 250
    assert page.has_more is False
    assert page.truncated is True
    assert page.limit_reached == "max_rows"
    with pytest.raises(PublicToolError) as error:
        store.reserve(consumed, "alice")
    assert error.value.code == "CURSOR_INVALID"


@pytest.mark.asyncio
async def test_resume_rechecks_authorization(pagination, multidb_postgres):
    service, store, registry, catalog = pagination
    page = await service.first_page("SELECT id FROM pagination_security_items ORDER BY id", "app_testing", 250, 15, 100, "offset", "alice")
    assert page.next_cursor is not None
    with multidb_postgres.admin() as conn:
        conn.execute(sql.SQL("REVOKE CONNECT ON DATABASE app_testing FROM {}").format(sql.Identifier(multidb_postgres.mcp_role)))
    await catalog.names(refresh=True)
    with pytest.raises(PublicToolError) as error:
        await service.next_page(page.next_cursor, None, "alice")
    assert error.value.code == "DATABASE_NOT_ALLOWED"
    reservation = store.reserve(page.next_cursor, "alice")
    assert reservation.state.database == "app_testing"
    assert reservation.state.total_returned_rows == 100
    store.release_on_error(reservation)
    assert registry.active_leases("app_testing") == 0
    assert registry.active_leases("app_development") == 0


@pytest.mark.asyncio
async def test_bound_keyset_value_and_literal_percent(pagination, multidb_postgres):
    service, _, registry, _ = pagination
    marker = "'; DROP TABLE pagination_security_items; -- $1 %s"
    with multidb_postgres.admin("app_testing") as conn:
        conn.execute("CREATE TABLE pagination_security_keys (id text PRIMARY KEY)")
        conn.execute("INSERT INTO pagination_security_keys VALUES (%s), (%s)", (marker, "z"))
        conn.execute(sql.SQL("GRANT SELECT ON pagination_security_keys TO {}").format(sql.Identifier(multidb_postgres.mcp_role)))
    try:
        page = await service.first_page("SELECT id FROM pagination_security_keys ORDER BY id", "app_testing", 10, 15, 1, "keyset", None)
        assert page.rows == [{"id": marker}]
        assert page.next_cursor is not None
        page = await service.next_page(page.next_cursor, None, None)
        assert page.rows == [{"id": "z"}]
        assert page.has_more is False
        page = await service.first_page(
            "SELECT id FROM pagination_security_items WHERE label = '; -- $1 %s 50%' ORDER BY id",
            "app_testing",
            10,
            15,
            2,
            "keyset",
            None,
        )
        assert page.rows == [{"id": 1}, {"id": 2}]
        assert registry.active_leases("app_testing") == 0
    finally:
        with multidb_postgres.admin("app_testing") as conn:
            conn.execute("DROP TABLE pagination_security_keys")
