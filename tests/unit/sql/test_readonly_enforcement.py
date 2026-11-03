from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from postgres_mcp.server import AccessMode
from postgres_mcp.server import get_sql_driver
from postgres_mcp.sql import SafeSqlDriver
from postgres_mcp.sql import SqlDriver


@pytest.mark.asyncio
async def test_force_readonly_enforcement():
    """
    Test that force_readonly is properly enforced based on access mode:
    - In RESTRICTED mode: force_readonly is always True regardless of what's passed
    - In UNRESTRICTED mode: force_readonly respects the passed value (default False)
    """
    # Create mock for connection pool
    mock_conn_pool = MagicMock()
    mock_conn_pool._is_valid = True

    # Create a mock for the base SqlDriver._execute_with_connection
    mock_execute = AsyncMock()
    mock_execute.return_value = [SqlDriver.RowResult(cells={"test": "value"})]

    # Test UNRESTRICTED mode
    with (
        patch("postgres_mcp.server.current_access_mode", AccessMode.UNRESTRICTED),
        patch("postgres_mcp.server.db_connection", mock_conn_pool),
        patch.object(SqlDriver, "_execute_with_connection", mock_execute),
    ):
        async with get_sql_driver() as driver:
            assert isinstance(driver, SqlDriver)
            assert not isinstance(driver, SafeSqlDriver)

            # Test default behavior (should be False)
            mock_execute.reset_mock()
            await driver.execute_query("SELECT 1")
            assert mock_execute.call_count == 1
            # Check that force_readonly is False by default
            assert mock_execute.call_args[1]["force_readonly"] is False

            # Test explicit True
            mock_execute.reset_mock()
            await driver.execute_query("SELECT 1", force_readonly=True)
            assert mock_execute.call_count == 1
            # Check that force_readonly=True is respected
            assert mock_execute.call_args[1]["force_readonly"] is True

            # Test explicit False
            mock_execute.reset_mock()
            await driver.execute_query("SELECT 1", force_readonly=False)
            assert mock_execute.call_count == 1
            # Check that force_readonly=False is respected
            assert mock_execute.call_args[1]["force_readonly"] is False

    # Test RESTRICTED mode
    with (
        patch("postgres_mcp.server.current_access_mode", AccessMode.RESTRICTED),
        patch("postgres_mcp.server.db_connection", mock_conn_pool),
        patch.object(SqlDriver, "_execute_with_connection", mock_execute),
    ):
        async with get_sql_driver() as driver:
            assert isinstance(driver, SafeSqlDriver)

            # Test default behavior
            mock_execute.reset_mock()
            await driver.execute_query("SELECT 1")
            assert mock_execute.call_count == 1
            # Check that force_readonly is always True
            assert mock_execute.call_args[1]["force_readonly"] is True

            # Test explicit False (should still be True)
            mock_execute.reset_mock()
            await driver.execute_query("SELECT 1", force_readonly=False)
            assert mock_execute.call_count == 1
            # Check that force_readonly is True despite passing False
            assert mock_execute.call_args[1]["force_readonly"] is True

            # Test explicit True
            mock_execute.reset_mock()
            await driver.execute_query("SELECT 1", force_readonly=True)
            assert mock_execute.call_count == 1
            # Check that force_readonly remains True
            assert mock_execute.call_args[1]["force_readonly"] is True


# --- Task 12: restricted guards hold for the default and for an explicit database ---

from contextlib import asynccontextmanager  # noqa: E402

from postgres_mcp.database_config import parse_database_config  # noqa: E402
from postgres_mcp.server import execute_sql  # noqa: E402
from postgres_mcp.server import explain_query  # noqa: E402

# Direct calls bypass FastMCP, so explain_query's Field() defaults are passed explicitly.
DATABASES = pytest.mark.parametrize("database", [None, "app_testing"], ids=["default", "explicit"])


class _Registry:
    """Minimal DatabaseRegistry stand-in: one mock pool per name."""

    def __init__(self) -> None:
        self.pools: dict[str, MagicMock] = {}

    @asynccontextmanager
    async def acquire(self, database: str | None = None):
        yield self.pools.setdefault(database or "app_main", MagicMock())


