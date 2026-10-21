from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from postgres_mcp.database_config import DatabaseConfig
from postgres_mcp.sql import database_catalog
from postgres_mcp.sql.database_catalog import DatabaseCatalog
from postgres_mcp.sql.database_catalog import discover_postgres_databases

URI = "postgresql://dev:s3cret@localhost:5432/postgres"


def make_config(**overrides) -> DatabaseConfig:
    values = dict(
        bootstrap_uri=URI,
        auto_discover=True,
        default_database="App_Test",
        allowed_databases=(),
        excluded_databases=(),
        discovery_ttl_seconds=60,
        max_pools=8,
        pool_max_size=5,
        pool_idle_seconds=600,
        access_mode="restricted",
    )
    values.update(overrides)
    return DatabaseConfig(**values)


def fake_clock() -> float:
    return 0.0


@pytest.mark.asyncio
async def test_discovery_sql_uses_pg_catalog_and_connect_privilege():
    cursor = MagicMock()
    cursor.fetchall = AsyncMock(return_value=[("App_Test",), ("postgres",)])
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=cursor)
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    connect = AsyncMock(return_value=conn)
    with patch.object(database_catalog.AsyncConnection, "connect", connect):
        result = await discover_postgres_databases(URI)

    assert result == {"App_Test", "postgres"}
    connect.assert_awaited_once()
    assert connect.await_args.args[0] == URI
    sql = conn.execute.await_args.args[0]
    assert "pg_catalog.pg_database" in sql
    assert "datallowconn" in sql
    assert "NOT datistemplate" in sql
    assert "has_database_privilege(oid, 'CONNECT')" in sql
    conn.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_connection_closed_after_exception():
    conn = MagicMock()
    conn.execute = AsyncMock(side_effect=RuntimeError("boom"))
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    with patch.object(database_catalog.AsyncConnection, "connect", AsyncMock(return_value=conn)):
        with pytest.raises(RuntimeError):
            await discover_postgres_databases(URI)
    conn.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_allowed_intersect_discovered():
    cfg = make_config(allowed_databases=("App_Test", "missing"))
    catalog = DatabaseCatalog(cfg, discover=AsyncMock(return_value={"postgres", "App_Test", "other"}), clock=fake_clock)
    assert await catalog.names(refresh=True) == (["App_Test"], False)


@pytest.mark.asyncio
async def test_denylist_wins():
    cfg = make_config(allowed_databases=("App_Test", "postgres"), excluded_databases=("postgres",))
    catalog = DatabaseCatalog(cfg, discover=AsyncMock(return_value={"postgres", "App_Test", "blocked_db"}), clock=fake_clock)
    assert (await catalog.names(refresh=True))[0] == ["App_Test"]


@pytest.mark.asyncio
async def test_case_is_preserved():
    cfg = make_config(allowed_databases=("App_Test",), excluded_databases=("postgres",))
    catalog = DatabaseCatalog(cfg, discover=AsyncMock(return_value={"postgres", "App_Test", "blocked_db"}), clock=fake_clock)
    assert (await catalog.names(refresh=True))[0] == ["App_Test"]
    assert await catalog.authorize("App_Test") == "App_Test"
    with pytest.raises(ValueError):
        await catalog.authorize("app_test")


@pytest.mark.asyncio
async def test_unknown_and_denied_rejected_before_pool():
    cfg = make_config(excluded_databases=("postgres",))
    catalog = DatabaseCatalog(cfg, discover=AsyncMock(return_value={"postgres", "App_Test"}), clock=fake_clock)
    for bad in ("postgres", "nope", "App_Test; DROP DATABASE x"):
        with pytest.raises(ValueError) as exc:
            await catalog.authorize(bad)
        message = str(exc.value)
        assert bad in message
        assert "s3cret" not in message
        assert "localhost" not in message


@pytest.mark.asyncio
async def test_legacy_exposes_only_bootstrap_database():
    cfg = make_config(auto_discover=False, default_database="postgres")
    discover = AsyncMock(return_value={"postgres", "other"})
    catalog = DatabaseCatalog(cfg, discover=discover, clock=fake_clock)
    assert await catalog.names(refresh=True) == (["postgres"], False)
    assert await catalog.authorize("postgres") == "postgres"
    with pytest.raises(ValueError):
        await catalog.authorize("other")
    discover.assert_not_awaited()
