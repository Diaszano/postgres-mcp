import asyncio
import inspect
import json
import time
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from mcp.server.fastmcp.tools import Tool
from mcp.types import CallToolResult
from psycopg.errors import QueryCanceled

import postgres_mcp.server as server
from postgres_mcp.query_limits.admission import QueryAdmission
from postgres_mcp.query_limits.admission import remaining_query_seconds
from postgres_mcp.query_limits.config import QueryBudgetConfig
from postgres_mcp.query_limits.results import BoundedQueryResult
from postgres_mcp.query_limits.results import encode_bounded_result
from postgres_mcp.security.errors import to_public_error
from postgres_mcp.sql import SafeSqlDriver
from postgres_mcp.sql import SqlDriver


def result():
    return BoundedQueryResult([{"answer": 1}], 1, False, None, 0, 15)


def mcp_result(response):
    content, structured = Tool.from_function(server.execute_sql).fn_metadata.convert_result(response)
    return CallToolResult(content=content, structuredContent=structured)


@pytest.fixture
def guarded(monkeypatch):
    monkeypatch.setattr(server, "query_budget_config", QueryBudgetConfig(enabled=True))


def test_execute_sql_schema_adds_optional_args():
    parameters = inspect.signature(server.execute_sql).parameters
    assert list(parameters) == ["sql", "database", "max_rows", "timeout_seconds", "page_size", "pagination"]
    assert parameters["sql"].default.default == "all"
    assert parameters["database"].default is None
    schema = Tool.from_function(server.execute_sql).parameters
    assert schema.get("required", []) == []
    for name in ("max_rows", "timeout_seconds", "page_size"):
        assert schema["properties"][name]["default"] is None
    assert schema["properties"]["sql"]["default"] == "all"
    assert schema["properties"]["pagination"]["default"] == "none"


@pytest.mark.asyncio
async def test_guarded_small_result_preserves_text_fallback(monkeypatch, guarded):
    driver = AsyncMock(spec=SqlDriver)
    driver.execute_bounded_query.return_value = result()

    @asynccontextmanager
    async def get_driver(database=None):
        assert remaining_query_seconds() is not None
        yield driver

    monkeypatch.setattr(server, "get_sql_driver", get_driver)
    response = await server.execute_sql("SELECT 1")
    assert response[0].type == "text"
    payload = json.loads(response[0].text)
    assert payload["rows"] == [{"answer": 1}]
    assert payload["returned_rows"] == 1
    assert payload["truncated"] is False
    assert payload["limit_reached"] is None
    driver.execute_bounded_query.assert_awaited_once_with("SELECT 1", max_rows=200, max_result_bytes=2097152, timeout_seconds=15)
    driver.execute_query.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("bytes_below_boundary", [0, 1])
async def test_mcp_byte_budget_counts_escaping_and_wrapper(monkeypatch, bytes_below_boundary):
    rows = [{"value": '"\\\n\tá🙂' * 5} for _ in range(2)]
    one_row = BoundedQueryResult(rows[:1], 1, True, "max_result_bytes", 0, 15)
    one_response = server.format_text_response(encode_bounded_result(one_row, 10000).decode("utf-8"))
    boundary = len(mcp_result(one_response).model_dump_json(exclude_none=True).encode("utf-8"))
    budget = boundary - bytes_below_boundary
    full_result = BoundedQueryResult(rows[:], 2, False, None, 0, 15)
    assert len(encode_bounded_result(full_result, budget)) <= budget
    monkeypatch.setattr(server, "query_budget_config", QueryBudgetConfig(enabled=True, max_result_bytes=budget))
    driver = AsyncMock(spec=SqlDriver)
    driver.execute_bounded_query.return_value = full_result

    @asynccontextmanager
    async def get_driver(database=None):
        yield driver

    monkeypatch.setattr(server, "get_sql_driver", get_driver)
    response = await server.execute_sql("SELECT 1")
    if bytes_below_boundary:
        assert response[0].text == "Error: The query result exceeds the response size limit."
    else:
        serialized = mcp_result(response).model_dump_json(exclude_none=True).encode("utf-8")
        assert len(serialized) == budget
        payload = json.loads(response[0].text)
        assert payload["rows"] == rows[:1]
        assert payload["returned_rows"] == 1
        assert payload["truncated"] is True
        assert payload["limit_reached"] == "max_result_bytes"


