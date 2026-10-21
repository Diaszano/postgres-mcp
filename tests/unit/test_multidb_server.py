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


# --- Task 10: list_databases, CLI defaults, startup ---

import json  # noqa: E402
import logging  # noqa: E402
import sys  # noqa: E402

from postgres_mcp import server  # noqa: E402
from postgres_mcp.sql.database_registry import DatabaseInfo  # noqa: E402


class _InfoRegistry:
    def __init__(self, infos=None, error: Exception | None = None):
        self.infos = infos or []
        self.error = error
        self.refreshes: list[bool] = []

    async def list_databases(self, *, refresh: bool = False):
        self.refreshes.append(refresh)
        if self.error:
            raise self.error
        return self.infos


@pytest.mark.asyncio
async def test_list_databases_reports_default_connection_state_stale():
    reg = _InfoRegistry([DatabaseInfo("app_testing", True, "not_connected", False)])
    with patch("postgres_mcp.server.database_config", _config(True)), patch("postgres_mcp.server.registry", reg):
        rows = json.loads((await server.list_databases(refresh=True))[0].text)
    assert [row["name"] for row in rows] == ["app_testing"]
    assert rows[0]["is_default"] is True
    assert rows[0]["connection_state"] == "not_connected"
    assert rows[0]["catalog_stale"] is False
    assert reg.refreshes == [True]


@pytest.mark.asyncio
async def test_list_databases_does_not_open_extra_pools():
    reg = FakeRegistry()
    reg.list_databases = _InfoRegistry([DatabaseInfo("a", True, "not_connected", False)]).list_databases
    with patch("postgres_mcp.server.database_config", _config(True)), patch("postgres_mcp.server.registry", reg):
        await server.list_databases()
    assert reg.pools == {} and reg.requested == []


@pytest.mark.asyncio
async def test_list_databases_error_is_reported_not_raised():
    reg = _InfoRegistry(error=RuntimeError("Database discovery is unavailable"))
    with patch("postgres_mcp.server.database_config", _config(True)), patch("postgres_mcp.server.registry", reg):
        text = (await server.list_databases())[0].text
    assert text == "Error: Database discovery is unavailable"


@pytest.mark.asyncio
async def test_list_databases_legacy_exposes_only_bootstrap():
    conn = MagicMock(is_valid=True)
    with patch("postgres_mcp.server.database_config", _config(False)), patch("postgres_mcp.server.db_connection", conn):
        rows = json.loads((await server.list_databases())[0].text)
    assert rows == [{"name": "app_main", "is_default": True, "connection_state": "connected", "catalog_stale": False}]


@pytest.mark.asyncio
async def test_list_databases_legacy_without_dbname_has_null_name():
    cfg = parse_database_config({"DATABASE_URI": "postgresql://u:p@h/"}, None, None)
    conn = MagicMock(is_valid=False)
    with patch("postgres_mcp.server.database_config", cfg), patch("postgres_mcp.server.db_connection", conn):
        rows = json.loads((await server.list_databases())[0].text)
    assert rows == [{"name": None, "is_default": True, "connection_state": "unavailable", "catalog_stale": False}]


def test_list_databases_is_registered_read_only():
    tool = next(t for t in server.mcp._tool_manager.list_tools() if t.name == "list_databases")
    assert tool.annotations.readOnlyHint is True
    assert [t.name for t in server.mcp._tool_manager.list_tools()].count("list_databases") == 1


async def _run_main(monkeypatch, argv, env):
    monkeypatch.setattr(sys, "argv", ["postgres_mcp", *argv])
    for key in list(__import__("os").environ):
        if key.startswith("DATABASE_"):
            monkeypatch.delenv(key)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    # main() mutates these globals; monkeypatch restores them afterwards.
    monkeypatch.setattr(server, "current_access_mode", server.current_access_mode)
    monkeypatch.setattr(server, "database_config", None)
    monkeypatch.setattr(server, "registry", None)
    with (
        patch("postgres_mcp.server.db_connection.pool_connect", AsyncMock()),
        patch("postgres_mcp.server.mcp.run_stdio_async", AsyncMock()),
        patch("postgres_mcp.server.DatabaseRegistry.start", AsyncMock()),
        patch("postgres_mcp.server.DatabaseRegistry.close_all", AsyncMock()),
    ):
        await server.main()


