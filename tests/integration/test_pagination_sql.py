import pytest
from psycopg import sql

from postgres_mcp.pagination.eligibility import PageableQuery
from postgres_mcp.pagination.planner import build_page_query


@pytest.fixture
def pagination_connection(multidb_postgres):
    with multidb_postgres.admin("app_testing") as conn:
        conn.execute("CREATE TEMP TABLE pagination_items (id int PRIMARY KEY, active boolean, label text)")
        conn.execute("INSERT INTO pagination_items SELECT id, id % 2 = 0, '; -- $1 %s 50%' FROM generate_series(250, 1, -1) AS id")
        yield conn


def test_offset_pages_progress_in_order(pagination_connection):
    query = PageableQuery("SELECT id FROM pagination_items ORDER BY id", "id")
    pages = []
    for offset in (0, 100, 200):
        plan = build_page_query(query, offset=offset, last_key=None, limit=100)
        pages.append(pagination_connection.execute(plan.sql, plan.params).fetchall())
    assert [len(page) for page in pages] == [100, 100, 50]
    assert [row[0] for page in pages for row in page] == list(range(1, 251))


def test_keyset_uses_bound_last_seen_value(pagination_connection):
    query = PageableQuery("SELECT p.id FROM pagination_items AS p ORDER BY p.id ASC", "id")
    pages = []
    last_key = None
    for _ in range(3):
        plan = build_page_query(query, offset=None, last_key=last_key, limit=100)
        pages.append(pagination_connection.execute(plan.sql, plan.params).fetchall())
        last_key = pages[-1][-1][0]
    assert [len(page) for page in pages] == [100, 100, 50]
    assert [row[0] for page in pages for row in page] == list(range(1, 251))


@pytest.mark.parametrize("predicate", ["active = true", "active = true OR id = 1", "id % 2 = 0"])
def test_existing_filter_preserved(pagination_connection, predicate):
    query = PageableQuery(f"SELECT id FROM pagination_items WHERE {predicate} ORDER BY id", "id")
    plan = build_page_query(query, offset=None, last_key=100, limit=100)
    rows = pagination_connection.execute(plan.sql, plan.params).fetchall()
    assert [row[0] for row in rows] == list(range(102, 251, 2))


def test_bad_identifiers_and_strings_are_safe(pagination_connection):
    column = 'clé%s; DROP TABLE pagination_items; -- "'
    marker = "'; DROP TABLE pagination_items; -- $1 %s"
    pagination_connection.execute(sql.SQL("CREATE TEMP TABLE hostile ({key} text PRIMARY KEY)").format(key=sql.Identifier(column)))
    pagination_connection.execute("INSERT INTO hostile VALUES (%s)", (marker,))
    query = PageableQuery(
        sql.SQL("SELECT {key} FROM hostile WHERE {key} = {value} /* ; DROP TABLE hostile */ ORDER BY {key}")
        .format(key=sql.Identifier(column), value=sql.Literal(marker))
        .as_string(),
        column,
    )
    plan = build_page_query(query, offset=None, last_key="", limit=10)
    assert pagination_connection.execute(plan.sql, plan.params).fetchall() == [(marker,)]
    continuation = build_page_query(query, offset=None, last_key=marker, limit=10)
    assert pagination_connection.execute(continuation.sql, continuation.params).fetchall() == []
    assert pagination_connection.execute("SELECT count(*) FROM pagination_items").fetchone() == (250,)
    assert pagination_connection.execute("SELECT count(*) FROM hostile").fetchone() == (1,)


def test_literal_placeholder_text_preserved(pagination_connection):
    query = PageableQuery("SELECT id FROM pagination_items WHERE label = '; -- $1 %s 50%' ORDER BY id -- ; SELECT 1", "id")
    plan = build_page_query(query, offset=None, last_key=100, limit=2)
    assert pagination_connection.execute(plan.sql, plan.params).fetchall() == [(101,), (102,)]


def test_comparison_ignores_search_path_operator(pagination_connection):
    # A temporary operator shadows > unless the planner explicitly selects pg_catalog.
    schema = pagination_connection.execute("SELECT pg_my_temp_schema()::regnamespace::text").fetchone()[0]
    pagination_connection.execute(
        sql.SQL("CREATE OPERATOR {}.> (FUNCTION = pg_catalog.int4lt, LEFTARG = integer, RIGHTARG = integer)").format(sql.Identifier(schema))
    )
    pagination_connection.execute(sql.SQL("SET LOCAL search_path TO {}, pg_catalog").format(sql.Identifier(schema)))
    query = PageableQuery("SELECT id FROM pagination_items ORDER BY id", "id")
    plan = build_page_query(query, offset=None, last_key=248, limit=10)
    assert pagination_connection.execute(plan.sql, plan.params).fetchall() == [(249,), (250,)]
