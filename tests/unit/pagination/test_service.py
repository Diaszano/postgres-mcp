import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

import pytest

from postgres_mcp.application.query_service import QueryExecutionService
from postgres_mcp.pagination.cursors import InMemoryCursorStore
from postgres_mcp.pagination.service import PaginationService
from postgres_mcp.query_limits.results import BoundedQueryResult
from postgres_mcp.security.errors import DatabaseNotAllowedError
from postgres_mcp.security.errors import PublicToolError
from postgres_mcp.sql import SqlDriver
from postgres_mcp.sql.sql_driver import query_for_validation


class PageDriver:
    def __init__(self):
        self.rows: list[dict[str, Any]] = [{"id": i} for i in range(1, 301)]
        self.allowed = True
        self.failure: PublicToolError | None = None
        self.leases = 0

    @asynccontextmanager
    async def acquire(self, database):
        if not self.allowed:
            raise DatabaseNotAllowedError("Denied")
        self.leases += 1
        try:
            yield self
        finally:
            self.leases -= 1

    async def execute_query(self, query, **kwargs):
        return [SqlDriver.RowResult({"verified": True})]

    async def execute_bounded_query(self, query, *, params, max_rows, timeout_seconds, **kwargs):
        if self.failure:
            raise self.failure
        if "OFFSET" in query:
            limit, offset = params
            last_key = None
        elif len(params) == 2:
            last_key, limit = params
            offset = 0
        else:
            (limit,) = params
            last_key, offset = None, 0
        rows = [row for row in self.rows if last_key is None or row["id"] > last_key][offset : offset + limit]
        return BoundedQueryResult(rows[:max_rows], min(len(rows), max_rows), len(rows) > max_rows, None, 1, timeout_seconds)


def make_service(driver, max_result_bytes=2_097_152):
    store = InMemoryCursorStore()
    return PaginationService(QueryExecutionService(driver.acquire, max_result_bytes), store, max_result_bytes), store


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["offset", "keyset"])
async def test_first_page_and_continuation_budget(mode):
    driver = PageDriver()
    service, store = make_service(driver)
    first = await service.first_page("SELECT id FROM items ORDER BY id", "app", 250, 15, 100, mode, "alice")
    assert first.next_cursor is not None
    second = await service.next_page(first.next_cursor, None, "alice")
    assert second.next_cursor is not None
    third = await service.next_page(second.next_cursor, None, "alice")
    assert [page.returned_rows for page in (first, second, third)] == [100, 100, 50]
    assert [page.total_returned_rows for page in (first, second, third)] == [100, 200, 250]
    assert [row["id"] for page in (first, second, third) for row in page.rows] == list(range(1, 251))
    assert third.has_more is False
    assert third.next_cursor is None
    assert third.truncated is True
    assert third.limit_reached == "max_rows"
    with pytest.raises(PublicToolError, match="invalid"):
        store.reserve(first.next_cursor, "alice")


@pytest.mark.asyncio
async def test_resume_rechecks_authorization():
    driver = PageDriver()
    service, store = make_service(driver)
    first = await service.first_page("SELECT id FROM items ORDER BY id", "app", 250, 15, 100, "offset", "alice")
    assert first.next_cursor is not None
    driver.allowed = False
    with pytest.raises(PublicToolError) as error:
        await service.next_page(first.next_cursor, None, "alice")
    assert error.value.code == "DATABASE_NOT_ALLOWED"
    reservation = store.reserve(first.next_cursor, "alice")
    assert reservation.state.total_returned_rows == 100
    store.release_on_error(reservation)
    driver.allowed = True
    assert (await service.next_page(first.next_cursor, None, "alice")).rows[0] == {"id": 101}


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "serialization"])
async def test_failed_page_does_not_advance_cursor(failure):
    driver = PageDriver()
    service, store = make_service(driver)
    first = await service.first_page("SELECT id FROM items ORDER BY id", "app", 250, 15, 100, "offset", None)
    assert first.next_cursor is not None
    if failure == "timeout":
        driver.failure = PublicToolError("QUERY_TIMEOUT", "Timed out")
    else:
        driver.rows[100]["payload"] = object()
    with pytest.raises(PublicToolError) as error:
        await service.next_page(first.next_cursor, None, None)
    assert error.value.code == ("QUERY_TIMEOUT" if failure == "timeout" else "RESULT_TOO_LARGE")
    reservation = store.reserve(first.next_cursor, None)
    assert reservation.state.offset == 100
    store.release_on_error(reservation)
    driver.failure = None
    driver.rows[100].pop("payload", None)
    assert (await service.next_page(first.next_cursor, None, None)).rows[0] == {"id": 101}


