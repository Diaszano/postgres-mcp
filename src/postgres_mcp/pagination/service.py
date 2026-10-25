"""Execute independent pages; failed continuations retain their original token and expiry."""

from dataclasses import dataclass
from dataclasses import replace
from typing import Literal
from typing import cast

from mcp import types

from ..application.query_service import QueryExecutionService
from ..query_limits.admission import QueryAdmission
from ..query_limits.admission import remaining_query_seconds
from ..query_limits.policy import QueryLimits
from ..query_limits.results import BoundedQueryResult
from ..query_limits.results import encode_bounded_result
from ..security.errors import PublicToolError
from ..security.errors import SQLValidationError
from ..security.errors import to_public_error
from .cursors import CursorState
from .cursors import InMemoryCursorStore
from .planner import build_page_query


@dataclass
class PageResult(BoundedQueryResult):
    __slots__ = ("text",)

    database: str | None
    total_returned_rows: int
    max_rows: int
    page_size: int
    mode: Literal["offset", "keyset"]
    has_more: bool | None
    next_cursor: str | None
    expires_in_seconds: int
    consistency: str = "best_effort"

    def to_text(self) -> str:
        return self.text


class PaginationService:
    def __init__(
        self,
        query_service: QueryExecutionService,
        cursors: InMemoryCursorStore,
        max_result_bytes: int,
        admission: QueryAdmission | None = None,
    ):
        self._queries = query_service
        self._cursors = cursors
        self._max_result_bytes = max_result_bytes
        self._admission = admission or QueryAdmission(1)

    @staticmethod
    def _positive(value: int, name: str) -> None:
        if type(value) is not int or value <= 0:
            raise PublicToolError("INVALID_QUERY_OPTIONS", f"{name} must be a positive integer.")

    @staticmethod
    def _complete(result: PageResult, cursor: str | None) -> PageResult:
        result.next_cursor = cursor
        if cursor is not None:
            placeholder = '"next_cursor":"' + "x" * 43 + '"'
            result.text = ('"next_cursor":"' + cursor + '"').join(result.text.rsplit(placeholder, 1))
        return result

    async def first_page(
        self,
        sql: str,
        database: str | None,
        max_rows: int,
        timeout_seconds: int,
        page_size: int,
        mode: Literal["offset", "keyset"],
        principal: str | None,
    ) -> PageResult:
        for value, name in ((max_rows, "max_rows"), (timeout_seconds, "timeout_seconds"), (page_size, "page_size")):
            self._positive(value, name)

        async def execute():
            try:
                query = await self._queries.inspect_pageable(sql, database, mode)
            except SQLValidationError as exc:
                raise PublicToolError("PAGINATION_NOT_SUPPORTED", "The query does not support pagination.") from exc
            state = CursorState(query, database, mode, max_rows, timeout_seconds, page_size, principal)
            result, next_state = await self._page(state)
            remaining_query_seconds()
            return self._complete(result, self._cursors.issue(next_state) if next_state else None)

        try:
            return await self._admission.run(execute, timeout_seconds)
        except Exception as exc:
            raise to_public_error(exc) from exc

    async def next_page(self, cursor: str, page_size: int | None, principal: str | None) -> PageResult:
        if page_size is not None:
            self._positive(page_size, "page_size")
        reservation = self._cursors.reserve(cursor, principal)
        state = reservation.state
        if page_size is not None:
            state = replace(state, page_size=page_size)

        async def execute():
            result, next_state = await self._page(state)
            remaining_query_seconds()
            return self._complete(result, self._cursors.commit(reservation, next_state))

        try:
            return await self._admission.run(execute, cast(int, state.timeout_seconds))
        except BaseException as exc:
            self._cursors.release_on_error(reservation)
            if isinstance(exc, Exception):
                raise to_public_error(exc) from exc
            raise

    async def _page(self, state: CursorState) -> tuple[PageResult, CursorState | None]:
        page_size = min(state.page_size, state.max_rows - state.total_returned_rows)
        plan = build_page_query(
            state.query,
            offset=state.offset if state.mode == "offset" else None,
            last_key=state.last_key if state.mode == "keyset" else None,
            limit=page_size + 1,
        )
        bounded = await self._queries.execute_page(plan, state.database, QueryLimits(page_size + 1, cast(int, state.timeout_seconds)))
        more = True if bounded.returned_rows > page_size else None if bounded.truncated else False
        rows = bounded.rows[:page_size]
        result = PageResult(
            rows=rows,
            returned_rows=len(rows),
            truncated=more is not False,
            limit_reached="max_result_bytes" if bounded.limit_reached == "max_result_bytes" else "page_size" if more else None,
            execution_time_ms=bounded.execution_time_ms,
            timeout_seconds=bounded.timeout_seconds,
            database=state.database,
            total_returned_rows=state.total_returned_rows + len(rows),
            max_rows=state.max_rows,
            page_size=page_size,
            mode=state.mode,
            has_more=more,
            next_cursor=None,
            expires_in_seconds=0,
        )
        while True:
            capped = result.total_returned_rows == state.max_rows
            result.has_more = False if capped and more is not None else more
            continuing = not capped and result.has_more is not False
            # Store tokens are always 43 URL-safe ASCII characters, so replacement preserves encoded size.
            result.next_cursor = "x" * 43 if continuing else None
            result.expires_in_seconds = 300 if continuing else 0
            if capped and more is not False:
                result.limit_reached = "max_rows"
            try:
                text = encode_bounded_result(result, self._max_result_bytes).decode("utf-8")
                content = [types.TextContent(type="text", text=text)]
                response = types.CallToolResult(
                    content=list(content),
                    structuredContent={"result": [block.model_dump(mode="json", by_alias=True) for block in content]},
                )
                if len(response.model_dump_json(exclude_none=True).encode("utf-8")) <= self._max_result_bytes:
                    break
            except PublicToolError as exc:
                if exc.code != "RESULT_TOO_LARGE":
                    raise
            if len(result.rows) <= 1:
                raise PublicToolError("RESULT_TOO_LARGE", "The query result exceeds the response size limit.")
            result.rows.pop()
            result.returned_rows -= 1
            result.total_returned_rows -= 1
            result.truncated = True
            result.limit_reached = "max_result_bytes"
            more = True
        next_state = None
        result.text = text
        if continuing:
            next_state = replace(
                state,
                total_returned_rows=result.total_returned_rows,
                offset=state.offset + result.returned_rows,
                last_key=result.rows[-1][state.query.key_column] if state.mode == "keyset" else None,
            )
        return result, next_state
