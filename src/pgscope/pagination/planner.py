"""Build bounded pages from an eligibility-checked SELECT."""

from dataclasses import dataclass

from pglast import ast
from pglast.enums import A_Expr_Kind
from pglast.enums import BoolExprType
from pglast.enums import LimitOption
from pglast.stream import RawStream

from ..sql.safe_sql import validate_single_select
from .eligibility import PageableQuery


@dataclass(frozen=True)
class PageQuery:
    sql: str
    params: tuple[object, ...]


class _PageStream(RawStream):
    def write(self, s):
        # psycopg parses percent signs even inside SQL literals and identifiers.
        return super().write(s.replace("%", "%%"))

    def print_node(self, node, *args, **kwargs):
        if isinstance(node, ast.ParamRef):
            super().write("%s")
        else:
            super().print_node(node, *args, **kwargs)


def build_page_query(query: PageableQuery, *, offset: int | None, last_key: object | None, limit: int) -> PageQuery:
    if type(limit) is not int or limit < 1:
        raise ValueError("Page limit must be a positive integer")
    if offset is not None and (type(offset) is not int or offset < 0 or last_key is not None):
        raise ValueError("Offset must be a non-negative integer without a last key")

    statement = validate_single_select(query.sql)
    params: list[object] = []
    if last_key is not None:
        assert statement.sortClause
        comparison = ast.A_Expr(
            kind=A_Expr_Kind.AEXPR_OP,
            name=(ast.String(sval="pg_catalog"), ast.String(sval=">")),
            lexpr=statement.sortClause[0].node,
            rexpr=ast.ParamRef(number=1),
        )
        statement.whereClause = (
            ast.BoolExpr(boolop=BoolExprType.AND_EXPR, args=(statement.whereClause, comparison)) if statement.whereClause else comparison
        )
        params.append(last_key)

    params.append(limit)
    statement.limitCount = ast.ParamRef(number=len(params))
    statement.limitOption = LimitOption.LIMIT_OPTION_COUNT
    if offset is not None:
        params.append(offset)
        statement.limitOffset = ast.ParamRef(number=len(params))
    return PageQuery(sql=_PageStream()(statement), params=tuple(params))
