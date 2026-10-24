import asyncio
from contextlib import asynccontextmanager

import pytest

from postgres_mcp.database_config import DatabaseConfig
from postgres_mcp.security.errors import DatabaseNotAllowedError
from postgres_mcp.sql.database_catalog import DatabaseCatalog
from postgres_mcp.sql.database_registry import DatabaseRegistry
from postgres_mcp.sql.database_registry import PoolCapacityError
from postgres_mcp.sql.database_session import database_session as session
from postgres_mcp.sql.sql_driver import DbConnPool


class Connection:
    def __init__(self):
        self.commands = []
        self.transaction = False
        self.readonly = False
        self.rollbacks = 0
        self.closed = False
        self.rollback_started = asyncio.Event()
        self.rollback_gate = None
        self.rollback_error = None
        self.fail_command = "FAIL"

    @asynccontextmanager
    async def cursor(self, **kwargs):
        yield Cursor(self)

    async def rollback(self):
        self.rollback_started.set()
        if self.rollback_gate is not None:
            await self.rollback_gate.wait()
        if self.rollback_error is not None:
            raise self.rollback_error
        self.rollbacks += 1
        self.transaction = False
        self.readonly = False

    async def close(self):
        self.closed = True


class Cursor:
    description = ("pid",)

    def __init__(self, connection):
        self.connection = connection
        self.fetched = False

    async def execute(self, query, params=None):
        self.connection.commands.append(query)
        self.description = None if query == "NO ROWS" else ("pid",)
        if query.startswith("BEGIN"):
            assert not self.connection.transaction, "nested transaction boundary"
            self.connection.transaction = True
            self.connection.readonly = "READ ONLY" in query
        elif query in {"COMMIT", "ROLLBACK"}:
            self.connection.transaction = False
        elif query == self.connection.fail_command:
            raise ValueError("query failed")

    def nextset(self):
        return None

    async def fetchall(self):
        return [{"pid": id(self.connection)}]

    async def fetchmany(self, count):
        if self.fetched:
            return []
        self.fetched = True
        return await self.fetchall()


class Pool(DbConnPool):
    def __init__(self):
        super().__init__()
        self.backend = Connection()
        self.checkouts = 0
        self.active = 0
        self.checkins = 0
        self.closed = False
        self.on_checkin = lambda: None
        self.checkout_started = asyncio.Event()
        self.checkout_gate = None

    async def pool_connect(self):
        return self

    @asynccontextmanager
    async def connection(self):
        self.checkout_started.set()
        if self.checkout_gate is not None:
            await self.checkout_gate.wait()
        assert self.active == 0, "nested checkout would deadlock a size-one pool"
        self.checkouts += 1
        self.active += 1
        try:
            yield self.backend
        finally:
            assert not self.backend.transaction or self.backend.closed
            self.on_checkin()
            self.active -= 1
            self.checkins += 1

    async def close(self):
        assert not self.active, "pool closed before physical session ended"
        self.closed = True


def registry_for(pools):
    config = DatabaseConfig(
        bootstrap_uri="postgresql://localhost/app",
        auto_discover=True,
        default_database="app",
        allowed_databases=(),
        excluded_databases=(),
        discovery_ttl_seconds=60,
        max_pools=1,
        pool_max_size=1,
        pool_idle_seconds=600,
        access_mode="restricted",
    )

    async def discover(_uri):
        return set(pools)

    return DatabaseRegistry(config, DatabaseCatalog(config, discover=discover), pool_factory=pools.__getitem__)


@pytest.mark.asyncio
async def test_one_backend_connection_for_multiple_commands():
    pool = Pool()
    async with session(None, restricted=False, registry=None, bootstrap_pool=pool) as driver:
        first = await driver.execute_query("SELECT pg_backend_pid()")
        second = await driver.execute_query("SELECT pg_backend_pid()")
        assert first == second
        assert first[0].cells == {"pid": id(pool.backend)}
        assert pool.checkouts == 1
    assert pool.checkins == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("restricted", [False, True])
async def test_session_owns_transaction_boundary(restricted):
    pool = Pool()
    async with session(None, restricted=restricted, registry=None, bootstrap_pool=pool) as driver:
        await driver.execute_query("SELECT 1", force_readonly=restricted)
        assert await driver.execute_query("NO ROWS") is None
        await driver.execute_query("SELECT 2")
        assert pool.backend.transaction
        assert pool.backend.readonly is restricted
        assert pool.backend.commands.count("BEGIN TRANSACTION READ ONLY" if restricted else "BEGIN") == 1
        assert "COMMIT" not in pool.backend.commands
        assert "ROLLBACK" not in pool.backend.commands
    assert pool.backend.rollbacks == 1


@pytest.mark.asyncio
async def test_bounded_query_keeps_session_transaction_open():
    pool = Pool()
    async with session(None, restricted=True, registry=None, bootstrap_pool=pool) as driver:
        result = await driver.execute_bounded_query("SELECT 1", max_rows=10, max_result_bytes=1024, timeout_seconds=30)
        assert result.returned_rows == 1
        assert pool.backend.transaction
        assert pool.backend.readonly
        assert pool.backend.commands.count("BEGIN TRANSACTION READ ONLY") == 1
    assert pool.backend.rollbacks == 1