@pytest.mark.asyncio
async def test_deadline_covers_final_mcp_serialization(monkeypatch, guarded):
    driver = AsyncMock(spec=SqlDriver)
    driver.execute_bounded_query.return_value = result()
    original_dump = CallToolResult.model_dump_json

    class ShortAdmission(QueryAdmission):
        async def run(self, operation, timeout_seconds):
            return await super().run(operation, 0.01)

    def slow_dump(self, *args, **kwargs):
        assert remaining_query_seconds() is not None
        time.sleep(0.02)
        return original_dump(self, *args, **kwargs)

    @asynccontextmanager
    async def get_driver(database=None):
        yield driver

    monkeypatch.setattr(server, "get_sql_driver", get_driver)
    monkeypatch.setattr(server, "query_admission", ShortAdmission(1))
    monkeypatch.setattr(CallToolResult, "model_dump_json", slow_dump)
    assert (await server.execute_sql("SELECT 1"))[0].text == "Error: The query exceeded its time limit."
    assert remaining_query_seconds() is None


@pytest.mark.asyncio
@pytest.mark.parametrize("rows,expected", [(None, "No results"), ([], "[]"), ([SqlDriver.RowResult({"answer": 1})], "[{'answer': 1}]")])
async def test_rollout_off_is_behaviorally_legacy(monkeypatch, rows, expected):
    monkeypatch.setattr(server, "query_budget_config", QueryBudgetConfig())
    driver = AsyncMock(spec=SqlDriver)
    driver.execute_query.return_value = rows

    @asynccontextmanager
    async def get_driver(database=None):
        assert remaining_query_seconds() is None
        yield driver

    monkeypatch.setattr(server, "get_sql_driver", get_driver)
    assert (await server.execute_sql("SELECT 1"))[0].text == expected
    driver.execute_bounded_query.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("options", [{"page_size": 10}, {"pagination": "cursor"}])
async def test_future_pagination_rejected_before_checkout(monkeypatch, enabled, options):
    monkeypatch.setattr(server, "query_budget_config", QueryBudgetConfig(enabled=enabled))
    get_driver = AsyncMock()
    monkeypatch.setattr(server, "get_sql_driver", get_driver)
    response = await server.execute_sql("SELECT 1", **options)
    assert "pagination" in response[0].text.lower()
    get_driver.assert_not_called()


@pytest.mark.asyncio
async def test_guarded_restricted_queries_keep_validation(monkeypatch, guarded):
    base = AsyncMock(spec=SqlDriver)
    base.execute_bounded_query.return_value = result()
    driver = SafeSqlDriver(base, timeout=0.001)

    @asynccontextmanager
    async def get_driver(database=None):
        yield driver

    monkeypatch.setattr(server, "get_sql_driver", get_driver)
    assert "not allowed" in (await server.execute_sql("SELECT secret_function()"))[0].text
    base.execute_bounded_query.assert_not_called()
    response = await server.execute_sql("SELECT 1", timeout_seconds=60)
    assert json.loads(response[0].text)["rows"] == [{"answer": 1}]


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_restricted_timeout_uses_shared_deadline(monkeypatch, enabled):
    monkeypatch.setattr(server, "query_budget_config", QueryBudgetConfig(enabled=enabled))
    base = AsyncMock(spec=SqlDriver)

    async def slow(*args, **kwargs):
        await asyncio.sleep(0.02)
        return result() if enabled else [SqlDriver.RowResult({"answer": 1})]

    base.execute_bounded_query.side_effect = slow
    base.execute_query.side_effect = slow
    driver = SafeSqlDriver(base, timeout=0.001)

    @asynccontextmanager
    async def get_driver(database=None):
        yield driver

    monkeypatch.setattr(server, "get_sql_driver", get_driver)
    response = await server.execute_sql("SELECT 1", **({"timeout_seconds": 60} if enabled else {}))
    if enabled:
        assert json.loads(response[0].text)["rows"] == [{"answer": 1}]
    else:
        assert response[0].text == "Error: The query exceeded its time limit."


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_confirmed_query_timeout_maps_public_code(monkeypatch, enabled):
    monkeypatch.setattr(server, "query_budget_config", QueryBudgetConfig(enabled=enabled))
    driver = AsyncMock(spec=SqlDriver)
    driver.execute_bounded_query.side_effect = QueryCanceled("sensitive SQL")
    driver.execute_query.side_effect = QueryCanceled("sensitive SQL")
    errors = []
    original = server.format_exception_response

    def capture(operation, error):
        errors.append(error)
        return original(operation, error)

    @asynccontextmanager
    async def get_driver(database=None):
        yield driver

    monkeypatch.setattr(server, "get_sql_driver", get_driver)
    monkeypatch.setattr(server, "format_exception_response", capture)
    assert (await server.execute_sql("SELECT 1"))[0].text == "Error: The query exceeded its time limit."
    assert to_public_error(errors[0]).code == "QUERY_TIMEOUT"


