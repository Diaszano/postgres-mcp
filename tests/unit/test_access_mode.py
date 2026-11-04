import asyncio
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from pgscope.server import AccessMode
from pgscope.server import get_sql_driver
from pgscope.sql.safe_sql import SafeSqlDriver
from pgscope.sql.sql_driver import DbConnPool
from pgscope.sql.sql_driver import SqlDriver


@pytest.fixture
def mock_db_connection():
    """Mock database connection pool."""
    conn = MagicMock(spec=DbConnPool)
    conn.is_valid = True
    return conn


@pytest.mark.parametrize(
    "access_mode,expected_driver_type",
    [
        (AccessMode.UNRESTRICTED, SqlDriver),
        (AccessMode.RESTRICTED, SafeSqlDriver),
    ],
)
@pytest.mark.asyncio
async def test_get_sql_driver_returns_correct_driver(access_mode, expected_driver_type, mock_db_connection):
    """Test that get_sql_driver returns the correct driver type based on access mode."""
    with (
        patch("pgscope.server.current_access_mode", access_mode),
        patch("pgscope.server.db_connection", mock_db_connection),
    ):
        async with get_sql_driver() as driver:
            assert isinstance(driver, expected_driver_type)

            # When in RESTRICTED mode, verify timeout is set
            if access_mode == AccessMode.RESTRICTED:
                assert isinstance(driver, SafeSqlDriver)
                assert driver.timeout == 30


@pytest.mark.asyncio
async def test_get_sql_driver_sets_timeout_in_restricted_mode(mock_db_connection):
    """Test that get_sql_driver sets the timeout in restricted mode."""
    with (
        patch("pgscope.server.current_access_mode", AccessMode.RESTRICTED),
        patch("pgscope.server.db_connection", mock_db_connection),
    ):
        async with get_sql_driver() as driver:
            assert isinstance(driver, SafeSqlDriver)
            assert driver.timeout == 30
            assert hasattr(driver, "sql_driver")


@pytest.mark.asyncio
async def test_get_sql_driver_in_unrestricted_mode_no_timeout(mock_db_connection):
    """Test that get_sql_driver in unrestricted mode is a regular SqlDriver."""
    with (
        patch("pgscope.server.current_access_mode", AccessMode.UNRESTRICTED),
        patch("pgscope.server.db_connection", mock_db_connection),
    ):
        async with get_sql_driver() as driver:
            assert isinstance(driver, SqlDriver)
            assert not hasattr(driver, "timeout")


@pytest.mark.asyncio
async def test_command_line_parsing():
    """Test that command-line arguments correctly set the access mode."""
    import sys

    from pgscope.server import main

    # Mock sys.argv and asyncio.run
    original_argv = sys.argv
    original_run = asyncio.run

    try:
        # Test with --access-mode=restricted
        sys.argv = [
            "pgscope",
            "postgresql://user:password@localhost/db",
            "--access-mode=restricted",
        ]
        asyncio.run = AsyncMock()

        with (
            patch("pgscope.server.current_access_mode", AccessMode.UNRESTRICTED),
            patch("pgscope.server.db_connection.pool_connect", AsyncMock()),
            patch("pgscope.server.mcp.run_stdio_async", AsyncMock()),
            patch("pgscope.server.shutdown", AsyncMock()),
        ):
            # Reset the current_access_mode to UNRESTRICTED
            import pgscope.server

            pgscope.server.current_access_mode = AccessMode.UNRESTRICTED

            # Run main (partially mocked to avoid actual connection)
            try:
                await main()
            except Exception:
                pass

            # Verify the mode was changed to RESTRICTED
            assert pgscope.server.current_access_mode == AccessMode.RESTRICTED

    finally:
        # Restore original values
        sys.argv = original_argv
        asyncio.run = original_run