@pytest.fixture
def restricted_discovery():
    """Restricted discovery mode; yields the connection-level mock: any call means SQL reached PostgreSQL."""
    config = parse_database_config({"DATABASE_URI": "postgresql://u:p@h/app_main", "DATABASE_AUTO_DISCOVER": "true"}, None, None)
    sql_executed = AsyncMock(return_value=[SqlDriver.RowResult(cells={"QUERY PLAN": []})])
    with (
        patch("postgres_mcp.server.database_config", config),
        patch("postgres_mcp.server.registry", _Registry()),
        patch("postgres_mcp.server.current_access_mode", AccessMode.RESTRICTED),
        patch.object(SqlDriver, "_execute_with_connection", sql_executed),
    ):
        yield sql_executed


WRITES = [
    "DELETE FROM isolated_marker",
    "INSERT INTO isolated_marker VALUES (1)",
    "UPDATE isolated_marker SET id = 2",
    "DROP TABLE isolated_marker",
    "SELECT 1; DELETE FROM isolated_marker",
    "SELECT 1; COMMIT; DELETE FROM isolated_marker",
    "WITH d AS (DELETE FROM isolated_marker RETURNING *) SELECT * FROM d",
]


@DATABASES
@pytest.mark.parametrize("sql", WRITES)
@pytest.mark.asyncio
async def test_restricted_denies_dml_and_multiple_statements(restricted_discovery, database, sql):
    results = [
        await execute_sql(sql=sql, database=database),
        await explain_query(sql, False, [], database=database),
        await explain_query(sql, True, [], database=database),
        await explain_query(sql, False, [{"table": "isolated_marker", "columns": ["id"]}], database=database),
    ]
    for result in results:
        assert result[0].text.startswith("Error: ") and "Cannot use analyze" not in result[0].text
    restricted_discovery.assert_not_called()  # writes_executed == 0: nothing reached the connection


DANGEROUS = [
    "DELETE FROM isolated_marker WHERE id = $1",
    "SELECT * FROM dblink_exec('dbname=app_main', 'DELETE FROM isolated_marker')",
    "SELECT * FROM pg_terminate_backend(1)",
    "SELECT * FROM isolated_marker, lo_import('/etc/passwd')",
    "SELECT pg_sleep(10)",
]


@DATABASES
@pytest.mark.parametrize("sql", DANGEROUS)
@pytest.mark.asyncio
async def test_restricted_explain_analyze_rejects_dangerous_sql(restricted_discovery, database, sql):
    result = await explain_query(sql, True, [], database=database)
    assert "Error:" in result[0].text
    restricted_discovery.assert_not_called()  # rejected before any query, even the bind-parameter lookups


FROM_FUNCTIONS = [
    "SELECT * FROM dblink_exec('dbname=app_main', 'DELETE FROM isolated_marker')",
    "SELECT * FROM pg_terminate_backend(1)",
    "SELECT * FROM pg_read_file('/etc/passwd')",
    "SELECT * FROM lo_import('/etc/passwd')",
    "SELECT * FROM dblink('dbname=app_main', 'SELECT 1') AS t(a int)",
    "SELECT * FROM pg_catalog.set_config('default_transaction_read_only', 'off', false)",
    "SELECT * FROM isolated_marker JOIN LATERAL pg_terminate_backend(isolated_marker.id) ON true",
]


@DATABASES
@pytest.mark.parametrize("sql", FROM_FUNCTIONS)
@pytest.mark.asyncio
async def test_restricted_denies_function_in_from_clause(restricted_discovery, database, sql):
    for result in (
        await execute_sql(sql=sql, database=database),
        await explain_query(sql, False, [], database=database),
        await explain_query(sql, True, [], database=database),
    ):
        assert "Error:" in result[0].text
    restricted_discovery.assert_not_called()


@DATABASES
@pytest.mark.asyncio
async def test_restricted_allows_allowlisted_function_in_from_clause(restricted_discovery, database):
    restricted_discovery.return_value = [SqlDriver.RowResult(cells={"generate_series": 1})]
    result = await execute_sql(sql="SELECT * FROM generate_series(1,3)", database=database)
    assert "Error:" not in result[0].text
    restricted_discovery.assert_called_once()
