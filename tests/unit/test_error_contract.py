from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch
import pytest
from mcp import types

from postgres_mcp.security.errors import DatabaseNotAllowedError
from postgres_mcp.security.errors import SQLValidationError
from postgres_mcp.sql.database_registry import PoolCapacityError
from postgres_mcp.server import AccessMode
from postgres_mcp.server import analyze_db_health
from postgres_mcp.server import execute_sql
from postgres_mcp.server import list_databases
from postgres_mcp.server import list_schemas
from postgres_mcp.server import mcp


@pytest.mark.asyncio
async def test_execute_sql_safe_error_on_wire():
    with patch("postgres_mcp.server.get_sql_driver") as mock_get:
        mock_driver = MagicMock()
        mock_driver.execute_query = AsyncMock(side_effect=SQLValidationError("Unsafe command"))
        mock_get.return_value.__aenter__.return_value = mock_driver

        res = await execute_sql("DROP TABLE users")
        assert isinstance(res, types.CallToolResult)
        assert res.isError is True
        assert res.structuredContent is not None
        assert res.structuredContent["error"]["code"] == "SQL_VALIDATION_FAILED"
        assert len(res.content) >= 1
        assert "Unsafe command" not in res.content[0].text
        assert "The SQL statement is not allowed." in res.content[0].text


def test_existing_read_only_annotations():
    tools = mcp._tool_manager.list_tools()
    tool_map = {t.name: t for t in tools}

    expected_read_only = [
        "list_databases",
        "list_schemas",
        "list_objects",
        "get_object_details",
        "explain_query",
        "analyze_workload_indexes",
        "analyze_query_indexes",
        "analyze_db_health",
        "get_top_queries",
        "fetch_query_page",
    ]
    for name in expected_read_only:
        assert name in tool_map, f"Tool {name} should exist"
        annotations = tool_map[name].annotations
        assert annotations is not None, f"Tool {name} must have annotations"
        assert getattr(annotations, "readOnlyHint", None) is True, f"Tool {name} must have readOnlyHint=True"


@pytest.mark.asyncio
async def test_legacy_text_fallback():
    with patch("postgres_mcp.server.get_sql_driver") as mock_get:
        mock_driver = MagicMock()
        mock_cell = MagicMock()
        mock_cell.cells = {"col": 123}
        mock_driver.execute_query = AsyncMock(return_value=[mock_cell])
        mock_get.return_value.__aenter__.return_value = mock_driver

        res = await execute_sql("SELECT 123 as col")
        assert len(res) >= 1
        assert isinstance(res[0], types.TextContent)
        assert "123" in res[0].text


@pytest.mark.asyncio
async def test_expected_health_errors():
    with patch("postgres_mcp.server.get_sql_driver") as mock_get:
        mock_get.return_value.__aenter__.side_effect = PoolCapacityError("exhausted")
        res = await analyze_db_health("all")
        assert isinstance(res, types.CallToolResult)
        assert res.isError is True
        assert res.structuredContent["error"]["code"] == "POOL_CAPACITY_EXCEEDED"

    with patch("postgres_mcp.server.get_sql_driver") as mock_get:
        mock_get.return_value.__aenter__.side_effect = RuntimeError("database secret pass")
        res = await analyze_db_health("all")
        assert isinstance(res, types.CallToolResult)
        assert res.isError is True
        assert res.structuredContent["error"]["code"] == "INTERNAL_ERROR"
        assert "secret" not in res.content[0].text
