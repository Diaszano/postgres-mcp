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
