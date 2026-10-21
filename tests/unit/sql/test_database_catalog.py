import asyncio
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from postgres_mcp.database_config import DatabaseConfig
from postgres_mcp.sql import database_catalog
from postgres_mcp.sql.database_catalog import DatabaseCatalog
from postgres_mcp.sql.database_catalog import DatabaseConfigurationError
from postgres_mcp.sql.database_catalog import DiscoveryUnavailableError
from postgres_mcp.sql.database_catalog import discover_postgres_databases

URI = "postgresql://dev:s3cret@localhost:5432/postgres"


def make_config(**overrides) -> DatabaseConfig:
    values = dict(
        bootstrap_uri=URI,
        auto_discover=True,
        default_database="App_Test",
        allowed_databases=(),
        excluded_databases=(),
        discovery_ttl_seconds=60,
        max_pools=8,
        pool_max_size=5,
        pool_idle_seconds=600,
        access_mode="restricted",
    )
    values.update(overrides)
    return DatabaseConfig(**values)


def fake_clock() -> float:
    return 0.0


@pytest.mark.asyncio
async def test_discovery_sql_uses_pg_catalog_and_connect_privilege():
    cursor = MagicMock()
    cursor.fetchall = AsyncMock(return_value=[("App_Test",), ("postgres",)])
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=cursor)
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    connect = AsyncMock(return_value=conn)
    with patch.object(database_catalog.AsyncConnection, "connect", connect):
        result = await discover_postgres_databases(URI)

    assert result == {"App_Test", "postgres"}
    connect.assert_awaited_once()
    assert connect.await_args.args[0] == URI
    sql = conn.execute.await_args.args[0]
    assert "pg_catalog.pg_database" in sql
    assert "datallowconn" in sql
    assert "NOT datistemplate" in sql
    assert "has_database_privilege(oid, 'CONNECT')" in sql
    conn.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_connection_closed_after_exception():
    conn = MagicMock()
    conn.execute = AsyncMock(side_effect=RuntimeError("boom"))
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    with patch.object(database_catalog.AsyncConnection, "connect", AsyncMock(return_value=conn)):
        with pytest.raises(RuntimeError):
            await discover_postgres_databases(URI)
    conn.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_allowed_intersect_discovered():
    cfg = make_config(allowed_databases=("App_Test", "missing"))
    catalog = DatabaseCatalog(cfg, discover=AsyncMock(return_value={"postgres", "App_Test", "other"}), clock=fake_clock)
    assert await catalog.names(refresh=True) == (["App_Test"], False)


@pytest.mark.asyncio
async def test_denylist_wins():
    cfg = make_config(allowed_databases=("App_Test", "postgres"), excluded_databases=("postgres",))
    catalog = DatabaseCatalog(cfg, discover=AsyncMock(return_value={"postgres", "App_Test", "blocked_db"}), clock=fake_clock)
    assert (await catalog.names(refresh=True))[0] == ["App_Test"]


@pytest.mark.asyncio
async def test_case_is_preserved():
    cfg = make_config(allowed_databases=("App_Test",), excluded_databases=("postgres",))
    catalog = DatabaseCatalog(cfg, discover=AsyncMock(return_value={"postgres", "App_Test", "blocked_db"}), clock=fake_clock)
    assert (await catalog.names(refresh=True))[0] == ["App_Test"]
    assert await catalog.authorize("App_Test") == "App_Test"
    with pytest.raises(ValueError):
        await catalog.authorize("app_test")


@pytest.mark.asyncio
async def test_unknown_and_denied_rejected_before_pool():
    cfg = make_config(excluded_databases=("postgres",))
    catalog = DatabaseCatalog(cfg, discover=AsyncMock(return_value={"postgres", "App_Test"}), clock=fake_clock)
    for bad in ("postgres", "nope", "App_Test; DROP DATABASE x"):
        with pytest.raises(ValueError) as exc:
            await catalog.authorize(bad)
        message = str(exc.value)
        assert bad in message
        assert "s3cret" not in message
        assert "localhost" not in message


@pytest.mark.asyncio
async def test_legacy_exposes_only_bootstrap_database():
    cfg = make_config(auto_discover=False, default_database="postgres")
    discover = AsyncMock(return_value={"postgres", "other"})
    catalog = DatabaseCatalog(cfg, discover=discover, clock=fake_clock)
    assert await catalog.names(refresh=True) == (["postgres"], False)
    assert await catalog.authorize("postgres") == "postgres"
    with pytest.raises(ValueError):
        await catalog.authorize("other")
    discover.assert_not_awaited()


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def flaky_discover(*results):
    """Each call pops the next result; an Exception instance is raised."""
    queue = list(results)

    async def discover(_uri: str) -> set[str]:
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item

    return AsyncMock(side_effect=discover)


