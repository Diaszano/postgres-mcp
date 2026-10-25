import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from postgres_mcp.database_config import parse_database_config
from postgres_mcp.security.errors import DatabaseNotAllowedError
from postgres_mcp.server import AccessMode
from postgres_mcp.server import get_object_details
from postgres_mcp.server import get_sql_driver
from postgres_mcp.server import list_objects
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
    assert "DATABASE_AUTO_DISCOVER=true" in message
    assert "app_testing" not in message
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
        with pytest.raises(DatabaseNotAllowedError) as exc:
            async with get_sql_driver("postgres"):
                pass
        assert "postgres" not in str(exc.value)


# --- Task 11: schema tools routed to the selected database ---

_CATALOG_KEYS = (
    "schema_name",
    "table_schema",
    "table_name",
    "table_type",
    "sequence_schema",
    "sequence_name",
    "data_type",
    "start_value",
    "increment",
)


def _catalog_execute(registry: FakeRegistry, calls: list[str]):
    """Fake _execute_with_connection: every row carries the name of the pool it was asked on."""

    async def fake(connection, query, params, force_readonly):
        name = next(n for n, pool in registry.pools.items() if pool is connection)
        calls.append(name)
        return [SqlDriver.RowResult(cells={key: f"cat_{name}" for key in _CATALOG_KEYS})]

    return AsyncMock(side_effect=fake)


_SCHEMA_TOOL_CALLS = [
    ("list_schemas", lambda db: list_schemas(database=db)),
    ("list_objects", lambda db: list_objects("public", "table", database=db)),
    ("get_object_details", lambda db: get_object_details("public", "s", "sequence", database=db)),
]


@pytest.mark.parametrize("call", [c for _, c in _SCHEMA_TOOL_CALLS], ids=[n for n, _ in _SCHEMA_TOOL_CALLS])
@pytest.mark.asyncio
async def test_schema_tools_use_selected_database(discovery, call):
    calls: list[str] = []
    with patch.object(SqlDriver, "_execute_with_connection", _catalog_execute(discovery, calls)):
        selected = (await call("app_testing"))[0].text
        default = (await call(None))[0].text
    assert "cat_app_testing" in selected and "cat_app_main" not in selected
    assert "cat_app_main" in default and "cat_app_testing" not in default
    assert discovery.requested == ["app_testing", None]
    assert set(calls) == {"app_testing", "app_main"}
    assert discovery.leases == {"app_testing": 0, "app_main": 0}


@pytest.mark.asyncio
async def test_legacy_positional_calls_still_work():
    bootstrap_pool = MagicMock(name="bootstrap")
    registry = FakeRegistry()
    registry.pools["app_main"] = bootstrap_pool
    calls: list[str] = []
    with (
        patch("postgres_mcp.server.database_config", _config(False)),
        patch("postgres_mcp.server.registry", registry),
        patch("postgres_mcp.server.db_connection", bootstrap_pool),
        patch("postgres_mcp.server.current_access_mode", AccessMode.UNRESTRICTED),
        patch.object(SqlDriver, "_execute_with_connection", _catalog_execute(registry, calls)),
    ):
        schemas = (await list_schemas())[0].text
        objects = (await list_objects("public", "sequence"))[0].text
        details = (await get_object_details("public", "s", "sequence"))[0].text
        explicit = (await list_schemas("app_main"))[0].text
    assert all("cat_app_main" in text for text in (schemas, objects, details, explicit))
    assert calls == ["app_main"] * 4
    assert registry.requested == []


@pytest.mark.parametrize("call", [c for _, c in _SCHEMA_TOOL_CALLS], ids=[n for n, _ in _SCHEMA_TOOL_CALLS])
@pytest.mark.asyncio
async def test_denied_database_never_queries(discovery, call):
    class Denying(FakeRegistry):
        @asynccontextmanager
        async def acquire(self, database=None):
            if database == "secret_db":
                raise DatabaseNotAllowedError("Database 'secret_db' is not available")
            async with super().acquire(database) as pool:
                yield pool

    denying = Denying()
    execute = AsyncMock()
    with patch("postgres_mcp.server.registry", denying), patch.object(SqlDriver, "_execute_with_connection", execute):
        text = (await call("secret_db"))[0].text
    assert text == "Error: The requested database is not available."
    assert "secret_db" not in text
    execute.assert_not_called()
    assert denying.pools == {}


