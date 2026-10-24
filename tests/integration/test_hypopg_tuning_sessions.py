"""DTA session affinity against disposable PostgreSQL with mandatory HypoPG."""

import asyncio
from collections.abc import AsyncIterator
from contextvars import ContextVar
from typing import Any

import pytest
import pytest_asyncio
from psycopg import AsyncConnection
from psycopg import sql
from test_multi_database_integration import _make_env

from postgres_mcp import server
from postgres_mcp.index.index_opt_base import IndexTuningBase
from postgres_mcp.sql import SqlDriver
from postgres_mcp.sql.database_session import database_session

pytestmark = pytest.mark.asyncio
operation: ContextVar[str] = ContextVar("tuning_operation", default="single")


@pytest_asyncio.fixture
async def tuning_env(hypopg_postgres: Any, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Any]:
    for database, table, columns in (
        ("app_development", "tuning_items", "value int, other int"),
        ("app_testing", "tuning_events", "account int, region int"),
    ):
        with hypopg_postgres.admin(database) as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS hypopg")
            conn.execute(sql.SQL("GRANT SELECT ON hypopg_list_indexes TO {}").format(sql.Identifier(hypopg_postgres.mcp_role)))
            conn.execute(sql.SQL("CREATE TABLE {} ({})").format(sql.Identifier(table), sql.SQL(columns)))
            conn.execute(sql.SQL("INSERT INTO {} SELECT i, i % 10 FROM generate_series(1, 1000) i").format(sql.Identifier(table)))
            conn.execute(sql.SQL("GRANT SELECT ON {} TO {}").format(sql.Identifier(table), sql.Identifier(hypopg_postgres.mcp_role)))
            conn.execute(sql.SQL("ANALYZE {}").format(sql.Identifier(table)))
    env = await _make_env(hypopg_postgres, monkeypatch)
    try:
        # Fill the two-slot pool so a per-statement checkout reliably changes backend.
        async with env.registry.acquire("app_development") as pool:
            physical = await pool.pool_connect()
            async with physical.connection(), physical.connection():
                pass
        yield env
    finally:
        await env.registry.close_all()
        for database, table in (("app_development", "tuning_items"), ("app_testing", "tuning_events")):
            with hypopg_postgres.admin(database) as conn:
                conn.execute(sql.SQL("DROP TABLE {}").format(sql.Identifier(table)))


class Observe:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, int, str]] = []
        self.list_sizes: list[int] = []
        self.definitions: dict[str, list[str]] = {}
        self.after_list: Any = None
        self.before_reset: Any = None

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        original = SqlDriver._execute_with_connection

        async def execute(driver, connection, query, params, force_readonly):
            kind = next((name for name in ("hypopg_create_index", "hypopg_list_indexes", "EXPLAIN", "hypopg_reset") if name in query), "query")
            if kind == "hypopg_reset" and self.before_reset is not None:
                await self.before_reset(connection)
            async with connection.cursor() as cursor:
                await cursor.execute("SELECT pg_backend_pid(), current_database()")
                pid, database = await cursor.fetchone()
            self.events.append((operation.get(), kind, pid, database))
            rows = await original(driver, connection, query, params, force_readonly)
            if kind == "hypopg_list_indexes":
                self.list_sizes.append(len(rows or []))
                async with connection.cursor() as cursor:
                    await cursor.execute("SELECT hypopg_get_indexdef(indexrelid) FROM hypopg_list_indexes")
                    self.definitions[operation.get()] = [row[0] for row in await cursor.fetchall()]
                if self.after_list is not None:
                    await self.after_list(connection)
            return rows

        monkeypatch.setattr(SqlDriver, "_execute_with_connection", execute)


@pytest.mark.parametrize("access_mode", [server.AccessMode.RESTRICTED, server.AccessMode.UNRESTRICTED])
async def test_tuning_sequence_uses_single_backend_pid(tuning_env: Any, monkeypatch: pytest.MonkeyPatch, access_mode: server.AccessMode):
    monkeypatch.setattr(server, "current_access_mode", access_mode)

    async def forbidden_bounded_query(*args, **kwargs):
        raise AssertionError("DTA must use the bound session's execute_query path")

    monkeypatch.setattr(SqlDriver, "execute_bounded_query", forbidden_bounded_query)
    observer = Observe()
    observer.install(monkeypatch)
    response = await server.analyze_query_indexes(["SELECT * FROM tuning_items WHERE value = 7"], 10000, "dta", "app_development")
    assert "Error" not in response[0].text, response[0].text
    assert {kind for _, kind, _, _ in observer.events} >= {"hypopg_create_index", "hypopg_list_indexes", "EXPLAIN", "hypopg_reset"}
    assert len({pid for _, _, pid, _ in observer.events}) == 1
    assert observer.list_sizes and all(size > 0 for size in observer.list_sizes)


async def _analyze(label: str, database: str, table: str, column: str):
    token = operation.set(label)
    try:
        return await server.analyze_query_indexes([f"SELECT * FROM {table} WHERE {column} = 7"], 10000, "dta", database)
    finally:
        operation.reset(token)


