"""Multi-database integration tests against an ephemeral Docker PostgreSQL (see conftest.multidb_postgres)."""

import ast
import asyncio
import json
import secrets
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from psycopg import sql

from postgres_mcp import server
from postgres_mcp.database_config import parse_database_config
from postgres_mcp.sql import reset_postgres_version_cache
from postgres_mcp.sql.database_catalog import DatabaseCatalog
from postgres_mcp.sql.database_catalog import discover_postgres_databases
from postgres_mcp.sql.database_registry import DatabaseRegistry

pytestmark = pytest.mark.asyncio

# Must match the fixture contract in conftest.multidb_postgres (conftest is not importable by name here).
ROLE = "mcp_test_role"
VISIBLE = ("app_development", "app_testing", "analytics")
BLOCKED = "blocked_db"


class Env:
    """Wires server globals to a registry built on the ephemeral instance."""

    def __init__(self, pg: Any, registry: DatabaseRegistry, catalog: DatabaseCatalog) -> None:
        self.pg = pg
        self.registry = registry
        self.catalog = catalog
        self.now = 1000.0
        self.outage = False


def _config(pg: Any, **overrides: str):
    env = {
        "DATABASE_URI": pg.mcp_bootstrap_uri,
        "DATABASE_AUTO_DISCOVER": "true",
        "DATABASE_DEFAULT_DATABASE": "app_testing",
        "DATABASE_EXCLUDED_DATABASES": "postgres",
        "DATABASE_MAX_POOLS": "8",
        "DATABASE_POOL_MAX_SIZE": "2",
        **overrides,
    }
    return parse_database_config(env, None, None)


async def _make_env(pg: Any, monkeypatch: pytest.MonkeyPatch, **overrides: str) -> Env:
    config = _config(pg, **overrides)
    holder: dict[str, Env] = {}

    async def discover(uri: str) -> set[str]:
        if holder["env"].outage:
            raise ConnectionError("bootstrap down")
        return await discover_postgres_databases(uri)

    catalog = DatabaseCatalog(config, discover=discover, clock=lambda: holder["env"].now)
    registry = DatabaseRegistry(config, catalog)
    env = holder["env"] = Env(pg, registry, catalog)
    await registry.start()
    monkeypatch.setattr(server, "database_config", config)
    monkeypatch.setattr(server, "registry", registry)
    monkeypatch.setattr(server, "current_access_mode", server.AccessMode.RESTRICTED)
    reset_postgres_version_cache()
    return env


@pytest_asyncio.fixture
async def env(multidb_postgres: Any, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Env]:
    e = await _make_env(multidb_postgres, monkeypatch)
    try:
        yield e
    finally:
        await e.registry.close_all()


def _text(response: Any) -> str:
    return response[0].text


def _rows(response: Any) -> list[dict[str, Any]]:
    text = _text(response)
    assert not text.startswith("Error:"), text
    return ast.literal_eval(text)  # tool output is the Python repr of a list of dicts


async def _db_names(refresh: bool = False) -> list[str]:
    return [r["name"] for r in json.loads(_text(await server.list_databases(refresh=refresh)))]


async def _current(database: str | None) -> str:
    return _rows(await server.execute_sql("SELECT current_database() AS db", database))[0]["db"]


async def test_discovery_filters_templates_blocked_db(env: Env):
    assert await _db_names() == sorted(VISIBLE)  # no postgres (excluded), templates or blocked_db
    rows = json.loads(_text(await server.list_databases()))
    assert {r["name"] for r in rows if r["is_default"]} == {"app_testing"}
    assert all(r["connection_state"] == "not_connected" for r in rows)  # listing opens no pool
    result = await server.execute_sql("SELECT 1", BLOCKED)
    assert "not available" in _text(result)
    with env.pg.admin() as conn:
        role = conn.execute("SELECT rolsuper, rolcreatedb FROM pg_roles WHERE rolname = %s", (ROLE,)).fetchone()
        assert role == (False, False)