@pytest.mark.parametrize("call", [c for _, c in _SCHEMA_TOOL_CALLS], ids=[n for n, _ in _SCHEMA_TOOL_CALLS])
@pytest.mark.asyncio
async def test_legacy_denied_database_never_queries_via_tools(call):
    execute = AsyncMock()
    with (
        patch("postgres_mcp.server.database_config", _config(False)),
        patch("postgres_mcp.server.db_connection", MagicMock()),
        patch.object(SqlDriver, "_execute_with_connection", execute),
    ):
        text = (await call("app_testing"))[0].text
    assert text == "Error: The requested database is not available."
    assert "app_testing" not in text
    execute.assert_not_called()


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
    assert text == "Error: The operation failed."
    assert "Database discovery is unavailable" not in text


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
    assert text == "Error: The database is temporarily unavailable."
    assert "boom s3cret" not in text


# --- Task 12: execute_sql and explain_query routed to the selected database ---

from postgres_mcp.server import execute_sql  # noqa: E402
from postgres_mcp.server import explain_query  # noqa: E402

_PLAN = {"Plan": {"Node Type": "Result", "Startup Cost": 0.0, "Total Cost": 0.01, "Plan Rows": 1, "Plan Width": 4}}


def _routing_execute(registry: FakeRegistry, calls: list[tuple[str, str]]):
    """Fake _execute_with_connection: records (pool name, query) and tags rows with the pool name."""

    async def fake(connection, query, params, force_readonly):
        name = next(n for n, pool in registry.pools.items() if pool is connection)
        calls.append((name, query))
        return [SqlDriver.RowResult(cells={"db": f"cat_{name}", "extversion": "1.4", "QUERY PLAN": [_PLAN]})]

    return AsyncMock(side_effect=fake)


@pytest.mark.asyncio
async def test_execute_sql_routes_by_database(discovery):
    calls: list[tuple[str, str]] = []
    with patch.object(SqlDriver, "_execute_with_connection", _routing_execute(discovery, calls)):
        selected = (await execute_sql(sql="SELECT current_database() AS db", database="app_testing"))[0].text
        default = (await execute_sql(sql="SELECT current_database() AS db"))[0].text
    assert "cat_app_testing" in selected and "cat_app_main" not in selected
    assert "cat_app_main" in default and "cat_app_testing" not in default
    assert [name for name, _ in calls] == ["app_testing", "app_main"]
    assert discovery.requested == ["app_testing", None]
    assert discovery.leases == {"app_testing": 0, "app_main": 0}


@pytest.mark.asyncio
@pytest.mark.parametrize("access_mode", [AccessMode.RESTRICTED, AccessMode.UNRESTRICTED])
async def test_database_selection_and_access_mode_unchanged(discovery, monkeypatch, access_mode):
    from postgres_mcp.query_limits.config import QueryBudgetConfig
    from postgres_mcp.query_limits.results import BoundedQueryResult

    monkeypatch.setattr(server, "query_budget_config", QueryBudgetConfig(enabled=True))
    monkeypatch.setattr(server, "current_access_mode", access_mode)
    calls = []

    async def bounded(driver, query, **limits):
        name = next(name for name, pool in discovery.pools.items() if pool is driver.conn)
        assert discovery.leases[name] == 1
        calls.append(name)
        return BoundedQueryResult([{"db": name}], 1, False, None, 0, limits["timeout_seconds"])

    with patch.object(SqlDriver, "execute_bounded_query", bounded):
        selected = (await execute_sql("SELECT current_database()", "app_testing"))[0].text
        default = (await execute_sql("SELECT current_database()"))[0].text
        if access_mode == AccessMode.RESTRICTED:
            assert "not allowed" in (await execute_sql("SELECT secret_function()"))[0].text
    assert '"db":"app_testing"' in selected
    assert '"db":"app_main"' in default
    assert calls == ["app_testing", "app_main"]
    assert discovery.leases == {"app_testing": 0, "app_main": 0}


