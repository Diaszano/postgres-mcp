from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any
from typing import Literal

from pglast import parse_sql
from pglast.ast import SelectStmt
from pglast.parser import ParseError
from pglast.visitors import Visitor

from ..observability.metrics import MetricsSink
from ..observability.metrics import NoopMetrics
from ..pagination.eligibility import PageableQuery
from ..pagination.eligibility import inspect_pageable_select
from ..pagination.planner import PageQuery
from ..query_limits.policy import QueryLimits
from ..query_limits.results import BoundedQueryResult
from ..security.errors import PublicToolError
from ..sql import SqlDriver
from ..sql.sql_driver import query_for_validation


def _unsupported_query() -> PublicToolError:
    return PublicToolError("SQL_VALIDATION_FAILED", "Query guardrails require a single read-only SELECT statement.")


class _ReadOnlySelect(Visitor):
    def visit_SelectStmt(self, ancestors, node):  # noqa: N802
        if node.intoClause or node.lockingClause:
            raise _unsupported_query()

    def visit_CommonTableExpr(self, ancestors, node):  # noqa: N802
        if not isinstance(node.ctequery, SelectStmt):
            raise _unsupported_query()


class QueryExecutionService:
    def __init__(
        self,
        get_driver: Callable[[str | None], AbstractAsyncContextManager[SqlDriver]],
        max_result_bytes: int,
        metrics: MetricsSink | None = None,
    ):
        self._get_driver = get_driver
        self._max_result_bytes = max_result_bytes
        self.metrics = metrics or NoopMetrics()

    async def inspect_pageable(self, sql: str, database: str | None, mode: Literal["offset", "keyset"]) -> PageableQuery:
        async with self._get_driver(database) as driver:
            return await inspect_pageable_select(sql, mode, driver)

    async def execute_page(self, query: PageQuery, database: str | None, limits: QueryLimits) -> BoundedQueryResult:
        return await self.execute(query.sql, database, limits, params=query.params)

    async def execute(self, sql: str, database: str | None, limits: QueryLimits, *, params: tuple[object, ...] | None = None) -> BoundedQueryResult:
        try:
            statements = parse_sql(query_for_validation(sql, params))
        except ParseError as exc:
            self.metrics.record_query(0.0, outcome="validation_failed", mode="unrestricted")
            raise _unsupported_query() from exc
        if len(statements) != 1 or not isinstance(statements[0].stmt, SelectStmt):
            self.metrics.record_query(0.0, outcome="validation_failed", mode="unrestricted")
            raise _unsupported_query()
        _ReadOnlySelect()(statements)
        async with self._get_driver(database) as driver:
            options: dict[str, Any] = {"params": params} if params is not None else {}
            res = await driver.execute_bounded_query(
                sql,  # type: ignore[arg-type]
                max_rows=limits.max_rows,
                max_result_bytes=self._max_result_bytes,
                timeout_seconds=limits.timeout_seconds,
                **options,
            )
            self.metrics.record_query(res.execution_time_ms / 1000.0, outcome="success", mode="unrestricted")
            return res