async def test_two_database_current_database_and_schema_isolation(env: Env):
    for name in ("app_development", "app_testing"):
        assert await _current(name) == name
    assert await _current(None) == "app_testing"  # default
    dev = _rows(await server.list_objects("public", "table", "app_development"))
    test = _rows(await server.list_objects("public", "table", "app_testing"))
    assert [o["name"] for o in dev] == ["development_marker"]
    assert [o["name"] for o in test] == ["testing_marker"]
    cross = await server.execute_sql("SELECT * FROM testing_marker", "app_development")
    assert _text(cross).startswith("Error:")
    assert _rows(await server.execute_sql("SELECT label FROM development_marker", "app_development")) == [{"label": "app_development"}]


async def test_create_database_visible_after_refresh_without_restart(env: Env):
    new = f"fresh_{secrets.token_hex(3)}"
    assert new not in await _db_names()
    with env.pg.admin() as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(new)))
        conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(new), sql.Identifier(ROLE)))
    try:
        assert new not in await _db_names()  # cached until TTL or refresh
        assert new in await _db_names(refresh=True)
        assert await _current(new) == new
        with env.pg.admin() as conn:
            conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(new)))
        env.now += 61  # TTL (60s) expires: next listing re-queries
        assert new not in await _db_names()
    finally:
        with env.pg.admin() as conn:
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(new)))


async def test_revoke_access_updates_catalog_without_cross_access(env: Env):
    assert await _current("analytics") == "analytics"
    stmts = (
        sql.SQL("REVOKE CONNECT ON DATABASE analytics FROM {}").format(sql.Identifier(ROLE)),
        sql.SQL("REVOKE CONNECT ON DATABASE analytics FROM PUBLIC"),
    )
    with env.pg.admin() as conn:
        for stmt in stmts:
            conn.execute(stmt)
    try:
        assert "analytics" not in await _db_names(refresh=True)
        assert "not available" in _text(await server.execute_sql("SELECT 1", "analytics"))
        assert await _current("app_development") == "app_development"
        assert await _current("app_testing") == "app_testing"
        rows = json.loads(_text(await server.list_databases()))
        assert [r["name"] for r in rows] == ["app_development", "app_testing"]
        assert {r["name"]: r["is_default"] for r in rows} == {"app_development": False, "app_testing": True}
    finally:
        with env.pg.admin() as conn:
            conn.execute(sql.SQL("GRANT CONNECT ON DATABASE analytics TO {}").format(sql.Identifier(ROLE)))


async def test_all_nine_tools_accept_explicit_database(env: Env):
    # Per-database fingerprints, created by the admin connection: a schema and a query workload on its own marker table.
    fingerprints = {"app_development": "dev", "app_testing": "testing"}
    for name, tag in fingerprints.items():
        with env.pg.admin(name) as conn:
            conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(f"schema_{tag}")))
            # information_schema.schemata only lists schemas the role can use.
            conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(sql.Identifier(f"schema_{tag}"), sql.Identifier(ROLE)))
    with env.pg.admin("app_development") as conn:
        conn.execute("DROP EXTENSION IF EXISTS hypopg")  # deterministic: the analyze tools report it missing per database
    try:
        for name, tag in fingerprints.items():
            other = next(t for t in fingerprints.values() if t != tag)
            marker = name.removeprefix("app_") + "_marker"
            marker = name.removeprefix("app_") + "_marker"
            await server.execute_sql(f"SELECT id, label FROM {marker} WHERE id = 1", name)  # workload only in this database
            schemas = _text(await server.list_schemas(name))
            assert f"schema_{tag}" in schemas and f"schema_{other}" not in schemas
            assert [o["name"] for o in _rows(await server.list_objects("public", "table", name))] == [marker]
            details = _text(await server.get_object_details("public", marker, "table", name))
            assert f"'name': '{marker}'" in details and f"{next(n for n in fingerprints if n != name).removeprefix('app_')}_marker" not in details
            assert f"on {marker}" in _text(await server.explain_query(f"SELECT * FROM {marker}", False, [], name))
            assert _rows(await server.execute_sql(f"SELECT label FROM {marker}", name)) == [{"label": name}]
            # Without hypopg both analyzers report it missing, naming the selected database.
            workload = _text(await server.analyze_workload_indexes(10000, "dta", name))
            assert f"database '{name}'" in workload and "hypopg" in workload
            queries = _text(await server.analyze_query_indexes([f"SELECT * FROM {marker}"], 10000, "dta", name))
            assert f"database '{name}'" in queries and "hypopg" in queries
            health = _text(await server.analyze_db_health("connection,constraint", name))
            assert f"[database-scoped: {name}]" in health and "[instance-wide]" in health
            top = _text(await server.get_top_queries("total_time", 100, name))
            if name == "app_development":
                assert "FROM development_marker WHERE id" in top and "testing_marker" not in top
            else:
                assert "pg_stat_statements extension is required" in top
    finally:
        for name, tag in fingerprints.items():
            with env.pg.admin(name) as conn:
                conn.execute(sql.SQL("DROP SCHEMA IF EXISTS {}").format(sql.Identifier(f"schema_{tag}")))