@pytest.mark.asyncio
async def test_driver_cannot_use_connection_after_checkin():
    pool = Pool()
    async with session(None, restricted=False, registry=None, bootstrap_pool=pool) as driver:
        await driver.execute_query("SELECT 1")
    with pytest.raises(ValueError, match="session is closed"):
        await driver.execute_query("SELECT 2")
    assert "SELECT 2" not in pool.backend.commands


@pytest.mark.asyncio
async def test_legacy_database_selection_uses_bootstrap_database():
    pool = Pool()
    pool.connection_url = "postgresql://localhost/app"
    async with session("app", restricted=True, registry=None, bootstrap_pool=pool):
        pass
    with pytest.raises(DatabaseNotAllowedError):
        async with session("other", restricted=True, registry=None, bootstrap_pool=pool):
            pytest.fail("legacy sessions must not select another database")
    assert pool.checkouts == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("ending", ["success", "error", "cancel", "shutdown"])
async def test_release_on_error_cancel_shutdown(ending):
    pool = Pool()
    registry = registry_for({"app": pool})
    entered = asyncio.Event()
    finish = asyncio.Event()

    async def use():
        async with session("app", restricted=True, registry=registry, bootstrap_pool=None) as driver:
            await driver.execute_query("SELECT 1")
            entered.set()
            await finish.wait()
            if ending == "error":
                await driver.execute_query("FAIL")

    task = asyncio.create_task(use())
    await entered.wait()
    shutdown = asyncio.create_task(registry.close_all()) if ending == "shutdown" else None
    if shutdown is not None:
        await asyncio.sleep(0)
        assert not pool.closed
    if ending == "cancel":
        task.cancel()
    else:
        finish.set()
    if ending in {"error", "cancel"}:
        with pytest.raises(ValueError if ending == "error" else asyncio.CancelledError):
            await task
    else:
        await task
    if shutdown is not None:
        await shutdown
        assert pool.closed
    assert pool.backend.rollbacks == 1
    assert not pool.backend.transaction
    assert pool.checkins == 1
    assert registry.active_leases("app") == 0
    await registry.close_all()


@pytest.mark.asyncio
async def test_registry_lease_outlives_physical_session():
    pool, other = Pool(), Pool()
    registry = registry_for({"app": pool, "other": other})
    pool.on_checkin = lambda: assert_lease(registry)
    async with session("app", restricted=False, registry=registry, bootstrap_pool=None) as driver:
        await driver.execute_query("SELECT 1")
        with pytest.raises(PoolCapacityError):
            async with registry.acquire("other"):
                pytest.fail("a leased pool must not be evicted")
        assert not pool.closed
    assert registry.active_leases("app") == 0
    async with registry.acquire("other"):
        assert pool.closed
    await registry.close_all()


def assert_lease(registry):
    assert registry.active_leases("app") == 1


@pytest.mark.asyncio
async def test_repeated_cancellation_does_not_release_lease_before_cleanup():
    pool = Pool()
    pool.backend.rollback_gate = asyncio.Event()
    registry = registry_for({"app": pool})
    entered = asyncio.Event()

    async def use():
        async with session("app", restricted=False, registry=registry, bootstrap_pool=None):
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(use())
    await entered.wait()
    task.cancel()
    await pool.backend.rollback_started.wait()
    task.cancel()
    await asyncio.sleep(0)
    assert registry.active_leases("app") == 1
    assert pool.active == 1
    pool.backend.rollback_gate.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert registry.active_leases("app") == 0
    assert pool.checkins == 1
    await registry.close_all()


@pytest.mark.asyncio
async def test_rollback_failure_discards_connection_and_releases_lease():
    pool = Pool()
    pool.backend.rollback_error = ValueError("rollback failed")
    registry = registry_for({"app": pool})
    with pytest.raises(ValueError, match="rollback failed"):
        async with session("app", restricted=False, registry=registry, bootstrap_pool=None):
            pass
    assert pool.backend.closed
    assert pool.checkins == 1
    assert registry.active_leases("app") == 0
    await registry.close_all()


@pytest.mark.asyncio
async def test_setup_failure_rolls_back_and_releases_lease():
    pool = Pool()
    pool.backend.fail_command = "SET TRANSACTION READ ONLY"
    registry = registry_for({"app": pool})
    with pytest.raises(ValueError, match="query failed"):
        async with session("app", restricted=True, registry=registry, bootstrap_pool=None):
            pytest.fail("a failed session setup must not yield a driver")
    assert pool.backend.rollbacks == 1
    assert pool.checkins == 1
    assert registry.active_leases("app") == 0
    await registry.close_all()


@pytest.mark.asyncio
async def test_cancelled_checkout_releases_registry_lease():
    pool = Pool()
    pool.checkout_gate = asyncio.Event()
    registry = registry_for({"app": pool})

    async def use():
        async with session("app", restricted=True, registry=registry, bootstrap_pool=None):
            pytest.fail("a cancelled checkout must not yield a driver")

    task = asyncio.create_task(use())
    await pool.checkout_started.wait()
    assert registry.active_leases("app") == 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert registry.active_leases("app") == 0
    assert pool.active == 0
    await registry.close_all()
