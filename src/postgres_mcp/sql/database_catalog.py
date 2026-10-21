"""Discovery and authorization of databases on the bootstrap PostgreSQL instance."""

import asyncio
import time
from collections.abc import Awaitable
from collections.abc import Callable

from psycopg import AsyncConnection

from postgres_mcp.database_config import DatabaseConfig

_DISCOVERY_SQL = """
SELECT datname
FROM pg_catalog.pg_database
WHERE datallowconn
  AND NOT datistemplate
  AND has_database_privilege(oid, 'CONNECT')
ORDER BY datname
"""


async def discover_postgres_databases(bootstrap_uri: str) -> set[str]:
    """Run the discovery query on a temporary connection that is always closed."""
    async with await AsyncConnection.connect(bootstrap_uri, autocommit=True) as conn:
        cursor = await conn.execute(_DISCOVERY_SQL)
        return {row[0] for row in await cursor.fetchall()}


_MAX_STALE_GRACE_SECONDS = 300
_DISCOVERY_TIMEOUT_SECONDS = 10


class DiscoveryUnavailableError(Exception):
    """Discovery failed and no snapshot may be served."""


class DatabaseConfigurationError(Exception):
    """The configured default database is not eligible."""


class DatabaseCatalog:
    def __init__(
        self,
        config: DatabaseConfig,
        discover: Callable[[str], Awaitable[set[str]]] = discover_postgres_databases,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._config = config
        self._discover = discover
        self._clock = clock or time.monotonic
        self._discovered: set[str] | None = None
        self._expires_at = 0.0
        self._inflight: asyncio.Task[None] | None = None
        self._generation = 0
        if config.auto_discover:
            self._check_default({config.default_database} if config.default_database else set())

    def _filter(self, discovered: set[str]) -> list[str]:
        allowed = set(self._config.allowed_databases)
        excluded = set(self._config.excluded_databases)
        return sorted(n for n in discovered if n not in excluded and (not allowed or n in allowed))

    def _check_default(self, discovered: set[str]) -> None:
        default = self._config.default_database
        if default and default not in self._filter(discovered):
            raise DatabaseConfigurationError(f"Default database {default!r} is not eligible")

    async def _fetch(self) -> None:
        try:
            async with asyncio.timeout(_DISCOVERY_TIMEOUT_SECONDS):
                found = await self._discover(self._config.bootstrap_uri)
        except Exception:
            # Fixed message: driver errors can embed the URI or password.
            raise DiscoveryUnavailableError("Database discovery is unavailable") from None
        self._check_default(found)
        self._discovered = found
        self._expires_at = self._clock() + self._config.discovery_ttl_seconds
        self._generation += 1

    async def _refresh(self) -> None:
        if self._inflight is None:
            task = asyncio.ensure_future(self._fetch())
            task.add_done_callback(self._fetch_done)
            self._inflight = task
        await asyncio.shield(self._inflight)

    def _fetch_done(self, task: "asyncio.Task[None]") -> None:
        self._inflight = None
        if not task.cancelled():
            task.exception()  # mark retrieved even if every waiter was cancelled

    async def names(self, refresh: bool = False) -> tuple[list[str], bool]:
        """Return (sorted authorized names, is_stale)."""
        if not self._config.auto_discover:
            default = self._config.default_database
            return ([default] if default else []), False
        if self._discovered is not None and not refresh and self._clock() < self._expires_at:
            return self._filter(self._discovered), False
        try:
            await self._refresh()
        except DiscoveryUnavailableError:
            ttl = self._config.discovery_ttl_seconds
            grace = min(_MAX_STALE_GRACE_SECONDS, 2 * ttl)
            if self._discovered is None or self._clock() > self._expires_at + grace:
                raise
            return self._filter(self._discovered), True
        assert self._discovered is not None
        return self._filter(self._discovered), False

    async def authorize(self, requested: str) -> str:
        """Validate an exact name; the error never includes the URI or credentials."""
        generation = self._generation
        names, _ = await self.names()
        if requested not in names and self._generation == generation:
            names, _ = await self.names(refresh=True)
        if requested not in names:
            raise ValueError(f"Database {requested!r} is not available")
        return requested