@pytest.mark.asyncio
async def test_deadline_covers_serialization(monkeypatch, guarded):
    from postgres_mcp.query_limits.results import encode_bounded_result

    driver = AsyncMock(spec=SqlDriver)
    driver.execute_bounded_query.return_value = result()

    class ShortAdmission(QueryAdmission):
        async def run(self, operation, timeout_seconds):
            return await super().run(operation, 0.01)

    def slow_encode(*args):
        assert remaining_query_seconds() is not None
        time.sleep(0.02)
        return encode_bounded_result(*args)

    @asynccontextmanager
    async def get_driver(database=None):
        yield driver

    monkeypatch.setattr(server, "get_sql_driver", get_driver)
    monkeypatch.setattr(server, "query_admission", ShortAdmission(1), raising=False)
    monkeypatch.setattr(server, "encode_bounded_result", slow_encode, raising=False)
    assert (await server.execute_sql("SELECT 1"))[0].text == "Error: The query exceeded its time limit."
    assert remaining_query_seconds() is None


@pytest.mark.asyncio
async def test_stateful_hypopg_query_never_enables_lookahead(monkeypatch, guarded):
    base = AsyncMock(spec=SqlDriver)
    base.execute_bounded_query.return_value = BoundedQueryResult([{"indexrelid": 1}], 1, True, "max_rows", 0, 15)

    @asynccontextmanager
    async def get_driver(database=None):
        yield SafeSqlDriver(base, timeout=30)

    monkeypatch.setattr(server, "get_sql_driver", get_driver)
    response = await server.execute_sql("SELECT hypopg_reset()", max_rows=1)
    payload = json.loads(response[0].text)
    assert payload["truncated"] is True
    assert payload["limit_reached"] == "max_rows"
    assert base.execute_bounded_query.await_args.kwargs["safe_row_yielding"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM private",
        "SHOW work_mem",
        "SELECT 1; SELECT 2",
        "SELECT 1 INTO private",
        "WITH removed AS (DELETE FROM private RETURNING *) SELECT * FROM removed",
        "SELECT * FROM private FOR UPDATE",
        "invalid SQL",
    ],
)
async def test_guarded_non_bounded_sql_is_rejected_before_checkout(monkeypatch, guarded, sql):
    get_driver = AsyncMock()
    monkeypatch.setattr(server, "get_sql_driver", get_driver)
    assert "single read-only SELECT" in (await server.execute_sql(sql))[0].text
    get_driver.assert_not_called()


@pytest.mark.asyncio
async def test_admission_limits_leases_and_cancellation_releases_them(monkeypatch, guarded):
    entered = asyncio.Event()
    leases = 0
    total_leases = 0
    driver = AsyncMock(spec=SqlDriver)

    async def wait(*args, **kwargs):
        entered.set()
        await asyncio.Event().wait()

    driver.execute_bounded_query.side_effect = wait

    @asynccontextmanager
    async def get_driver(database=None):
        nonlocal leases, total_leases
        leases += 1
        total_leases += 1
        try:
            yield driver
        finally:
            leases -= 1

    monkeypatch.setattr(server, "get_sql_driver", get_driver)
    monkeypatch.setattr(server, "query_admission", QueryAdmission(1), raising=False)
    holder = asyncio.create_task(server.execute_sql("SELECT 1"))
    waiter = None
    try:
        await asyncio.wait_for(entered.wait(), 1)
        waiter = asyncio.create_task(server.execute_sql("SELECT 2"))
        await asyncio.sleep(0)
        assert leases == total_leases == 1
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        holder.cancel()
        with pytest.raises(asyncio.CancelledError):
            await holder
        assert leases == 0
        driver.execute_bounded_query.side_effect = None
        driver.execute_bounded_query.return_value = result()
        assert json.loads((await server.execute_sql("SELECT 3"))[0].text)["returned_rows"] == 1
    finally:
        for task in (holder, waiter):
            if task is not None and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
