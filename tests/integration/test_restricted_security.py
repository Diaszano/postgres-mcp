import asyncio

import psycopg
import pytest
from psycopg import sql

from pgscope.security.errors import SQLValidationError
from pgscope.sql import SafeSqlDriver
from pgscope.sql import SqlDriver
from tests.type_helpers import first_item


@pytest.fixture
def restricted_database(multidb_postgres):
    pg = multidb_postgres
    database = pg.visible_databases[0]
    with pg.admin(database) as admin:
        admin.execute("CREATE TABLE public.restricted_marker (id integer)")
        admin.execute("INSERT INTO public.restricted_marker VALUES (1)")
        admin.execute(sql.SQL("GRANT SELECT, INSERT ON public.restricted_marker TO {}").format(sql.Identifier(pg.mcp_role)))
    try:
        yield pg, database
    finally:
        with pg.admin(database) as admin:
            admin.execute("DROP FUNCTION IF EXISTS public.lower(character varying)")
            admin.execute("DROP OPERATOR IF EXISTS public.= (character varying, character varying)")
            admin.execute("DROP FUNCTION IF EXISTS public.restricted_equal(character varying, character varying)")
            admin.execute("DROP TABLE public.restricted_marker")


@pytest.mark.asyncio
async def test_restricted_does_not_trust_shadowed_functions(restricted_database):
    pg, database = restricted_database
    with pg.admin(database) as admin:
        admin.execute("CREATE FUNCTION public.lower(character varying) RETURNS text LANGUAGE sql AS $$ SELECT 'shadowed'::text $$")
        # PostgreSQL prefers the exact public overload despite pg_catalog coming first.
        assert first_item(admin.execute("SELECT lower('X'::varchar)").fetchone()) == "shadowed"
    async with await psycopg.AsyncConnection.connect(pg.uri(pg.mcp_role, database), autocommit=True) as connection:
        safe = SafeSqlDriver(SqlDriver(conn=connection))
        with pytest.raises(SQLValidationError):
            await safe.execute_query("SELECT lower('X'::varchar)")
        safe = SafeSqlDriver(SqlDriver(conn=connection))
        rows = await safe.execute_query("SELECT pg_catalog.lower('X'::varchar) AS value")
        assert first_item(rows).cells == {"value": "x"}
        assert first_item(await safe.execute_query("SELECT id FROM public.restricted_marker")).cells == {"id": 1}


@pytest.mark.asyncio
async def test_readonly_transaction_prevents_real_writes(restricted_database):
    pg, database = restricted_database
    async with await psycopg.AsyncConnection.connect(pg.uri(pg.mcp_role, database), autocommit=True) as connection:
        assert first_item(await (await connection.execute("SHOW is_superuser")).fetchone()) == "off"
        driver = SqlDriver(conn=connection)
        # Exercise the database barrier directly, bypassing AST rejection.
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            await driver.execute_query("INSERT INTO public.restricted_marker VALUES (2)", force_readonly=True)
        driver = SqlDriver(conn=connection)
        count = first_item(await driver.execute_query("SELECT count(*) AS count FROM public.restricted_marker", force_readonly=True))
        assert count.cells == {"count": 1}


@pytest.mark.asyncio
async def test_restricted_does_not_trust_shadowed_operators(restricted_database):
    pg, database = restricted_database
    with pg.admin(database) as admin:
        admin.execute(
            """
            CREATE FUNCTION public.restricted_equal(character varying, character varying)
            RETURNS boolean LANGUAGE plpgsql AS $$
            BEGIN
                PERFORM pg_catalog.pg_advisory_lock(6413403, 3);
                RETURN true;
            END
            $$
            """
        )
        admin.execute("CREATE OPERATOR public.= (FUNCTION = public.restricted_equal, LEFTARG = character varying, RIGHTARG = character varying)")
        # The exact public overload beats the catalog operator's implicit cast to text.
        admin.execute("BEGIN READ ONLY")
        assert first_item(admin.execute("SELECT 'a'::varchar = 'b'::varchar").fetchone()) is True
        admin.execute("ROLLBACK")
        with pg.admin(database) as observer:
            assert first_item(observer.execute("SELECT pg_catalog.pg_try_advisory_lock(6413403, 3)").fetchone()) is False
        admin.execute("SELECT pg_catalog.pg_advisory_unlock_all()")
    async with await psycopg.AsyncConnection.connect(pg.uri(pg.mcp_role, database), autocommit=True) as connection:
        safe = SafeSqlDriver(SqlDriver(conn=connection))
        with pytest.raises(SQLValidationError):
            await safe.execute_query("SELECT 'a'::varchar = 'b'::varchar")
        with pg.admin(database) as observer:
            assert first_item(observer.execute("SELECT pg_catalog.pg_try_advisory_lock(6413403, 3)").fetchone()) is True
        safe = SafeSqlDriver(SqlDriver(conn=connection))
        rows = await safe.execute_query("SELECT 'a'::varchar OPERATOR(pg_catalog.=) 'b'::varchar AS value")
        assert first_item(rows).cells == {"value": False}
        assert first_item(await safe.execute_query("SELECT id FROM public.restricted_marker")).cells == {"id": 1}