@pytest.mark.asyncio
async def test_refresh_flag_bypasses_ttl():
    clock = FakeClock()
    discover = flaky_discover({"App_Test"}, {"App_Test", "other"})
    catalog = DatabaseCatalog(make_config(), discover=discover, clock=clock)
    assert (await catalog.names())[0] == ["App_Test"]
    assert (await catalog.names())[0] == ["App_Test"]
    assert discover.await_count == 1  # TTL honored
    assert await catalog.names(refresh=True) == (["App_Test", "other"], False)
    assert discover.await_count == 2


@pytest.mark.asyncio
async def test_expiry_refreshes_once_concurrently():
    clock = FakeClock()
    gate = asyncio.Event()
    calls = 0

    async def slow(_uri: str) -> set[str]:
        nonlocal calls
        calls += 1
        await gate.wait()
        return {"App_Test"}

    catalog = DatabaseCatalog(make_config(), discover=slow, clock=clock)
    tasks = [asyncio.create_task(catalog.names()) for _ in range(10)]
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    gate.set()
    results = await asyncio.gather(*tasks)
    assert calls == 1
    assert all(r == (["App_Test"], False) for r in results)
    clock.advance(61)
    gate.clear()
    tasks = [asyncio.create_task(catalog.names()) for _ in range(10)]
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    gate.set()
    await asyncio.gather(*tasks)
    assert calls == 2


@pytest.mark.asyncio
async def test_unknown_name_forces_single_refresh():
    clock = FakeClock()
    discover = flaky_discover({"App_Test"}, {"App_Test", "new_db"})
    catalog = DatabaseCatalog(make_config(), discover=discover, clock=clock)
    await catalog.names()
    results = await asyncio.gather(*(catalog.authorize("new_db") for _ in range(5)))
    assert results == ["new_db"] * 5
    assert discover.await_count == 2


@pytest.mark.asyncio
async def test_stale_denies_new_names():
    clock = FakeClock()
    boom = RuntimeError("postgresql://dev:s3cret@localhost")
    discover = flaky_discover({"App_Test"}, boom)
    catalog = DatabaseCatalog(make_config(), discover=discover, clock=clock)
    assert await catalog.names(refresh=True) == (["App_Test"], False)
    clock.advance(61)
    assert await catalog.names(refresh=True) == (["App_Test"], True)
    assert await catalog.authorize("App_Test") == "App_Test"
    with pytest.raises(ValueError):
        await catalog.authorize("new_db")


@pytest.mark.asyncio
async def test_stale_grace_expiry_fails_closed():
    clock = FakeClock()
    discover = flaky_discover({"App_Test"}, RuntimeError("down"))
    catalog = DatabaseCatalog(make_config(), discover=discover, clock=clock)  # ttl 60 -> grace min(300, 120) = 120
    await catalog.names(refresh=True)
    clock.advance(60 + 120)  # exactly at the end of the grace window
    assert (await catalog.names())[1] is True
    clock.advance(1)
    with pytest.raises(DiscoveryUnavailableError):
        await catalog.names()
    with pytest.raises(DiscoveryUnavailableError):
        await catalog.authorize("App_Test")


@pytest.mark.asyncio
async def test_stale_grace_is_capped_at_300():
    clock = FakeClock()
    cfg = make_config(discovery_ttl_seconds=1000)
    catalog = DatabaseCatalog(cfg, discover=flaky_discover({"App_Test"}, RuntimeError("down")), clock=clock)
    await catalog.names(refresh=True)
    clock.advance(1000 + 300)
    assert (await catalog.names())[1] is True
    clock.advance(1)
    with pytest.raises(DiscoveryUnavailableError):
        await catalog.names()


@pytest.mark.asyncio
async def test_unreachable_bootstrap_without_snapshot_fails():
    secret_error = RuntimeError("could not connect to postgresql://dev:s3cret@localhost:5432/postgres")
    catalog = DatabaseCatalog(make_config(), discover=AsyncMock(side_effect=secret_error), clock=FakeClock())
    with pytest.raises(DiscoveryUnavailableError) as exc:
        await catalog.names()
    assert exc.value.__suppress_context__ is True and exc.value.__cause__ is None
    for leak in ("s3cret", "localhost", "postgresql://"):
        assert leak not in str(exc.value)


@pytest.mark.asyncio
async def test_default_missing_after_successful_refresh_fails_configuration():
    catalog = DatabaseCatalog(make_config(), discover=AsyncMock(return_value={"postgres"}), clock=FakeClock())
    with pytest.raises(DatabaseConfigurationError):
        await catalog.names()


def test_default_excluded_by_config_fails_immediately():
    discover = AsyncMock()
    with pytest.raises(DatabaseConfigurationError):
        DatabaseCatalog(make_config(excluded_databases=("App_Test",)), discover=discover, clock=FakeClock())
    with pytest.raises(DatabaseConfigurationError):
        DatabaseCatalog(make_config(allowed_databases=("other",)), discover=discover, clock=FakeClock())
    discover.assert_not_awaited()
