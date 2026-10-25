"""Conservative SQL eligibility for deterministic pagination."""

from dataclasses import dataclass
from typing import Literal

from pglast import ast
from pglast.enums import SetOperation
from pglast.enums import SortByDir
from pglast.enums import SortByNulls
from pglast.stream import RawStream
from psycopg.sql import Identifier

from ..security.errors import SQLValidationError
from ..sql.safe_sql import SafeSqlDriver
from ..sql.safe_sql import validate_single_select
from ..sql.sql_driver import SqlDriver


@dataclass(frozen=True)
class PageableQuery:
    sql: str
    key_column: str


_ALLOWED_NODES = {
    ast.SelectStmt,
    ast.ResTarget,
    ast.RangeVar,
    ast.Alias,
    ast.ColumnRef,
    ast.String,
    ast.A_Star,
    ast.SortBy,
    ast.A_Expr,
    ast.A_Const,
    ast.Integer,
    ast.Float,
    ast.Boolean,
    ast.BoolExpr,
    ast.NullTest,
    ast.BooleanTest,
}


def _check_nodes(node: ast.Node) -> None:
    if type(node) not in _ALLOWED_NODES:
        raise SQLValidationError("Unsupported pagination expression")
    for name in node:
        value = getattr(node, name)
        if isinstance(value, ast.Node):
            _check_nodes(value)
        elif isinstance(value, tuple):
            for child in value:
                if isinstance(child, ast.Node):
                    _check_nodes(child)


def _column_name(node: ast.Node, relation: ast.RangeVar) -> str | None:
    if not isinstance(node, ast.ColumnRef) or not node.fields or any(not isinstance(field, ast.String) for field in node.fields):
        return None
    names = tuple(field.sval for field in node.fields)
    qualifier = relation.alias.aliasname if relation.alias else relation.relname
    if len(names) == 1 or (len(names) == 2 and names[0] == qualifier):
        return names[-1]
    if not relation.alias and len(names) == 3 and names[:2] == (relation.schemaname, relation.relname):
        return names[-1]
    return None


async def inspect_pageable_select(sql: str, mode: Literal["offset", "keyset"], sql_driver: SqlDriver) -> PageableQuery:
    statement = validate_single_select(sql)
    if mode not in {"offset", "keyset"}:
        raise SQLValidationError("Unsupported pagination mode")
    if (
        any(
            getattr(statement, name)
            for name in (
                "distinctClause",
                "intoClause",
                "groupClause",
                "groupDistinct",
                "havingClause",
                "windowClause",
                "valuesLists",
                "limitOffset",
                "limitCount",
                "lockingClause",
                "withClause",
            )
        )
        or statement.op != SetOperation.SETOP_NONE
        or statement.all
        or statement.larg
        or statement.rarg
        or not statement.fromClause
        or len(statement.fromClause) != 1
        or not isinstance(statement.fromClause[0], ast.RangeVar)
        or not statement.sortClause
        or len(statement.sortClause) != 1
    ):
        raise SQLValidationError("Unsupported pagination SELECT shape")
    relation = statement.fromClause[0]
    if relation.catalogname or (relation.alias and relation.alias.colnames):
        raise SQLValidationError("Unsupported pagination relation")
    _check_nodes(statement)
    order = statement.sortClause[0]
    key = _column_name(order.node, relation)
    if (
        key is None
        or order.sortby_dir not in {SortByDir.SORTBY_DEFAULT, SortByDir.SORTBY_ASC}
        or order.sortby_nulls != SortByNulls.SORTBY_NULLS_DEFAULT
        or order.useOp
    ):
        raise SQLValidationError("Pagination requires one ascending column")
    projected = False
    for target in statement.targetList or ():
        name = _column_name(target.val, relation)
        if target.name or (
            name is None
            and not (
                isinstance(target.val, ast.ColumnRef)
                and target.val.fields
                and len(target.val.fields) == 1
                and isinstance(target.val.fields[0], ast.A_Star)
            )
        ):
            raise SQLValidationError("Pagination requires unaliased column projections")
        projected |= name == key or name is None
    if not projected:
        raise SQLValidationError("Pagination key must be projected")

    relation_name = Identifier(*([relation.schemaname] if relation.schemaname else []), relation.relname).as_string()
    query = SafeSqlDriver.param_sql_to_query(
        """SELECT EXISTS (
            SELECT 1 FROM pg_catalog.pg_class AS c
            JOIN pg_catalog.pg_attribute AS a ON a.attrelid = c.oid
            JOIN pg_catalog.pg_index AS i ON i.indrelid = c.oid AND i.indkey[0] = a.attnum
            JOIN pg_catalog.pg_opclass AS o ON o.oid = i.indclass[0]
            JOIN pg_catalog.pg_am AS m ON m.oid = o.opcmethod
            WHERE c.oid = pg_catalog.to_regclass({}) AND a.attname = {}
                AND c.relkind = 'r' AND a.attnotnull AND NOT a.attisdropped
                AND i.indisunique AND i.indisvalid AND i.indisready AND i.indimmediate
                AND i.indnkeyatts = 1 AND i.indexprs IS NULL AND i.indpred IS NULL
                AND i.indcollation[0] = a.attcollation AND o.opcdefault AND m.amname = 'btree'
                AND o.opcnamespace = 'pg_catalog'::pg_catalog.regnamespace
                AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_inherits AS h WHERE h.inhparent = c.oid)
        ) AS verified""",
        [relation_name, key],
    )
    rows = await sql_driver.execute_query(query, force_readonly=True)  # type: ignore[arg-type]
    if not rows or len(rows) != 1 or rows[0].cells.get("verified") is not True:
        raise SQLValidationError("Pagination requires a verified unique non-null ordering key")
    return PageableQuery(sql=RawStream()(statement), key_column=key)