@pytest.mark.asyncio
async def test_legacy_select_still_works(restricted_database):
    pg, database = restricted_database
    async with await psycopg.AsyncConnection.connect(pg.uri(pg.mcp_role, database), autocommit=True) as connection:
        safe = SafeSqlDriver(SqlDriver(conn=connection))
        for table in ("public.restricted_marker", "restricted_marker"):
            rows = await safe.execute_query(f"SELECT id FROM {table}")
            assert first_item(rows).cells == {"id": 1}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "SELECT 'x'::public.restricted_domain",
        "SELECT 'x'::restricted_domain",
        "SELECT CAST('x' AS restricted_domain)",
        "SELECT '{x}'::restricted_domain[]",
    ],
)
async def test_restricted_rejects_domain_cast_without_side_effects(restricted_database, query):
    pg, database = restricted_database
    with pg.admin(database) as admin:
        admin.execute(
            """
            CREATE FUNCTION public.restricted_domain_check(text) RETURNS boolean LANGUAGE plpgsql AS $$
            BEGIN
                PERFORM pg_catalog.pg_advisory_lock(6413403, 4);
                RETURN true;
            END
            $$
            """
        )
        admin.execute("CREATE DOMAIN public.restricted_domain AS text CHECK (public.restricted_domain_check(VALUE))")
        try:
            admin.execute("BEGIN READ ONLY")
            assert first_item(admin.execute(query).fetchone()) is not None
            admin.execute("ROLLBACK")
            with pg.admin(database) as observer:
                assert first_item(observer.execute("SELECT pg_catalog.pg_try_advisory_lock(6413403, 4)").fetchone()) is False
            admin.execute("SELECT pg_catalog.pg_advisory_unlock_all()")
            async with await psycopg.AsyncConnection.connect(pg.uri(pg.mcp_role, database), autocommit=True) as connection:
                safe = SafeSqlDriver(SqlDriver(conn=connection))
                with pytest.raises(SQLValidationError):
                    await safe.execute_query(query)
                with pg.admin(database) as observer:
                    assert first_item(observer.execute("SELECT pg_catalog.pg_try_advisory_lock(6413403, 4)").fetchone()) is True
                safe = SafeSqlDriver(SqlDriver(conn=connection))
                rows = await safe.execute_query("SELECT id::pg_catalog.text AS value FROM public.restricted_marker")
                assert first_item(rows).cells == {"value": "1"}
        finally:
            admin.execute("DROP DOMAIN public.restricted_domain")
            admin.execute("DROP FUNCTION public.restricted_domain_check(text)")


@pytest.mark.asyncio
async def test_restricted_allows_verified_extension_function(restricted_database):
    pg, database = restricted_database
    with pg.admin(database) as admin:
        admin.execute("CREATE EXTENSION pg_trgm")
    try:
        async with await psycopg.AsyncConnection.connect(pg.uri(pg.mcp_role, database), autocommit=True) as connection:
            safe = SafeSqlDriver(SqlDriver(conn=connection))
            rows = await safe.execute_query("SELECT similarity('same', 'same') AS value")
            assert first_item(rows).cells == {"value": 1.0}
    finally:
        with pg.admin(database) as admin:
            admin.execute("DROP EXTENSION pg_trgm")


@pytest.mark.asyncio
async def test_cancelled_readonly_query_releases_transaction(restricted_database):
    pg, database = restricted_database
    async with await psycopg.AsyncConnection.connect(pg.uri(pg.mcp_role, database), autocommit=True) as connection:
        driver = SqlDriver(conn=connection)
        task = asyncio.create_task(driver.execute_query("SELECT pg_catalog.pg_sleep(30)", force_readonly=True))
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert first_item(await driver.execute_query("SELECT 1 AS value", force_readonly=True)).cells == {"value": 1}
