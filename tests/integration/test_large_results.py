import time

import pytest

from postgres_mcp.sql.sql_driver import SqlDriver


@pytest.mark.asyncio
async def test_bounded_driver_reads_only_capped_rows(multidb_postgres):
    driver = SqlDriver(engine_url=multidb_postgres.uri(multidb_postgres.mcp_role, "app_development"))
    result = await driver.execute_bounded_query(
        "SELECT generate_series(1, 1000000) AS id",
        max_rows=200,
        max_result_bytes=2_097_152,
        timeout_seconds=15,
    )
    assert result.returned_rows == 200
    assert result.rows[0] == {"id": 1}
    assert result.rows[-1] == {"id": 200}
    assert result.truncated is True
    assert result.limit_reached == "max_rows"


@pytest.mark.asyncio
async def test_bounded_driver_does_not_evaluate_all_server_rows(multidb_postgres):
    driver = SqlDriver(engine_url=multidb_postgres.uri(multidb_postgres.mcp_role, "app_development"))
    started = time.monotonic()
    result = await driver.execute_bounded_query(
        "SELECT pg_catalog.pg_sleep(0.01), g AS id FROM generate_series(1, 1000) AS g",
        max_rows=20,
        max_result_bytes=2_097_152,
        timeout_seconds=15,
    )
    elapsed = time.monotonic() - started
    assert result.returned_rows == 20
    assert result.truncated is True
    assert elapsed < 5
