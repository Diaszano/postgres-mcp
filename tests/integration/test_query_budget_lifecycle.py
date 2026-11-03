import asyncio
import tracemalloc
from functools import partial

import psycopg
import pytest
import pytest_asyncio
from psycopg.pq import TransactionStatus

import postgres_mcp.server as server
import postgres_mcp.sql.sql_driver as driver_module
from postgres_mcp.application.query_service import QueryExecutionService
from postgres_mcp.database_config import parse_database_config
from postgres_mcp.query_limits.admission import QueryAdmission
from postgres_mcp.query_limits.config import QueryBudgetConfig
from postgres_mcp.query_limits.policy import QueryLimits
from postgres_mcp.query_limits.results import encode_bounded_result
from postgres_mcp.security.errors import PublicToolError
from postgres_mcp.security.errors import to_public_error
from postgres_mcp.sql import SqlDriver
from postgres_mcp.sql.database_catalog import DatabaseCatalog
from postgres_mcp.sql.database_registry import DatabaseRegistry
from postgres_mcp.sql.database_registry import DatabaseUnavailableError


@pytest_asyncio.fixture
async def lifecycle(multidb_postgres, monkeypatch):
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
    monkeypatch.setattr(server, "current_access_mode", server.AccessMode.UNRESTRICTED)
    admission = QueryAdmission(1)
    service = QueryExecutionService(server.get_sql_driver, 2_097_152)
    await admission.run(lambda: service.execute("SELECT 1 AS value", None, QueryLimits(200, 15)), 15)
    async with registry.acquire(None) as pool:
        pass
    try:
        yield registry, pool, admission, service
    finally:
        await registry.close_all()


@pytest.mark.asyncio
async def test_cancellation_releases_pool_and_semaphore(lifecycle, monkeypatch):
    registry, pool, admission, service = lifecycle
    fetching = asyncio.Event()
    returning = asyncio.Event()
    release = asyncio.Event()
    original_fetch = psycopg.AsyncServerCursor.fetchmany
    original_putconn = pool.pool.putconn
    connections = []

    async def fetch(cursor, size=0):
        fetching.set()
        return await original_fetch(cursor, size)

    async def putconn(connection):
        connections.append(connection)
        returning.set()
        await release.wait()
        await original_putconn(connection)

    monkeypatch.setattr(psycopg.AsyncServerCursor, "fetchmany", fetch)
    monkeypatch.setattr(pool.pool, "putconn", putconn)
    task = asyncio.create_task(admission.run(lambda: service.execute("SELECT pg_catalog.pg_sleep(30)", None, QueryLimits(200, 60)), 60))
    try:
        await asyncio.wait_for(fetching.wait(), 5)
        task.cancel()
        await asyncio.wait_for(returning.wait(), 5)
        task.cancel()
        await asyncio.sleep(0)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert registry.active_leases("app_development") == 0
        assert pool.pool.get_stats()["pool_available"] == 1
        result = await admission.run(lambda: service.execute("SELECT 1 AS value", None, QueryLimits(200, 15)), 15)
        assert result.rows == [{"value": 1}]
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        monkeypatch.setattr(pool.pool, "putconn", original_putconn)
        if connections and pool.pool.get_stats()["pool_available"] == 0:
            await original_putconn(connections[0])


@pytest.mark.asyncio
async def test_connection_failure_is_sanitized(multidb_postgres, monkeypatch):
    secret = multidb_postgres.mcp_bootstrap_uri.replace(multidb_postgres.mcp_password, "private_password")
    config = parse_database_config(
        {"DATABASE_URI": secret, "DATABASE_AUTO_DISCOVER": "true", "DATABASE_DEFAULT_DATABASE": "app_development"}, None, None
    )

    async def discover(uri):
        return {"app_development"}

    registry = DatabaseRegistry(config, DatabaseCatalog(config, discover=discover))
    monkeypatch.setattr(driver_module, "AsyncConnectionPool", partial(driver_module.AsyncConnectionPool, timeout=0.1, reconnect_timeout=0.1))
    monkeypatch.setattr(server, "database_config", config)
    monkeypatch.setattr(server, "registry", registry)
    monkeypatch.setattr(server, "query_budget_config", QueryBudgetConfig(enabled=True))
    try:
        with pytest.raises(DatabaseUnavailableError) as error:
            await QueryExecutionService(server.get_sql_driver, 2_097_152).execute("SELECT 1", None, QueryLimits(200, 15))
        public = to_public_error(error.value)
        assert public.code == "DATABASE_UNAVAILABLE"
        response = await server.execute_sql("SELECT 1")
        assert response[0].text == "Error: The database is temporarily unavailable."
        assert all(value not in public.message + response[0].text for value in (secret, "private_password", multidb_postgres.mcp_role))
        assert registry.active_leases("app_development") == 0
    finally:
        await registry.close_all()


