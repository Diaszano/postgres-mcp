from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest

from postgres_mcp.security.errors import SQLValidationError
from postgres_mcp.sql import SafeSqlDriver
from postgres_mcp.sql import SqlDriver


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "UPDATE public.items SET id = 2",
        "DELETE FROM public.items",
        "CREATE EXTENSION IF NOT EXISTS hypopg",
        "VACUUM public.items",
        "ANALYZE public.items",
        "EXPLAIN ANALYZE SELECT 1",
        "WITH changed AS (DELETE FROM public.items RETURNING *) SELECT * FROM changed",
    ],
)
async def test_restricted_rejects_write_ast_and_data_modifying_ctes(query):
    driver = Mock(spec=SqlDriver)
    driver.execute_query = AsyncMock()
    with pytest.raises(SQLValidationError):
        await SafeSqlDriver(driver).execute_query(query)
    driver.execute_query.assert_not_awaited()


@pytest.mark.parametrize("query", ["SELECT public.lower('x')", """SELECT "PG_CATALOG".lower('x')""", "SELECT 1 OPERATOR(public.+) 2"])
def test_restricted_rejects_explicit_untrusted_resolution(query):
    with pytest.raises(SQLValidationError):
        SafeSqlDriver(Mock()).validate(query)


def test_restricted_policy_accepts_qualified_reads():
    from postgres_mcp.sql.safe_sql import validate_restricted_sql

    validate_restricted_sql("SELECT pg_catalog.lower(name) FROM public.items")