@pytest.mark.asyncio
async def test_response_byte_budget_includes_metadata():
    from mcp import types

    driver = PageDriver()
    driver.rows = [{"id": i, "payload": "é" * 100_000} for i in range(1, 20)]
    service, _ = make_service(driver)
    page = await service.first_page("SELECT id, payload FROM items ORDER BY id", "app", 50, 15, 10, "keyset", None)
    content = [types.TextContent(type="text", text=page.to_text())]
    response = types.CallToolResult(
        content=list(content), structuredContent={"result": [block.model_dump(mode="json", by_alias=True) for block in content]}
    )
    assert len(response.model_dump_json(exclude_none=True).encode("utf-8")) <= 2_097_152
    assert 0 < page.returned_rows < 10
    assert page.has_more is True
    assert page.limit_reached == "max_result_bytes"
    assert page.next_cursor is not None
    assert json.loads(page.to_text())["next_cursor"] == page.next_cursor
    next_page = await service.next_page(page.next_cursor, None, None)
    assert next_page.rows[0]["id"] == page.rows[-1]["id"] + 1


@pytest.mark.asyncio
async def test_response_is_serialized_before_cursor_commit(monkeypatch):
    import postgres_mcp.pagination.service as service_module

    service, _ = make_service(PageDriver())
    page = await service.first_page("SELECT id FROM items ORDER BY id", "app", 250, 15, 100, "offset", None)

    def failed_serialization(*args, **kwargs):
        raise AssertionError("Response must already be serialized")

    monkeypatch.setattr(service_module, "encode_bounded_result", failed_serialization)
    assert json.loads(page.to_text())["next_cursor"] == page.next_cursor


@pytest.mark.asyncio
async def test_no_connection_held_between_pages():
    driver = PageDriver()
    service, _ = make_service(driver)
    page = await service.first_page("SELECT id FROM items ORDER BY id", "app", 250, 15, 100, "offset", None)
    assert driver.leases == 0
    while page.next_cursor:
        page = await service.next_page(page.next_cursor, None, None)
        assert driver.leases == 0


@pytest.mark.asyncio
async def test_exact_end_does_not_claim_more():
    driver = PageDriver()
    driver.rows = driver.rows[:100]
    service, _ = make_service(driver)
    page = await service.first_page("SELECT id FROM items ORDER BY id", "app", 250, 15, 100, "offset", None)
    assert page.has_more is False
    assert page.truncated is False
    assert page.next_cursor is None


@pytest.mark.asyncio
async def test_byte_limited_read_keeps_has_more_unknown(monkeypatch):
    driver = PageDriver()
    service, _ = make_service(driver)

    async def bounded(*args, **kwargs):
        return BoundedQueryResult([{"id": 1}], 1, True, "max_result_bytes", 1, 15)

    monkeypatch.setattr(driver, "execute_bounded_query", bounded)
    page = await service.first_page("SELECT id FROM items ORDER BY id", "app", 250, 15, 100, "offset", None)
    assert page.has_more is None
    assert page.next_cursor is not None
    assert page.truncated is True
    assert page.limit_reached == "max_result_bytes"


@pytest.mark.asyncio
async def test_cancelled_page_releases_reservation_and_lease(monkeypatch):
    driver = PageDriver()
    service, store = make_service(driver)
    first = await service.first_page("SELECT id FROM items ORDER BY id", "app", 250, 15, 100, "offset", None)
    assert first.next_cursor is not None
    fetching = asyncio.Event()

    async def blocked(*args, **kwargs):
        fetching.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(driver, "execute_bounded_query", blocked)
    task = asyncio.create_task(service.next_page(first.next_cursor, None, None))
    await asyncio.wait_for(fetching.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert driver.leases == 0
    reservation = store.reserve(first.next_cursor, None)
    assert reservation.state.total_returned_rows == 100
    store.release_on_error(reservation)


@pytest.mark.parametrize("page_size", [0, -1, True, 1.5])
@pytest.mark.asyncio
async def test_invalid_page_size_preserves_cursor(page_size):
    service, _ = make_service(PageDriver())
    first = await service.first_page("SELECT id FROM items ORDER BY id", "app", 250, 15, 100, "offset", None)
    assert first.next_cursor is not None
    with pytest.raises(PublicToolError) as error:
        await service.next_page(first.next_cursor, page_size, None)
    assert error.value.code == "INVALID_QUERY_OPTIONS"
    page = await service.next_page(first.next_cursor, 20, None)
    assert page.rows == [{"id": i} for i in range(101, 121)]
    assert page.page_size == 20


def test_bound_sql_validation_preserves_literal_percent_and_values():
    template = """SELECT "key%%s" FROM items WHERE label = '%%s 50%%' AND "key%%s" > %s LIMIT %s"""
    marker = "'; DROP TABLE items; -- %s"
    parsed = query_for_validation(template, (marker, 10))
    assert parsed == """SELECT "key%s" FROM items WHERE label = '%s 50%' AND "key%s" > $1 LIMIT $2"""
    assert marker not in parsed
    with pytest.raises(ValueError, match="parameter count"):
        query_for_validation(template, (marker,))