@pytest.mark.asyncio
async def test_guarded_unknown_database_never_falls_back(discovery, monkeypatch):
    from postgres_mcp.query_limits.config import QueryBudgetConfig

    @asynccontextmanager
    async def reject(database=None):
        raise DatabaseNotAllowedError("private database")
        yield

    monkeypatch.setattr(server, "query_budget_config", QueryBudgetConfig(enabled=True))
    monkeypatch.setattr(discovery, "acquire", reject)
    with patch.object(SqlDriver, "execute_bounded_query", AsyncMock()) as bounded:
        assert (await execute_sql("SELECT 1", "unknown"))[0].text == "Error: The requested database is not available."
    bounded.assert_not_called()
    assert discovery.pools == {}


_EXPLAIN_CALLS = [
    # Direct calls bypass FastMCP, so Field() defaults must be passed explicitly.
    ("explain", lambda db: explain_query("SELECT 1", False, [], database=db)),
    ("analyze", lambda db: explain_query("SELECT 1", True, [], database=db)),
    ("hypothetical", lambda db: explain_query("SELECT 1", False, [{"table": "t", "columns": ["a"]}], database=db)),
]


@pytest.mark.parametrize("call", [c for _, c in _EXPLAIN_CALLS], ids=[n for n, _ in _EXPLAIN_CALLS])
@pytest.mark.asyncio
async def test_explain_query_routes_by_database(discovery, call):
    calls: list[tuple[str, str]] = []

    @asynccontextmanager
    async def fake_database_session(database=None, **options):
        async with get_sql_driver(database) as driver:
            yield driver

    with (
        patch.object(SqlDriver, "_execute_with_connection", _routing_execute(discovery, calls)),
        patch("postgres_mcp.server.database_session", fake_database_session),
    ):
        selected = (await call("app_testing"))[0].text
        selected_calls = list(calls)
        calls.clear()
        default = (await call(None))[0].text
    assert not selected.startswith("Error") and not default.startswith("Error")
    # Every query of the call (hypopg check, hypopg_reset, EXPLAIN) runs on the requested pool only.
    assert selected_calls and {name for name, _ in selected_calls} == {"app_testing"}
    assert calls and {name for name, _ in calls} == {"app_main"}
    assert any("EXPLAIN" in query for _, query in selected_calls)
    assert discovery.requested == ["app_testing", None]
    assert discovery.leases == {"app_testing": 0, "app_main": 0}


def test_execute_sql_and_explain_signatures_keep_legacy_defaults():
    import inspect

    execute_params = inspect.signature(execute_sql).parameters
    assert list(execute_params) == ["sql", "database", "max_rows", "timeout_seconds", "page_size", "pagination"]
    assert execute_params["sql"].default.default == "all"
    assert execute_params["database"].default is None
    assert execute_params["max_rows"].default is None
    assert execute_params["timeout_seconds"].default is None
    explain_params = inspect.signature(explain_query).parameters
    assert list(explain_params) == ["sql", "analyze", "hypothetical_indexes", "database"]
    assert explain_params["analyze"].default.default is False
    assert explain_params["hypothetical_indexes"].default.default == []
    assert explain_params["database"].default is None


