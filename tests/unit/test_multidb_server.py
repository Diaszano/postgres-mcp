import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from postgres_mcp.database_config import parse_database_config
from postgres_mcp.server import AccessMode
from postgres_mcp.server import get_sql_driver
from postgres_mcp.server import list_schemas
from postgres_mcp.sql import SafeSqlDriver
from postgres_mcp.sql import SqlDriver

BOOTSTRAP = "postgresql://user:s3cret@db.internal:5432/app_main"


class FakeRegistry:
    """Stands in for DatabaseRegistry.acquire: one pool per name, counted leases."""

    def __init__(self, default: str = "app_main") -> None:
        self.default = default
        self.pools: dict[str, MagicMock] = {}
        self.leases: dict[str, int] = {}
        self.requested: list[str | None] = []

    @asynccontextmanager
    async def acquire(self, database: str | None = None):
        self.requested.append(database)
        name = database if database is not None else self.default
        pool = self.pools.setdefault(name, MagicMock(name=f"pool-{name}"))
        self.leases[name] = self.leases.get(name, 0) + 1
        try:
            yield pool
        finally:
            self.leases[name] -= 1


def _config(auto_discover: bool):
    env = {"DATABASE_URI": BOOTSTRAP, "DATABASE_AUTO_DISCOVER": "true" if auto_discover else "false"}
    return parse_database_config(env, None, None)


@pytest.fixture
def discovery():
    registry = FakeRegistry()
    with (
        patch("postgres_mcp.server.database_config", _config(True)),
        patch("postgres_mcp.server.registry", registry),
        patch("postgres_mcp.server.current_access_mode", AccessMode.UNRESTRICTED),
    ):
        yield registry


@pytest.mark.asyncio
async def test_get_sql_driver_uses_selected_pool(discovery):
    async with get_sql_driver("app_testing") as driver:
        assert type(driver) is SqlDriver
        assert driver.conn is discovery.pools["app_testing"]
    async with get_sql_driver() as driver:
        assert driver.conn is discovery.pools["app_main"]
    assert discovery.requested == ["app_testing", None]


@pytest.mark.asyncio
async def test_get_sql_driver_restricted_wraps_safe_driver(discovery):
    with patch("postgres_mcp.server.current_access_mode", AccessMode.RESTRICTED):
        async with get_sql_driver("app_testing") as driver:
            assert isinstance(driver, SafeSqlDriver)
            assert driver.timeout == 30
            assert driver.sql_driver.conn is discovery.pools["app_testing"]


@pytest.mark.asyncio
async def test_sql_driver_keeps_lease_during_multiple_queries(discovery):
    seen: list[int] = []

    async def fake_execute(connection, query, params, force_readonly):
        seen.append(discovery.leases["app_testing"])
        await asyncio.sleep(0)
        return [SqlDriver.RowResult(cells={"ok": 1})]

    with patch.object(SqlDriver, "_execute_with_connection", AsyncMock(side_effect=fake_execute)):
        async with get_sql_driver("app_testing") as driver:
            await driver.execute_query("SELECT 1")
            await driver.execute_query("SELECT 2")
        assert seen == [1, 1]
        assert discovery.leases["app_testing"] == 0

        with pytest.raises(RuntimeError, match="boom"):
            async with get_sql_driver("app_testing") as driver:
                await driver.execute_query("SELECT 3")
                raise RuntimeError("boom")
        assert discovery.leases["app_testing"] == 0


@pytest.mark.asyncio
async def test_default_database_unaffected_by_parallel_calls(discovery):
    other_entered = asyncio.Event()
    release_other = asyncio.Event()

    async def use_other():
        async with get_sql_driver("app_testing") as driver:
            other_entered.set()
            await release_other.wait()
            return driver.conn

    task = asyncio.create_task(use_other())
    await other_entered.wait()
    async with get_sql_driver() as driver:
        assert driver.conn is discovery.pools["app_main"]
    release_other.set()
    assert await task is discovery.pools["app_testing"]
    async with get_sql_driver() as driver:
        assert driver.conn is discovery.pools["app_main"]


@pytest.mark.asyncio
async def test_tool_holds_lease_for_its_queries(discovery):
    seen: list[int] = []

    async def fake_execute(connection, query, params, force_readonly):
        seen.append(discovery.leases["app_main"])
        return [SqlDriver.RowResult(cells={"schema_name": "public"})]

    with patch.object(SqlDriver, "_execute_with_connection", AsyncMock(side_effect=fake_execute)):
        result = await list_schemas()
    assert "public" in result[0].text
    assert seen == [1]
    assert discovery.leases["app_main"] == 0


@pytest.mark.asyncio
async def test_restricted_tool_query_is_read_only(discovery):
    execute = AsyncMock(return_value=[SqlDriver.RowResult(cells={"schema_name": "public"})])
    with (
        patch("postgres_mcp.server.current_access_mode", AccessMode.RESTRICTED),
        patch.object(SqlDriver, "_execute_with_connection", execute),
    ):
        await list_schemas()
    assert execute.call_args.kwargs["force_readonly"] is True


@pytest.mark.parametrize("access_mode", [AccessMode.UNRESTRICTED, AccessMode.RESTRICTED])
@pytest.mark.asyncio
async def test_legacy_rejects_database_other_than_bootstrap(access_mode):
    registry = FakeRegistry()
    with (
        patch("postgres_mcp.server.database_config", _config(False)),
        patch("postgres_mcp.server.registry", registry),
        patch("postgres_mcp.server.current_access_mode", access_mode),
    ):
        with pytest.raises(ValueError) as excinfo:
            async with get_sql_driver("app_testing"):
                pytest.fail("legacy mode must not open another database")
    message = str(excinfo.value)
    assert "'app_testing'" in message
    assert "app_main" not in message and "s3cret" not in message and "db.internal" not in message
    assert registry.requested == []


@pytest.mark.asyncio
async def test_legacy_uses_bootstrap_pool_for_default_or_same_name():
    bootstrap_pool = MagicMock(name="bootstrap")
    registry = FakeRegistry()
    with (
        patch("postgres_mcp.server.database_config", _config(False)),
        patch("postgres_mcp.server.registry", registry),
        patch("postgres_mcp.server.db_connection", bootstrap_pool),
        patch("postgres_mcp.server.current_access_mode", AccessMode.RESTRICTED),
    ):
        for database in (None, "app_main"):
            async with get_sql_driver(database) as driver:
                assert isinstance(driver, SafeSqlDriver)
                assert driver.sql_driver.conn is bootstrap_pool
    assert registry.requested == []


@pytest.mark.asyncio
async def test_legacy_without_known_bootstrap_rejects_any_explicit_database():
    with (
        patch("postgres_mcp.server.database_config", None),
        patch("postgres_mcp.server.registry", None),
    ):
        with pytest.raises(ValueError, match="'postgres'"):
            async with get_sql_driver("postgres"):
                pass
