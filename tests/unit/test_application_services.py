import inspect
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch
import pytest

from postgres_mcp.application.database_service import DatabaseInspectionService
from postgres_mcp.application.health_service import HealthInspectionService
from postgres_mcp.database_health import DatabaseHealthTool
from postgres_mcp.server import analyze_db_health
from postgres_mcp.server import execute_sql
from postgres_mcp.server import fetch_query_page
from postgres_mcp.server import get_object_details
from postgres_mcp.server import get_top_queries
from postgres_mcp.server import list_databases
from postgres_mcp.server import list_objects
from postgres_mcp.server import list_schemas
from postgres_mcp.sql import SafeSqlDriver
from postgres_mcp.sql import SqlDriver


@pytest.mark.asyncio
async def test_database_service_contract():
    mock_driver = MagicMock()
    mock_driver.execute_query = AsyncMock(
        return_value=[
            SqlDriver.RowResult(cells={"schema_name": "public", "schema_owner": "postgres", "schema_type": "User Schema"})
        ]
    )

    class FakeDriverContext:
        def __call__(self, database=None):
            self.database = database
            return self

        async def __aenter__(self):
            return mock_driver

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    driver_factory = FakeDriverContext()
    service = DatabaseInspectionService(driver_factory)

    # 1. list_schemas
    schemas = await service.list_schemas(database="my_db")
    assert driver_factory.database == "my_db"
    assert len(schemas) == 1
    assert schemas[0]["schema_name"] == "public"

    # 2. list_objects
    mock_row = SqlDriver.RowResult(cells={"table_schema": "public", "table_name": "users", "table_type": "BASE TABLE"})
    with patch.object(SafeSqlDriver, "execute_param_query", AsyncMock(return_value=[mock_row])):
        objs = await service.list_objects(schema_name="public", object_type="table", database="my_db")
        assert len(objs) == 1
        assert objs[0]["name"] == "users"

    # 3. get_object_details
    col_row = SqlDriver.RowResult(cells={"column_name": "id", "data_type": "integer", "is_nullable": "NO", "column_default": None})
    with patch.object(SafeSqlDriver, "execute_param_query", AsyncMock(side_effect=[[col_row], [], []])):
        details = await service.get_object_details(schema_name="public", object_name="users", object_type="table", database="my_db")
        assert details["basic"]["name"] == "users"
        assert len(details["columns"]) == 1
        assert details["columns"][0]["column"] == "id"


@pytest.mark.asyncio
async def test_health_and_top_queries_service():
    mock_driver = MagicMock()

    class FakeDriverContext:
        def __call__(self, database=None):
            self.database = database
            return self

        async def __aenter__(self):
            return mock_driver

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    driver_factory = FakeDriverContext()
    service = HealthInspectionService(driver_factory)

    with patch.object(DatabaseHealthTool, "health", AsyncMock(return_value="Health: OK")) as mock_health:
        res = await service.check_health("all", database="custom_db")
        assert res == "Health: OK"
        assert driver_factory.database == "custom_db"


def test_tool_parameter_contract():
    tools = {
        "list_databases": (list_databases, ["refresh"]),
        "list_schemas": (list_schemas, ["database"]),
        "list_objects": (list_objects, ["schema_name", "object_type", "database"]),
        "get_object_details": (get_object_details, ["schema_name", "object_name", "object_type", "database"]),
        "execute_sql": (execute_sql, ["sql", "database", "max_rows", "timeout_seconds", "page_size", "pagination"]),
        "fetch_query_page": (fetch_query_page, ["cursor", "page_size"]),
        "get_top_queries": (get_top_queries, ["sort_by", "limit", "database"]),
        "analyze_db_health": (analyze_db_health, ["health_type", "database"]),
    }
    for name, (fn, expected_params) in tools.items():
        params = list(inspect.signature(fn).parameters.keys())
        assert params == expected_params, f"Mismatch in {name} parameters: {params} vs {expected_params}"
