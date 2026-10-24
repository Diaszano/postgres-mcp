"""Short-lived physical sessions for commands that share PostgreSQL session state."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from contextlib import asynccontextmanager

from psycopg.conninfo import conninfo_to_dict

from postgres_mcp.security.errors import DatabaseNotAllowedError

from .database_registry import DatabaseRegistry
from .sql_driver import DbConnPool
from .sql_driver import SqlDriver


@asynccontextmanager
async def database_session(
    database: str | None,
    *,
    restricted: bool,
    registry: DatabaseRegistry | None,
    bootstrap_pool: DbConnPool | None,
) -> AsyncIterator[SqlDriver]:
    """Hold one connection and transaction, retaining its pool lease until checkin."""
    stack = AsyncExitStack()
    driver = None
    try:
        if registry is not None:
            pool = await stack.enter_async_context(registry.acquire(database))
        else:
            if bootstrap_pool is None:
                raise RuntimeError("The bootstrap database pool is not initialized")
            if database is not None and database != conninfo_to_dict(bootstrap_pool.connection_url or "").get("dbname"):
                raise DatabaseNotAllowedError("Selecting another database requires DATABASE_AUTO_DISCOVER=true")
            pool = bootstrap_pool
        physical_pool = await pool.pool_connect()
        connection = await stack.enter_async_context(physical_pool.connection())

        async def rollback() -> None:
            if connection.closed:
                return
            try:
                await connection.rollback()
            except BaseException:
                # A connection with unknown transaction state must not be reused.
                await connection.close()
                raise

        stack.push_async_callback(rollback)
        async with connection.cursor() as cursor:
            await cursor.execute("BEGIN TRANSACTION READ ONLY" if restricted else "BEGIN")
            if restricted:
                await cursor.execute("SET TRANSACTION READ ONLY")
                await cursor.execute("SET LOCAL search_path = pg_catalog, public, pg_temp")
        driver = SqlDriver(conn=connection, owns_transaction=False)
        yield driver
    finally:
        if driver is not None:
            driver.conn = None
        # Cleanup includes checkin and lease release, so repeated cancellation cannot reorder them.
        cleanup = asyncio.create_task(stack.aclose())
        cancelled = False
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                cancelled = True
        cleanup.result()
        if cancelled:
            raise asyncio.CancelledError