# --- Task 13: query statistics and index tuning use the selected database's driver ---


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["dta", "llm"])
async def test_index_tools_use_database_specific_driver(method):
    from postgres_mcp.server import analyze_query_indexes
    from postgres_mcp.server import analyze_workload_indexes
    from postgres_mcp.server import get_top_queries

    selected = MagicMock(name="selected_driver")
    requested: list[str | None] = []
    session_requests: list[dict] = []

    @asynccontextmanager
    async def fake_get_sql_driver(database=None):
        requested.append(database)
        yield selected

    @asynccontextmanager
    async def fake_database_session(database=None, **options):
        session_requests.append(options)
        async with fake_get_sql_driver(database) as driver:
            yield driver

    presentation = MagicMock()
    presentation.analyze_workload = AsyncMock(return_value="ok")
    presentation.analyze_queries = AsyncMock(return_value="ok")
    top = MagicMock()
    top.get_top_resource_queries = AsyncMock(return_value="ok")
    top.get_top_queries_by_time = AsyncMock(return_value="ok")
    with (
        patch("postgres_mcp.server.get_sql_driver", fake_get_sql_driver),
        patch("postgres_mcp.server.database_session", fake_database_session),
        patch("postgres_mcp.server.current_access_mode", AccessMode.UNRESTRICTED),
        patch("postgres_mcp.server.DatabaseTuningAdvisor") as dta,
        patch("postgres_mcp.server.LLMOptimizerTool") as llm,
        patch("postgres_mcp.server.TextPresentation", return_value=presentation) as text_presentation,
        patch("postgres_mcp.server.TopQueriesCalc", return_value=top) as top_calc,
    ):
        await analyze_workload_indexes(method=method, database="app_two")
        await analyze_query_indexes(["select 1"], method=method, database="app_two")
        await get_top_queries(sort_by="resources", database="app_two")
        await get_top_queries(sort_by="mean_time", limit=3, database="app_two")

    assert requested == ["app_two"] * 4
    assert len(session_requests) == (2 if method == "dta" else 0)
    assert all(options["restricted"] is False for options in session_requests)
    tuner = dta if method == "dta" else llm
    assert [c.args[0] for c in tuner.call_args_list] == [selected, selected]
    assert [c.args[0] for c in text_presentation.call_args_list] == [selected, selected]
    assert [c.kwargs["sql_driver"] for c in top_calc.call_args_list] == [selected, selected]


# --- Task 14: health and extension checks keep database context ---

from postgres_mcp.server import analyze_db_health  # noqa: E402
from postgres_mcp.sql import check_hypopg_installation_status  # noqa: E402
from postgres_mcp.sql.database_catalog import DatabaseConfigurationError  # noqa: E402
from postgres_mcp.sql.database_catalog import DiscoveryUnavailableError  # noqa: E402
from postgres_mcp.sql.database_registry import DatabaseUnavailableError  # noqa: E402
from postgres_mcp.sql.database_registry import PoolCapacityError  # noqa: E402


class _Row:
    def __init__(self, **cells):
        self.cells = cells


def _extension_driver(db: str, installed: bool, available: bool):
    """Driver whose pg_extension / current_database answers belong to database `db`."""
    driver = MagicMock()

    async def execute_query(query, *a, **k):
        if "current_database" in query:
            return [_Row(current_database=db)]
        if "pg_extension" in query:
            return [_Row(extversion="1.0")] if installed else []
        if "pg_available_extensions" in query:
            return [_Row(default_version="1.0")] if available else []
        return [_Row(server_version="16.2")]

    driver.execute_query = AsyncMock(side_effect=execute_query)
    return driver


@pytest.mark.asyncio
async def test_health_uses_selected_database(discovery):
    with patch("postgres_mcp.server.DatabaseHealthTool") as tool:
        tool.return_value.health = AsyncMock(return_value="ok")
        await analyze_db_health("index", "app_testing")
        await analyze_db_health("index")
    assert discovery.requested == ["app_testing", None]
    assert tool.call_args_list[0].args[0].conn is discovery.pools["app_testing"]
    assert tool.call_args_list[1].args[0].conn is discovery.pools["app_main"]


@pytest.mark.asyncio
async def test_health_legacy_positional_order():
    with patch("postgres_mcp.server.get_sql_driver") as gsd, patch("postgres_mcp.server.DatabaseHealthTool") as tool:

        @asynccontextmanager
        async def fake(database=None):
            gsd.seen = database
            yield MagicMock()

        gsd.side_effect = fake
        tool.return_value.health = AsyncMock(return_value="ok")
        await analyze_db_health("index,vacuum")
    assert gsd.seen is None
    tool.return_value.health.assert_awaited_once_with(health_type="index,vacuum")


