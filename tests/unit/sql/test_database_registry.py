import asyncio
from collections import Counter
from unittest.mock import AsyncMock

import pytest

from postgres_mcp.database_config import DatabaseConfig
from postgres_mcp.sql import DatabaseInfo
from postgres_mcp.sql import DatabaseRegistry
from postgres_mcp.sql import DatabaseUnavailableError
from postgres_mcp.sql.database_catalog import DatabaseCatalog

URI = "postgresql://dev:s3cret@localhost:5432/postgres"
NAMES = {"postgres", "app_testing", "app_development", "app_bad"}


def make_config(**overrides) -> DatabaseConfig:
    values = dict(
        bootstrap_uri=URI,
        auto_discover=True,
        default_database="app_testing",
        allowed_databases=(),
        excluded_databases=("postgres",),
        discovery_ttl_seconds=60,
        max_pools=8,
        pool_max_size=5,
        pool_idle_seconds=600,
        access_mode="restricted",
    )
    values.update(overrides)
    return DatabaseConfig(**values)


class FakePool:
    """Stands in for DbConnPool; `gate` blocks pool_connect until set."""

    def __init__(self, name: str, gate: asyncio.Event | None, error: Exception | None) -> None:
        self.name = name
        self.gate = gate
        self.error = error
        self.connects = 0
        self.closed = False

    async def pool_connect(self) -> None:
        self.connects += 1
        if self.gate is not None:
            await self.gate.wait()
        if self.error is not None:
            raise self.error

    async def close(self) -> None:
        self.closed = True


class Harness:
    def __init__(self, **config_overrides) -> None:
        self.calls: Counter[str] = Counter()
        self.pools: dict[str, list[FakePool]] = {}
        self.gates: dict[str, asyncio.Event] = {}
        self.errors: dict[str, Exception] = {}
        config = make_config(**config_overrides)
        catalog = DatabaseCatalog(config, discover=AsyncMock(return_value=set(NAMES)), clock=lambda: 0.0)
        self.registry = DatabaseRegistry(config, catalog, pool_factory=self.factory, clock=lambda: 0.0)

    def factory(self, name: str) -> FakePool:
        self.calls[name] += 1
        pool = FakePool(name, self.gates.get(name), self.errors.get(name))
        self.pools.setdefault(name, []).append(pool)
        return pool  # type: ignore[return-value]

    def pool(self, name: str) -> FakePool:
        return self.pools[name][-1]


async def settle() -> None:
    for _ in range(5):
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_first_use_opens_only_requested_pool():
    h = Harness()
    async with h.registry.acquire("app_testing") as pool_a:
        assert pool_a is h.pool("app_testing")
    assert dict(h.calls) == {"app_testing": 1}
    async with h.registry.acquire("app_testing") as again:
        assert again is pool_a
    async with h.registry.acquire("app_development") as pool_b:
        assert pool_b is not pool_a
    assert h.calls["app_testing"] == 1
    assert pool_a.connects == 1


@pytest.mark.asyncio
async def test_parallel_first_use_creates_one_pool():
    h = Harness()
    h.gates["app_testing"] = asyncio.Event()
    seen = []

    async def use() -> None:
        async with h.registry.acquire("app_testing") as pool:
            seen.append(pool)
            await asyncio.sleep(0)

    tasks = [asyncio.create_task(use()) for _ in range(20)]
    await settle()
    assert h.calls["app_testing"] == 1
    h.gates["app_testing"].set()
    await asyncio.gather(*tasks)
    assert h.calls["app_testing"] == 1
    assert len(seen) == 20 and all(p is seen[0] for p in seen)
    assert seen[0].connects == 1
    assert h.registry.active_leases("app_testing") == 0


@pytest.mark.asyncio
async def test_parallel_distinct_databases_do_not_cross():
    h = Harness()
    names = ["app_testing", "app_development"] * 10

    async def use(name: str) -> str:
        async with h.registry.acquire(name) as pool:
            await asyncio.sleep(0)
            return pool.name  # type: ignore[attr-defined]

    results = await asyncio.gather(*(use(n) for n in names))
    assert results == names
    assert dict(h.calls) == {"app_testing": 1, "app_development": 1}