URI = {"DATABASE_URI": BOOTSTRAP}
DISCOVER = {**URI, "DATABASE_AUTO_DISCOVER": "true"}


@pytest.mark.asyncio
async def test_cli_legacy_default_is_unrestricted(monkeypatch):
    await _run_main(monkeypatch, [], URI)
    assert server.current_access_mode == AccessMode.UNRESTRICTED
    assert server.registry is None


@pytest.mark.asyncio
async def test_cli_legacy_positional_url_still_works(monkeypatch):
    await _run_main(monkeypatch, [BOOTSTRAP], {})
    assert server.database_config.bootstrap_uri == BOOTSTRAP


@pytest.mark.asyncio
async def test_cli_discovery_default_is_restricted(monkeypatch):
    await _run_main(monkeypatch, [], DISCOVER)
    assert server.current_access_mode == AccessMode.RESTRICTED
    assert server.registry is not None


@pytest.mark.asyncio
async def test_cli_discovery_explicit_restricted(monkeypatch):
    await _run_main(monkeypatch, ["--access-mode=restricted"], DISCOVER)
    assert server.current_access_mode == AccessMode.RESTRICTED


@pytest.mark.asyncio
async def test_cli_explicit_unrestricted_warns(monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger="postgres_mcp.server"):
        await _run_main(monkeypatch, ["--access-mode=unrestricted"], DISCOVER)
    assert server.current_access_mode == AccessMode.UNRESTRICTED
    assert any("unrestricted" in r.getMessage().lower() and r.levelno == logging.WARNING for r in caplog.records)
    assert "s3cret" not in caplog.text


@pytest.mark.asyncio
async def test_cli_legacy_explicit_unrestricted_does_not_warn(monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger="postgres_mcp.server"):
        await _run_main(monkeypatch, ["--access-mode=unrestricted"], URI)
    assert [r for r in caplog.records if r.name == "postgres_mcp.server"] == []


@pytest.mark.asyncio
async def test_startup_config_error_denying_default_is_not_masked(monkeypatch):
    env = {**DISCOVER, "DATABASE_EXCLUDED_DATABASES": "app_main"}
    with pytest.raises(ValueError, match="excluded"):
        await _run_main(monkeypatch, [], env)


@pytest.mark.asyncio
async def test_startup_discovery_without_dbname_fails(monkeypatch):
    with pytest.raises(ValueError, match="DATABASE_DEFAULT_DATABASE"):
        await _run_main(monkeypatch, [], {"DATABASE_URI": "postgresql://u:p@h/", "DATABASE_AUTO_DISCOVER": "true"})


@pytest.mark.asyncio
async def test_startup_degraded_does_not_list_falsely(monkeypatch):
    async def down(_uri):
        raise OSError("boom s3cret")

    monkeypatch.setattr(sys, "argv", ["postgres_mcp"])
    monkeypatch.setenv("DATABASE_URI", BOOTSTRAP)
    monkeypatch.setenv("DATABASE_AUTO_DISCOVER", "true")
    monkeypatch.setattr(server, "registry", None)
    monkeypatch.setattr(server, "database_config", None)
    monkeypatch.setattr(server, "current_access_mode", server.current_access_mode)
    # Catalog default arg binds the original function at import; patch the registry's catalog factory instead.
    from postgres_mcp.sql import database_catalog

    real_init = database_catalog.DatabaseCatalog.__init__

    def init(self, config, discover=down, clock=None):
        real_init(self, config, discover, clock)

    with patch.object(database_catalog.DatabaseCatalog, "__init__", init), patch("postgres_mcp.server.mcp.run_stdio_async", AsyncMock()):
        await server.main()
        assert server.registry is not None
        text = (await server.list_databases())[0].text
    assert text == "Error: Database discovery is unavailable"