async def test_parallel_tools_keep_context(env: Env):
    names = ["app_development", "app_testing"] * 25
    results = await asyncio.gather(*(_current(n) for n in names))
    assert results == names
    mixed = await asyncio.gather(
        *(
            server.execute_sql(f"SELECT label FROM {m}", n)
            for n, m in (("app_development", "development_marker"), ("app_testing", "testing_marker")) * 10
        )
    )
    assert [_rows(r)[0]["label"] for r in mixed] == ["app_development", "app_testing"] * 10


async def test_extension_presence_is_database_local(env: Env):
    def names(resp: Any) -> set[str]:
        return {o["name"] for o in _rows(resp)}

    dev = names(await server.list_objects("public", "extension", "app_development"))
    test = names(await server.list_objects("public", "extension", "app_testing"))
    assert "pg_stat_statements" in dev
    assert "pg_stat_statements" not in test
    with env.pg.admin("app_development") as conn:
        hypopg_available = conn.execute("SELECT 1 FROM pg_available_extensions WHERE name = 'hypopg'").fetchone()
    if not hypopg_available:
        pytest.skip("hypopg is not provisioned in this image (only this check depends on it)")
    with env.pg.admin("app_development") as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS hypopg")
    assert "hypopg" in names(await server.list_objects("public", "extension", "app_development"))
    assert "hypopg" not in test and "hypopg" not in names(await server.list_objects("public", "extension", "app_testing"))


async def test_pool_limit_smaller_than_database_count(multidb_postgres: Any, monkeypatch: pytest.MonkeyPatch):
    env = await _make_env(multidb_postgres, monkeypatch, DATABASE_MAX_POOLS="2")
    try:
        for name in ("app_development", "app_testing", "analytics", "app_development"):  # idle pools are evicted (LRU)
            assert await _current(name) == name
        states = {r["name"]: r["connection_state"] for r in json.loads(_text(await server.list_databases()))}
        # LRU: analytics evicted app_development, then app_development evicted app_testing.
        assert states == {"analytics": "connected", "app_development": "connected", "app_testing": "not_connected"}
        assert await _db_names() == sorted(VISIBLE)  # evicted databases stay authorized
    finally:
        await env.registry.close_all()


async def test_stale_and_error_isolated_with_bootstrap_outage(env: Env):
    assert await _current("app_development") == "app_development"  # pool open before the outage
    env.outage = True
    env.now += 61  # TTL expired, discovery now fails: stale snapshot is served within the grace period
    rows = json.loads(_text(await server.list_databases(refresh=True)))
    assert {r["name"] for r in rows} == set(VISIBLE)
    assert all(r["catalog_stale"] for r in rows)
    assert {r["name"]: r["connection_state"] for r in rows}["app_development"] == "connected"
    assert await _current("app_development") == "app_development"  # existing pool keeps working
    env.now += 600  # beyond the grace period: error, never an unbounded stale snapshot
    err = _text(await server.list_databases(refresh=True))
    assert err.startswith("Error:") and env.pg.mcp_password not in err and env.pg.admin_password not in err
    assert _text(await server.execute_sql("SELECT 1", "app_development")).startswith("Error:")
    env.outage = False  # recovery without restart
    assert await _db_names(refresh=True) == sorted(VISIBLE)
    assert await _current("app_development") == "app_development"
