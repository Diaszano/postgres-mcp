"""Characterize HypoPG locality on disposable PostgreSQL, using the MCP role."""

import psycopg
import pytest

from postgres_mcp.sql.sql_driver import DbConnPool
from postgres_mcp.sql.sql_driver import SqlDriver


class SessionAffinityMismatchError(AssertionError):
    """The expected baseline failure, separate from other assertion failures."""


def test_hypopg_visibility_is_session_local(hypopg_postgres):
    pg = hypopg_postgres
    uri = pg.uri(pg.mcp_role, "app_development")
    with psycopg.connect(uri, autocommit=True) as creator, psycopg.connect(uri, autocommit=True) as observer:
        creator_pid = creator.execute("SELECT pg_backend_pid()").fetchone()[0]
        observer_pid = observer.execute("SELECT pg_backend_pid()").fetchone()[0]
        assert creator_pid != observer_pid
        created = creator.execute("SELECT indexrelid FROM hypopg_create_index('CREATE INDEX ON development_marker (label)')").fetchone()[0]
        assert creator.execute("SELECT indexrelid FROM hypopg_list_indexes").fetchall() == [(created,)]
        assert observer.execute("SELECT indexrelid FROM hypopg_list_indexes").fetchall() == []
        observer.execute("SELECT hypopg_reset()")
        assert creator.execute("SELECT indexrelid FROM hypopg_list_indexes").fetchall() == [(created,)]
        creator.execute("SELECT hypopg_reset()")
        assert creator.execute("SELECT indexrelid FROM hypopg_list_indexes").fetchall() == []


@pytest.mark.asyncio
@pytest.mark.xfail(
    strict=True,
    raises=SessionAffinityMismatchError,
    reason="Independent pooled calls can use another backend, losing HypoPG create/list/explain/reset affinity",
)
async def test_tuning_flow_requires_single_backend_pid(hypopg_postgres):
    pg = hypopg_postgres
    manager = DbConnPool(pg.uri(pg.mcp_role, "app_development"), min_size=2, max_size=2)
    pool = await manager.pool_connect()
    try:
        await pool.wait()
        # An overlapping checkout keeps the creator busy, forcing independent calls onto another backend.
        async with pool.connection() as creator:
            pinned = SqlDriver(creator)
            created = await pinned.execute_query(
                "SELECT pg_backend_pid() AS pid, indexrelid FROM hypopg_create_index('CREATE INDEX ON development_marker (label)')"
            )
            independent = SqlDriver(manager)
            listed = await independent.execute_query("SELECT pg_backend_pid() AS pid, count(*) AS indexes FROM hypopg_list_indexes")
            explained = await independent.execute_query(
                "EXPLAIN SELECT * FROM development_marker WHERE label = 'app_development'; SELECT pg_backend_pid() AS pid"
            )
            reset = await independent.execute_query("SELECT pg_backend_pid() AS pid, hypopg_reset()")
            remaining = await pinned.execute_query("SELECT indexrelid FROM hypopg_list_indexes")
            assert listed[0].cells["indexes"] == 0
            assert remaining[0].cells["indexrelid"] == created[0].cells["indexrelid"]
            pids = {
                "create": created[0].cells["pid"],
                "list": listed[0].cells["pid"],
                "explain": explained[0].cells["pid"],
                "reset": reset[0].cells["pid"],
            }
            await pinned.execute_query("SELECT hypopg_reset()")
            if len(set(pids.values())) != 1:
                raise SessionAffinityMismatchError(f"Independent pooled calls break HypoPG session affinity: {pids}")
    finally:
        await manager.close()


def test_hypopg_image_is_mandatory(hypopg_postgres):
    with psycopg.connect(hypopg_postgres.uri(hypopg_postgres.mcp_role, "app_development")) as conn:
        assert conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'hypopg'").fetchone()
        assert conn.execute("SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname = current_user").fetchone() == (
            False,
            False,
            False,
        )
