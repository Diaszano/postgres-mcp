import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

import postgres_mcp.server as server
from postgres_mcp.database_config import parse_database_config
from postgres_mcp.explain import ExplainPlanTool
from postgres_mcp.sql import IndexDefinition
from postgres_mcp.sql import SafeSqlDriver
from postgres_mcp.sql import SqlDriver
from postgres_mcp.sql.database_session import database_session
from postgres_mcp.sql.sql_driver import DbConnPool

PLAN = {
    "Plan": {
        "Node Type": "Index Scan",
        "Startup Cost": 0,
        "Total Cost": 1,
        "Plan Rows": 1,
        "Plan Width": 4,
    }
}
INDEXES = [{"table": "users", "columns": ["email"]}]


class Connection:
    def __init__(self):
        self.events = []
        self.commands = []
        self.reset_count = 0
        self.reset_error = None
        self.explain_error = None
        self.explain_started = asyncio.Event()
        self.block_explain = False
        self.closed = False

    @asynccontextmanager
    async def cursor(self, **kwargs):
        yield Cursor(self)

    async def rollback(self):
        if self.closed:
            raise RuntimeError("cannot roll back a closed connection")
        self.events.append("rollback")

    async def close(self):
        self.closed = True
        self.events.append("close")


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.description = None
        self.rows = []

    async def execute(self, query, params=None):
        conn = self.connection
        conn.commands.append(query)
        self.description = ("result",)
        if "EXPLAIN" in query:
            conn.events.append("explain")
            conn.explain_started.set()
            if conn.block_explain:
                await asyncio.Event().wait()
            if conn.explain_error:
                raise conn.explain_error
            self.rows = [{"QUERY PLAN": [PLAN]}]
        elif "hypopg_reset" in query:
            conn.events.append("reset")
            conn.reset_count += 1
            if conn.reset_count == 2 and conn.reset_error:
                raise conn.reset_error
            self.rows = []
        elif "hypopg_create_index" in query:
            conn.events.append("create")
            self.rows = []
        elif "pg_extension" in query:
            self.rows = [{"extversion": "1.4"}]
        else:
            self.description = None

    def nextset(self):
        return False

    async def fetchall(self):
        return self.rows


class Pool(DbConnPool):
    def __init__(self):
        super().__init__("postgresql://localhost/app")
        self.backend = Connection()
        self.checkouts = 0

    async def pool_connect(self):
        return self

    @asynccontextmanager
    async def connection(self):
        self.checkouts += 1
        try:
            yield self.backend
        finally:
            self.backend.events.append("release")


@pytest.fixture
def pool(monkeypatch):
    pool = Pool()
    monkeypatch.setattr(server, "db_connection", pool)
    monkeypatch.setattr(server, "database_config", parse_database_config({"DATABASE_URI": pool.connection_url}, None, None))
    monkeypatch.setattr(server, "registry", None)
    monkeypatch.setattr(server, "current_access_mode", server.AccessMode.UNRESTRICTED)
    return pool


@pytest.mark.asyncio
async def test_explain_hypopg_uses_one_bound_driver(pool, monkeypatch):
    calls = []
    execute_query = SqlDriver.execute_query

    async def record(driver, query, *args, **kwargs):
        calls.append((driver, driver.conn, query))
        return await execute_query(driver, query, *args, **kwargs)

    monkeypatch.setattr(SqlDriver, "execute_query", record)
    result = await server.explain_query("SELECT * FROM users", analyze=False, hypothetical_indexes=INDEXES, database="app")

    assert "Index Scan" in result[0].text
    assert pool.checkouts == 1
    assert pool.backend.events == ["reset", "create", "explain", "reset", "rollback", "release"]
    assert all(driver is calls[0][0] and connection is pool.backend for driver, connection, _ in calls)
    assert all(not driver.owns_transaction for driver, _, _ in calls)
    assert not any(query.startswith("CREATE INDEX") for _, _, query in calls)


