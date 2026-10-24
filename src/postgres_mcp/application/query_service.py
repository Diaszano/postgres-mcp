from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from pglast import parse_sql
from pglast.ast import SelectStmt
from pglast.parser import ParseError
from pglast.visitors import Visitor

from ..query_limits.policy import QueryLimits
from ..query_limits.results import BoundedQueryResult
from ..security.errors import PublicToolError
from ..sql import SqlDriver


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
    def __init__(self, get_driver: Callable[[str | None], AbstractAsyncContextManager[SqlDriver]], max_result_bytes: int):
        self._get_driver = get_driver
        self._max_result_bytes = max_result_bytes

    async def execute(self, sql: str, database: str | None, limits: QueryLimits) -> BoundedQueryResult:
        try:
            statements = parse_sql(sql)
        except ParseError as exc:
            raise _unsupported_query() from exc
        if len(statements) != 1 or not isinstance(statements[0].stmt, SelectStmt):
            raise _unsupported_query()
        _ReadOnlySelect()(statements)
        async with self._get_driver(database) as driver:
            return await driver.execute_bounded_query(
                sql,  # type: ignore[arg-type]
                max_rows=limits.max_rows,
                max_result_bytes=self._max_result_bytes,
                timeout_seconds=limits.timeout_seconds,
            )