@pytest.mark.asyncio
async def test_guarded_read_timeout_releases_pool_and_semaphore(lifecycle):
    registry, pool, admission, service = lifecycle
    with pytest.raises(PublicToolError) as error:
        await admission.run(lambda: service.execute("SELECT pg_catalog.pg_sleep(30)", None, QueryLimits(200, 15)), 0.1)
    assert error.value.code == "QUERY_TIMEOUT"
    assert registry.active_leases("app_development") == 0
    async with pool.pool.connection() as connection:
        assert connection.info.transaction_status == TransactionStatus.IDLE
        assert (await (await connection.execute("SHOW statement_timeout")).fetchone())[0] == "0"
    result = await admission.run(lambda: service.execute("SELECT 1 AS value", None, QueryLimits(200, 15)), 15)
    assert result.rows == [{"value": 1}]


@pytest.mark.asyncio
async def test_guardrails_off_preserves_legacy_dml(lifecycle, monkeypatch):
    registry, pool, admission, service = lifecycle
    monkeypatch.setattr(server, "query_budget_config", QueryBudgetConfig(enabled=False))
    assert (await server.execute_sql("CREATE TEMP TABLE lifecycle_marker (id integer)"))[0].text == "No results"
    assert (await server.execute_sql("INSERT INTO lifecycle_marker VALUES (1)"))[0].text == "No results"
    assert (await server.execute_sql("SELECT id FROM lifecycle_marker"))[0].text == "[{'id': 1}]"
    with pytest.raises(PublicToolError) as error:
        await service.execute("INSERT INTO lifecycle_marker VALUES (2)", None, QueryLimits(200, 15))
    assert error.value.code == "SQL_VALIDATION_FAILED"
    with pytest.raises(psycopg.errors.DivisionByZero):
        await SqlDriver(pool).execute_query("BEGIN; INSERT INTO lifecycle_marker VALUES (2); SELECT 1 / 0")
    assert (await server.execute_sql("SELECT id FROM lifecycle_marker"))[0].text == "[{'id': 1}]"
    assert registry.active_leases("app_development") == 0


@pytest.mark.asyncio
async def test_shutdown_drains_cancelled_query(lifecycle, monkeypatch):
    registry, pool, admission, service = lifecycle
    fetching = asyncio.Event()
    original_fetch = psycopg.AsyncServerCursor.fetchmany

    async def fetch(cursor, size=0):
        fetching.set()
        return await original_fetch(cursor, size)

    monkeypatch.setattr(psycopg.AsyncServerCursor, "fetchmany", fetch)
    query = asyncio.create_task(admission.run(lambda: service.execute("SELECT pg_catalog.pg_sleep(30)", None, QueryLimits(200, 60)), 60))
    shutdown = None
    try:
        await asyncio.wait_for(fetching.wait(), 5)
        shutdown = asyncio.create_task(registry.close_all())
        await asyncio.sleep(0)
        assert not shutdown.done()
        query.cancel()
        with pytest.raises(asyncio.CancelledError):
            await query
        await asyncio.wait_for(shutdown, 5)
        assert registry.active_leases("app_development") == 0
        assert pool.pool is None
        with pytest.raises(DatabaseUnavailableError) as error:
            await service.execute("SELECT 1", None, QueryLimits(200, 15))
        assert to_public_error(error.value).code == "DATABASE_UNAVAILABLE"
    finally:
        query.cancel()
        await asyncio.gather(query, return_exceptions=True)
        if shutdown is not None:
            await shutdown


@pytest.mark.asyncio
async def test_large_result_stays_within_hard_row_cap(lifecycle):
    registry, pool, admission, service = lifecycle
    result = await admission.run(lambda: service.execute("SELECT pg_catalog.generate_series(1, 1000000) AS id", None, QueryLimits(5000, 60)), 60)
    assert result.returned_rows == 5000
    assert result.rows[0] == {"id": 1}
    assert result.rows[-1] == {"id": 5000}
    assert result.truncated is True
    assert result.limit_reached == "max_rows"
    assert len(encode_bounded_result(result, 2_097_152)) <= 2_097_152
    assert registry.active_leases("app_development") == 0


@pytest.mark.asyncio
async def test_large_result_stays_within_byte_and_memory_caps(lifecycle):
    registry, pool, admission, service = lifecycle
    bounded = QueryExecutionService(server.get_sql_driver, 4096)
    tracemalloc.start()
    try:
        result = await admission.run(
            lambda: bounded.execute(
                "SELECT id, pg_catalog.repeat('x', 1000) AS payload FROM pg_catalog.generate_series(1, 1000000) AS id",
                None,
                QueryLimits(5000, 15),
            ),
            15,
        )
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert result.returned_rows == 3
    assert result.truncated is True
    assert result.limit_reached == "max_result_bytes"
    assert len(encode_bounded_result(result, 4096)) <= 4096
    assert peak < 8 * 1024 * 1024
    assert registry.active_leases("app_development") == 0
