import asyncio

import pytest
import pytest_asyncio
from psycopg.pq import TransactionStatus

from pgscope.query_limits.admission import QueryAdmission
from pgscope.security.errors import PublicToolError
from pgscope.sql.sql_driver import DbConnPool
from pgscope.sql.sql_driver import SqlDriver
from tests.type_helpers import first_item


@pytest_asyncio.fixture
async def query_pool(multidb_postgres):
    pool = DbConnPool(multidb_postgres.uri(multidb_postgres.mcp_role, "app_development"), min_size=1, max_size=1)
    await pool.pool_connect()
    try:
        yield pool
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_statement_timeout_is_transaction_local(query_pool):
    admission = QueryAdmission(1)
    driver = SqlDriver(query_pool)
    async with query_pool.pool.connection() as connection:
        original = first_item(await (await connection.execute("SHOW statement_timeout")).fetchone())

    async def operation():
        return await driver.execute_query("SHOW statement_timeout")

    rows = await admission.run(operation, 2)
    scoped = str(first_item(rows).cells["statement_timeout"])
    async with query_pool.pool.connection() as connection:
        assert connection.info.transaction_status == TransactionStatus.IDLE
        restored = first_item(await (await connection.execute("SHOW statement_timeout")).fetchone())
        milliseconds = first_item(await (await connection.execute("SELECT EXTRACT(EPOCH FROM %s::interval) * 1000", (scoped,))).fetchone())
    assert 0 < milliseconds <= 2000
    assert restored == original


@pytest.mark.asyncio
@pytest.mark.parametrize("force_readonly", [False, True])
async def test_server_deadline_cancels_slow_statement(query_pool, force_readonly):
    admission = QueryAdmission(1)
    driver = SqlDriver(query_pool)
    started = asyncio.get_running_loop().time()

    async def operation():
        return await driver.execute_query("SELECT pg_sleep(2)", force_readonly=force_readonly)

    with pytest.raises(PublicToolError) as error:
        await admission.run(operation, 0.1)
    assert error.value.code == "QUERY_TIMEOUT"
    assert asyncio.get_running_loop().time() - started < 1.5
    async with query_pool.pool.connection() as connection:
        assert connection.info.transaction_status == TransactionStatus.IDLE
        assert first_item(await (await connection.execute("SELECT 1")).fetchone()) == 1
        assert first_item(await (await connection.execute("SHOW statement_timeout")).fetchone()) == "0"


@pytest.mark.asyncio
async def test_postgres_statement_timeout_rolls_back(query_pool):
    admission = QueryAdmission(1)
    driver = SqlDriver(query_pool)
    async with query_pool.pool.connection() as connection:
        await connection.execute("CREATE TEMPORARY TABLE timeout_marker (id integer)")

    async def operation():
        # A shorter local timer makes PostgreSQL cancellation win over the Python deadline.
        return await driver.execute_query(
            "SELECT set_config('statement_timeout', '20ms', true); INSERT INTO timeout_marker VALUES (1); SELECT pg_sleep(2)"
        )

    with pytest.raises(PublicToolError) as error:
        await admission.run(operation, 1)
    assert error.value.code == "QUERY_TIMEOUT"
    async with query_pool.pool.connection() as connection:
        assert connection.info.transaction_status == TransactionStatus.IDLE
        assert first_item(await (await connection.execute("SHOW statement_timeout")).fetchone()) == "0"
        assert first_item(await (await connection.execute("SELECT count(*) FROM timeout_marker")).fetchone()) == 0


@pytest.mark.asyncio
async def test_pool_checkout_consumes_the_statement_deadline(query_pool):
    admission = QueryAdmission(1)
    driver = SqlDriver(query_pool)
    task = None

    async def operation():
        return await driver.execute_query("SELECT current_setting('statement_timeout')::interval AS timeout")

    try:
        async with query_pool.pool.connection():
            task = asyncio.create_task(admission.run(operation, 1))
            await asyncio.sleep(0.2)
            assert not task.done()
        rows = await task
        assert 0 < first_item(rows).cells["timeout"].total_seconds() <= 0.9
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