@pytest.mark.parametrize(
    "exc, expected",
    [
        (DatabaseUnavailableError("db gone"), "The database is temporarily unavailable."),
        (DiscoveryUnavailableError("no discovery"), "The database is temporarily unavailable."),
        (DatabaseConfigurationError("bad cfg"), "The requested database is not available."),
        (PoolCapacityError("full"), "The database connection pool is at capacity."),
        (ValueError("Database 'x' is not available"), "The operation failed."),
    ],
)
@pytest.mark.asyncio
async def test_health_reports_expected_errors_as_error_response(exc, expected):
    @asynccontextmanager
    async def boom(database=None):
        raise exc
        yield  # pragma: no cover

    with patch("postgres_mcp.server.get_sql_driver", boom):
        text = (await analyze_db_health("all", "x"))[0].text
    assert text == f"Error: {expected}"
    assert str(exc) not in text


@pytest.mark.asyncio
async def test_health_does_not_swallow_unexpected_errors():
    @asynccontextmanager
    async def boom(database=None):
        raise RuntimeError("bug")
        yield  # pragma: no cover

    with patch("postgres_mcp.server.get_sql_driver", boom):
        res = await analyze_db_health("all", "x")
        assert res.isError is True
        assert res.structuredContent["error"]["code"] == "INTERNAL_ERROR"


@pytest.mark.asyncio
async def test_replication_is_labeled_instance_wide():
    from postgres_mcp.database_health import DatabaseHealthTool

    tool = DatabaseHealthTool(_extension_driver("db_a", True, True))
    with (
        patch("postgres_mcp.database_health.database_health.ReplicationCalc") as rep,
        patch("postgres_mcp.database_health.database_health.IndexHealthCalc") as idx,
    ):
        rep.return_value.replication_health_check = AsyncMock(return_value="r")
        idx.return_value.invalid_index_check = AsyncMock(return_value="i")
        idx.return_value.duplicate_index_check = AsyncMock(return_value="i")
        idx.return_value.index_bloat = AsyncMock(return_value="i")
        idx.return_value.unused_indexes = AsyncMock(return_value="i")
        text = await tool.health("replication,index")
    assert "Replication health: [instance-wide] r" in text
    assert "Invalid index check: [database-scoped: db_a] i" in text


@pytest.mark.asyncio
async def test_connection_health_scope_is_declared():
    from postgres_mcp.database_health import DatabaseHealthTool

    tool = DatabaseHealthTool(_extension_driver("db_a", True, True))
    with patch("postgres_mcp.database_health.database_health.ConnectionHealthCalc") as conn:
        conn.return_value.connection_health_check = AsyncMock(return_value="c")
        text = await tool.health("connection")
    assert "Connection health: [instance-wide] c" in text


@pytest.mark.asyncio
async def test_missing_hypopg_in_second_db_is_reported():
    ok, _ = await check_hypopg_installation_status(_extension_driver("db_a", True, True))
    assert ok
    ok, msg = await check_hypopg_installation_status(_extension_driver("db_b", False, True))
    assert not ok
    assert "db_b" in msg and "db_a" not in msg


@pytest.mark.asyncio
async def test_extension_probe_is_not_shared_across_databases():
    a = _extension_driver("db_a", True, True)
    b = _extension_driver("db_b", False, False)
    first = await check_hypopg_installation_status(a)
    second = await check_hypopg_installation_status(b)
    third = await check_hypopg_installation_status(a)
    assert first[0] is True and second[0] is False and third[0] is True

    def probes(driver):
        return [c for c in driver.execute_query.await_args_list if "pg_extension" in c.args[0]]

    assert len(probes(a)) == 2  # one probe per call on db_a, none borrowed from db_b
    assert len(probes(b)) == 1  # db_b probed its own pg_extension, not reusing db_a's result


LEGACY_TOOLS = {
    "list_schemas",
    "list_objects",
    "get_object_details",
    "explain_query",
    "execute_sql",
    "analyze_workload_indexes",
    "analyze_query_indexes",
    "analyze_db_health",
    "get_top_queries",
}