@pytest.mark.asyncio
async def test_lease_spans_entire_context():
    h = Harness()
    assert h.registry.active_leases("app_testing") == 0
    async with h.registry.acquire("app_testing"):
        assert h.registry.active_leases("app_testing") == 1
        async with h.registry.acquire("app_testing"):
            assert h.registry.active_leases("app_testing") == 2
        await asyncio.sleep(0)
        assert h.registry.active_leases("app_testing") == 1
    assert h.registry.active_leases("app_testing") == 0
    with pytest.raises(RuntimeError):
        async with h.registry.acquire("app_testing"):
            raise RuntimeError("tool failed")
    assert h.registry.active_leases("app_testing") == 0


@pytest.mark.asyncio
async def test_database_default_not_last_request():
    h = Harness()
    async with h.registry.acquire("app_development") as dev:
        async with h.registry.acquire() as default:
            assert default is h.pool("app_testing")
            assert default is not dev
    async with h.registry.acquire(None) as default_again:
        assert default_again is h.pool("app_testing")


@pytest.mark.asyncio
async def test_pool_open_failure_isolated():
    h = Harness()
    h.gates["app_bad"] = asyncio.Event()
    h.errors["app_bad"] = ValueError(f"Connection attempt failed: {URI}")

    async def bad() -> None:
        async with h.registry.acquire("app_bad"):
            pass

    bad_tasks = [asyncio.create_task(bad()) for _ in range(3)]
    await settle()
    # app_bad is stuck opening; other databases are not blocked.
    async with h.registry.acquire("app_testing") as pool:
        assert pool is h.pool("app_testing")
    h.gates["app_bad"].set()
    results = await asyncio.gather(*bad_tasks, return_exceptions=True)
    assert h.calls["app_bad"] == 1
    for exc in results:
        assert isinstance(exc, DatabaseUnavailableError)
        assert "s3cret" not in str(exc) and "localhost" not in str(exc) and URI not in str(exc)
    assert h.registry.active_leases("app_bad") == 0
    assert h.pool("app_bad").closed
    infos = {i.name: i for i in await h.registry.list_databases()}
    assert infos["app_bad"].connection_state == "unavailable"

    # The failed state is released: a later call retries with a fresh pool.
    del h.errors["app_bad"]
    del h.gates["app_bad"]
    async with h.registry.acquire("app_bad") as retried:
        assert retried is h.pool("app_bad")
    assert h.calls["app_bad"] == 2


@pytest.mark.asyncio
async def test_unauthorized_database_never_reaches_factory():
    h = Harness()
    for bad in ("postgres", "nope", URI):
        with pytest.raises(ValueError):
            async with h.registry.acquire(bad):
                pass
    assert not h.calls


@pytest.mark.asyncio
async def test_cancelled_waiter_releases_its_lease():
    h = Harness()
    h.gates["app_testing"] = asyncio.Event()
    opener_cm = h.registry.acquire("app_testing")
    opener = asyncio.create_task(opener_cm.__aenter__())
    await settle()
    waiter = asyncio.create_task(h.registry.acquire("app_testing").__aenter__())
    await settle()
    assert h.registry.active_leases("app_testing") == 2
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    assert h.registry.active_leases("app_testing") == 1
    h.gates["app_testing"].set()
    await opener
    assert h.registry.active_leases("app_testing") == 1
    await opener_cm.__aexit__(None, None, None)
    assert h.registry.active_leases("app_testing") == 0
    assert h.calls["app_testing"] == 1


@pytest.mark.asyncio
async def test_cancelled_opener_lets_waiter_retry():
    h = Harness()
    h.gates["app_testing"] = asyncio.Event()

    async def use() -> FakePool:
        async with h.registry.acquire("app_testing") as pool:
            return pool  # type: ignore[return-value]

    opener = asyncio.create_task(use())
    await settle()
    waiter = asyncio.create_task(use())
    await settle()
    first = h.pool("app_testing")
    opener.cancel()
    with pytest.raises(asyncio.CancelledError):
        await opener
    assert first.closed
    h.gates["app_testing"].set()
    pool = await waiter
    assert pool is not first and pool is h.pool("app_testing")
    assert h.calls["app_testing"] == 2
    assert h.registry.active_leases("app_testing") == 0


@pytest.mark.asyncio
async def test_list_databases_reports_state_without_opening():
    h = Harness()
    assert await h.registry.list_databases() == [
        DatabaseInfo("app_bad", False, "not_connected", False),
        DatabaseInfo("app_development", False, "not_connected", False),
        DatabaseInfo("app_testing", True, "not_connected", False),
    ]
    assert not h.calls
    async with h.registry.acquire():
        pass
    infos = {i.name: i for i in await h.registry.list_databases()}
    assert infos["app_testing"].connection_state == "connected"