@pytest.mark.asyncio
async def test_reset_runs_in_finally(pool):
    pool.backend.block_explain = True
    task = asyncio.create_task(server.explain_query("SELECT * FROM users", analyze=False, hypothetical_indexes=INDEXES))
    await pool.backend.explain_started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert pool.backend.events == ["reset", "create", "explain", "reset", "rollback", "release"]


@pytest.mark.asyncio
async def test_analyze_hypopg_combination_remains_rejected(pool):
    result = await server.explain_query("SELECT * FROM users", analyze=True, hypothetical_indexes=INDEXES)

    assert "Cannot use analyze and hypothetical indexes together" in result[0].text
    assert pool.checkouts == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("primary_error", [None, ValueError("explain failed"), asyncio.CancelledError()])
async def test_failed_reset_retires_connection_and_preserves_primary_error(pool, primary_error):
    pool.backend.explain_error = primary_error
    reset_error = ValueError("reset failed")
    pool.backend.reset_error = reset_error

    with pytest.raises(type(primary_error or reset_error)) as raised:
        async with database_session(None, restricted=False, registry=None, bootstrap_pool=pool) as driver:
            await ExplainPlanTool(driver).generate_explain_plan_with_hypothetical_indexes(
                "SELECT * FROM users", frozenset({IndexDefinition(table="users", columns=("email",))})
            )

    assert raised.value is (primary_error or reset_error)
    assert pool.backend.closed
    assert pool.backend.events == ["reset", "create", "explain", "reset", "close", "release"]


@pytest.mark.asyncio
@pytest.mark.parametrize("restricted", [False, True])
async def test_failed_reset_returns_sanitized_error(pool, monkeypatch, restricted):
    if restricted:
        monkeypatch.setattr(server, "current_access_mode", server.AccessMode.RESTRICTED)
        monkeypatch.setattr("postgres_mcp.sql.safe_sql.validate_restricted_function_resolution", AsyncMock())
    pool.backend.reset_error = ValueError("reset failed: private database details")

    result = await server.explain_query("SELECT * FROM users", analyze=False, hypothetical_indexes=INDEXES)

    assert result[0].text.startswith("Error:")
    assert "private database details" not in result[0].text
    assert pool.backend.closed
    assert pool.backend.events[-2:] == ["close", "release"]


@pytest.mark.asyncio
async def test_restricted_hypopg_preserves_safe_driver_validation(pool, monkeypatch):
    monkeypatch.setattr(server, "current_access_mode", server.AccessMode.RESTRICTED)
    validate = SafeSqlDriver.validate
    validated = []

    def record(driver, query):
        validated.append(query)
        return validate(driver, query)

    monkeypatch.setattr(SafeSqlDriver, "validate", record)
    runtime_guard = AsyncMock()
    monkeypatch.setattr("postgres_mcp.sql.safe_sql.validate_restricted_function_resolution", runtime_guard)
    result = await server.explain_query("SELECT * FROM users", analyze=False, hypothetical_indexes=INDEXES)

    assert "Index Scan" in result[0].text
    assert validated[0] == "SELECT * FROM users"
    assert any(query.startswith("EXPLAIN") for query in validated)
    assert runtime_guard.await_count == 5
    assert pool.backend.commands[0] == "BEGIN TRANSACTION READ ONLY"
    assert pool.checkouts == 1


@pytest.mark.asyncio
async def test_restricted_hypopg_rejects_user_sql_before_extension_queries(pool, monkeypatch):
    monkeypatch.setattr(server, "current_access_mode", server.AccessMode.RESTRICTED)
    result = await server.explain_query("DELETE FROM users", analyze=False, hypothetical_indexes=INDEXES)

    assert result[0].text.startswith("Error:")
    assert not any("hypopg" in query or "pg_extension" in query or "EXPLAIN" in query for query in pool.backend.commands)
