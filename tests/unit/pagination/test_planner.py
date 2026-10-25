import sqlite3

import pytest
from pglast import ast
from pglast import parse_sql

from postgres_mcp.pagination.eligibility import PageableQuery
from postgres_mcp.pagination.planner import build_page_query


def test_offset_pages_progress_in_order():
    with sqlite3.connect(":memory:") as conn:
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY)")
        conn.executemany("INSERT INTO items VALUES (?)", [(i,) for i in range(250, 0, -1)])
        query = PageableQuery("SELECT id FROM items ORDER BY id", "id")
        pages = []
        for offset in (0, 100, 200):
            plan = build_page_query(query, offset=offset, last_key=None, limit=100)
            pages.append(conn.execute(plan.sql.replace("%s", "?"), plan.params).fetchall())
    assert [len(page) for page in pages] == [100, 100, 50]
    assert [row[0] for page in pages for row in page] == list(range(1, 251))


def test_keyset_uses_bound_last_seen_value():
    marker = "'; DROP TABLE items; -- $1 %s"
    plan = build_page_query(PageableQuery("SELECT id FROM items ORDER BY id", "id"), offset=None, last_key=marker, limit=100)
    assert marker not in plan.sql
    assert plan.params == (marker, 100)
    statement = parse_sql(plan.sql.replace("%s", "$1"))[0].stmt
    assert isinstance(statement.whereClause.rexpr, ast.ParamRef)
    assert tuple(part.sval for part in statement.whereClause.name) == ("pg_catalog", ">")
    assert statement.sortClause[0].node.fields[0].sval == "id"


def test_existing_filter_preserved():
    query = PageableQuery("SELECT id FROM items WHERE active = true OR id = 2 ORDER BY id", "id")
    plan = build_page_query(query, offset=None, last_key=100, limit=10)
    statement = parse_sql(plan.sql.replace("%s", "$1"))[0].stmt
    assert statement.whereClause.boolop.name == "AND_EXPR"
    assert statement.whereClause.args[0].boolop.name == "OR_EXPR"
    assert len(statement.whereClause.args[0].args) == 2


def test_bad_identifiers_and_strings_are_safe():
    query = PageableQuery(
        '''SELECT "id; DROP TABLE items; --" FROM items
        WHERE label = '; -- $1 %s 50%' /* ; SELECT 'unsafe' */
        ORDER BY "id; DROP TABLE items; --"''',
        "id; DROP TABLE items; --",
    )
    plan = build_page_query(query, offset=None, last_key="bound", limit=10)
    assert '"id; DROP TABLE items; --"' in plan.sql
    assert "'; -- $1 %%s 50%%'" in plan.sql
    assert plan.params == ("bound", 10)


@pytest.mark.parametrize(
    "offset,last_key,limit",
    [(-1, None, 10), (0, 5, 10), (None, None, 0), (None, None, -1), (True, None, 10), (None, None, True)],
)
def test_invalid_page_bounds_rejected(offset, last_key, limit):
    with pytest.raises(ValueError):
        build_page_query(PageableQuery("SELECT id FROM items ORDER BY id", "id"), offset=offset, last_key=last_key, limit=limit)