async def _parallel_tuning(monkeypatch: pytest.MonkeyPatch, cross_database: bool):
    observer = Observe()
    observer.install(monkeypatch)
    both_created = asyncio.Event()
    arrived = 0

    async def rendezvous(connection):
        nonlocal arrived
        arrived += 1
        if arrived == 2:
            both_created.set()
        await asyncio.wait_for(both_created.wait(), 10)

    observer.after_list = rendezvous
    responses = await asyncio.gather(
        _analyze("left", "app_development", "tuning_items", "value"),
        _analyze(
            "right",
            "app_testing" if cross_database else "app_development",
            "tuning_events" if cross_database else "tuning_items",
            "account" if cross_database else "other",
        ),
    )
    assert all("Error" not in response[0].text for response in responses), [response[0].text for response in responses]
    assert observer.list_sizes == [1, 1]
    assert len(observer.definitions["left"]) == len(observer.definitions["right"]) == 1
    assert "(value)" in observer.definitions["left"][0]
    assert ("(account)" if cross_database else "(other)") in observer.definitions["right"][0]
    pids = {label: {pid for op, _, pid, _ in observer.events if op == label} for label in ("left", "right")}
    assert len(pids["left"]) == len(pids["right"]) == 1
    assert pids["left"].isdisjoint(pids["right"])


async def test_parallel_tuning_does_not_share_hypopg_indexes(tuning_env: Any, monkeypatch: pytest.MonkeyPatch):
    await _parallel_tuning(monkeypatch, False)


async def test_cross_db_isolation(tuning_env: Any, monkeypatch: pytest.MonkeyPatch):
    await _parallel_tuning(monkeypatch, True)


async def _assert_pool_clean(env: Any):
    async with (
        database_session("app_development", restricted=True, registry=env.registry, bootstrap_pool=None) as first,
        database_session("app_development", restricted=True, registry=env.registry, bootstrap_pool=None) as second,
    ):
        for driver in (first, second):
            assert await driver.execute_query("SELECT * FROM hypopg_list_indexes") == []
            rows = await driver.execute_query("SELECT 1 AS alive")
            assert rows and rows[0].cells == {"alive": 1}


@pytest.mark.parametrize("cleanup_stage", ["reset", "retirement"])
@pytest.mark.parametrize(
    ("failure", "repeat_cancel"),
    [("error", False), ("cancel", False), ("error", True), ("cancel", True), ("success", True)],
    ids=["error", "cancel", "repeated-error", "repeated-cancel", "cancel-after-success"],
)
async def test_cleanup_after_cancel_and_error(
    tuning_env: Any, monkeypatch: pytest.MonkeyPatch, failure: str, cleanup_stage: str, repeat_cancel: bool
):
    observer = Observe()
    observer.install(monkeypatch)
    created = asyncio.Event()
    body_done = asyncio.Event()
    cleanup_started = asyncio.Event()
    release_cleanup = asyncio.Event()
    connection_holder: list[Any] = []
    original_close = AsyncConnection.close
    original_format = IndexTuningBase._format_recommendations

    async def format_recommendations(advisor, *args):
        result = await original_format(advisor, *args)
        body_done.set()
        return result

    monkeypatch.setattr(IndexTuningBase, "_format_recommendations", format_recommendations)

    async def close(connection):
        if connection_holder and connection is connection_holder[0] and cleanup_stage == "retirement":
            cleanup_started.set()
            await release_cleanup.wait()
        await original_close(connection)

    monkeypatch.setattr(AsyncConnection, "close", close)

    async def after_list(connection):
        connection_holder.append(connection)
        created.set()
        if failure == "success":
            return
        if failure == "error":
            async with connection.cursor() as cursor:
                await cursor.execute("SELECT 1 / 0")
        await asyncio.Event().wait()

    async def before_reset(connection):
        if not created.is_set() or (failure == "success" and not body_done.is_set()):
            return
        if cleanup_stage == "reset":
            cleanup_started.set()
            await release_cleanup.wait()
        else:
            raise RuntimeError("injected reset failure")

    observer.after_list = after_list
    observer.before_reset = before_reset
    task = asyncio.create_task(_analyze("failed", "app_development", "tuning_items", "value"))
    try:
        await asyncio.wait_for(created.wait(), 10)
        if failure == "cancel":
            task.cancel()
        await asyncio.wait_for(cleanup_started.wait(), 10)
        if repeat_cancel:
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.sleep(0)
        assert not task.done(), "session cleanup must finish before cancellation releases its connection"
        release_cleanup.set()
        if failure == "cancel" or repeat_cancel:
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            response = await task
            assert "error" in response[0].text.lower(), response[0].text
    finally:
        release_cleanup.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    observer.after_list = observer.before_reset = None
    await _assert_pool_clean(tuning_env)
    response = await _analyze("next", "app_development", "tuning_items", "value")
    assert "Error" not in response[0].text, response[0].text