# Defaults the nine legacy tools had before the optional `database` argument existed.
LEGACY_DEFAULTS = {
    "list_objects": {"object_type": "table"},
    "get_object_details": {"object_type": "table"},
    "explain_query": {"analyze": False, "hypothetical_indexes": []},
    "execute_sql": {"sql": "all"},
    "analyze_workload_indexes": {"max_index_size_mb": 10000, "method": "dta"},
    "analyze_query_indexes": {"max_index_size_mb": 10000, "method": "dta"},
    "analyze_db_health": {"health_type": "all"},
    "get_top_queries": {"sort_by": "resources", "limit": 10},
}


async def _tools_after_startup(monkeypatch, argv, env):
    # execute_sql is registered by main() per access mode: start from a clean slate, restore afterwards.
    monkeypatch.delitem(server.mcp._tool_manager._tools, "execute_sql", raising=False)
    await _run_main(monkeypatch, argv, env)
    return {t.name: t for t in server.mcp._tool_manager.list_tools()}


@pytest.mark.asyncio
@pytest.mark.parametrize("argv,env", [([], URI), ([], DISCOVER)], ids=["legacy", "discovery"])
async def test_contract_nine_legacy_tools_plus_database_list_and_continuation(monkeypatch, argv, env):
    tools = await _tools_after_startup(monkeypatch, argv, env)
    assert set(tools) == LEGACY_TOOLS | {"list_databases", "fetch_query_page"}
    assert len(tools) == 11


@pytest.mark.asyncio
async def test_contract_database_is_optional_on_all_nine_tools(monkeypatch):
    tools = await _tools_after_startup(monkeypatch, [], DISCOVER)
    for name in LEGACY_TOOLS:
        schema = tools[name].parameters
        assert "database" in schema["properties"], name
        assert "database" not in schema.get("required", []), name
        assert schema["properties"]["database"].get("default") is None, name
    assert "database" not in tools["list_databases"].parameters["properties"]
    assert tools["list_databases"].parameters["properties"]["refresh"]["default"] is False
    assert "refresh" not in tools["list_databases"].parameters.get("required", [])


@pytest.mark.asyncio
async def test_contract_legacy_defaults_and_required_arguments_unchanged(monkeypatch):
    tools = await _tools_after_startup(monkeypatch, [], DISCOVER)
    for name, defaults in LEGACY_DEFAULTS.items():
        props = tools[name].parameters["properties"]
        for arg, expected in defaults.items():
            assert props[arg]["default"] == expected, f"{name}.{arg}"
    required = {name: set(tools[name].parameters.get("required", [])) for name in LEGACY_TOOLS}
    assert required["list_objects"] == {"schema_name"}
    assert required["get_object_details"] == {"schema_name", "object_name"}
    assert required["explain_query"] == {"sql"}
    assert required["analyze_query_indexes"] == {"queries"}
    for name in ("list_schemas", "execute_sql", "analyze_workload_indexes", "analyze_db_health", "get_top_queries"):
        assert required[name] == set(), name


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "argv,env,title,read_only,destructive",
    [
        ([], URI, "Execute SQL", None, True),
        (["--access-mode=unrestricted"], DISCOVER, "Execute SQL", None, True),
        ([], DISCOVER, "Execute SQL (Read-Only)", True, None),
        (["--access-mode=restricted"], URI, "Execute SQL (Read-Only)", True, None),
    ],
    ids=["legacy-default", "discovery-unrestricted", "discovery-default-restricted", "legacy-restricted"],
)
async def test_contract_execute_sql_annotations_follow_access_mode(monkeypatch, argv, env, title, read_only, destructive):
    tools = await _tools_after_startup(monkeypatch, argv, env)
    ann = tools["execute_sql"].annotations
    assert (ann.title, ann.readOnlyHint, ann.destructiveHint) == (title, read_only, destructive)


@pytest.mark.asyncio
async def test_contract_every_other_tool_is_read_only(monkeypatch):
    tools = await _tools_after_startup(monkeypatch, [], DISCOVER)
    for name in (LEGACY_TOOLS - {"execute_sql"}) | {"list_databases"}:
        assert tools[name].annotations.readOnlyHint is True, name
