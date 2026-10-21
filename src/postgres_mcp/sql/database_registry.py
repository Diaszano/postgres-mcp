"""Per-database lazy connection pools with single-flight creation and per-call leases.

Concurrency model: every state transition is a synchronous block with no `await`
inside, so under asyncio it is atomic (this is the "short lock"). Pool I/O
(open/close) always happens outside those blocks, so one database never waits
on another.
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from dataclasses import field
from typing import Literal

from postgres_mcp.database_config import DatabaseConfig
from postgres_mcp.database_config import build_database_conninfo

from .database_catalog import DatabaseCatalog
from .sql_driver import DbConnPool

logger = logging.getLogger(__name__)

ConnectionState = Literal["not_connected", "connected", "unavailable"]


class DatabaseUnavailableError(Exception):
    """A pool for an authorized database could not be opened."""


@dataclass(frozen=True)
class DatabaseInfo:
    name: str
    is_default: bool
    connection_state: ConnectionState
    catalog_stale: bool


@dataclass(eq=False)
class _Entry:
    pool: DbConnPool
    state: Literal["opening", "open", "closing", "failed"] = "opening"
    leases: int = 0
    last_used: float = 0.0
    ready: asyncio.Event = field(default_factory=asyncio.Event)
    error: DatabaseUnavailableError | None = None  # None with state "failed" means the opener was cancelled


class DatabaseRegistry:
    def __init__(
        self,
        config: DatabaseConfig,
        catalog: DatabaseCatalog,
        pool_factory: Callable[[str], DbConnPool] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._catalog = catalog
        self._factory = pool_factory or self._default_factory
        self._clock = clock
        self._entries: dict[str, _Entry] = {}
        self._unavailable: set[str] = set()

    def _default_factory(self, name: str) -> DbConnPool:
        # DSN always derived from the bootstrap URI, never from agent input.
        min_size = 0 if self._config.auto_discover else 1
        return DbConnPool(build_database_conninfo(self._config, name), min_size=min_size, max_size=self._config.pool_max_size)

    def active_leases(self, name: str) -> int:
        entry = self._entries.get(name)
        return entry.leases if entry else 0

    async def list_databases(self, *, refresh: bool = False) -> list[DatabaseInfo]:
        """Report authorized databases and pool state; never opens a pool."""
        names, stale = await self._catalog.names(refresh=refresh)
        return [DatabaseInfo(n, n == self._config.default_database, self._state(n), stale) for n in names]

    def _state(self, name: str) -> ConnectionState:
        entry = self._entries.get(name)
        if entry is not None and entry.state == "open":
            return "connected"
        return "unavailable" if name in self._unavailable else "not_connected"

    @asynccontextmanager
    async def acquire(self, database: str | None = None) -> AsyncIterator[DbConnPool]:
        """Hold a lease on the database's pool for the whole `async with` body."""
        requested = database if database is not None else self._config.default_database
        if requested is None:
            raise ValueError("No default database is configured")
        name = await self._catalog.authorize(requested)
        entry = await self._lease(name)
        try:
            yield entry.pool
        finally:
            entry.leases -= 1
            entry.last_used = self._clock()

    async def _lease(self, name: str) -> _Entry:
        """Return an open entry with one lease already counted for the caller."""
        while True:
            entry = self._entries.get(name)
            if entry is None:
                entry = _Entry(pool=self._factory(name))
                self._entries[name] = entry
                entry.leases += 1
                await self._open(name, entry)
                return entry

            # Reserve the lease before waiting, so the pool is never open with zero leases.
            entry.leases += 1
            if entry.state == "opening":
                try:
                    await entry.ready.wait()
                except BaseException:
                    entry.leases -= 1
                    raise
            if entry.state == "open":
                entry.last_used = self._clock()
                return entry
            entry.leases -= 1
            if entry.error is not None:
                raise DatabaseUnavailableError(str(entry.error))
            # Opener was cancelled and already dropped the entry: retry with a fresh one.
            # Guard against a busy loop if a later state ("closing") keeps the entry registered.
            assert self._entries.get(name) is not entry, "retry on a registered non-open entry"

    async def _open(self, name: str, entry: _Entry) -> None:
        """Open the pool outside any critical section; the caller's lease is already counted."""
        try:
            await entry.pool.pool_connect()
        except BaseException as exc:
            entry.leases -= 1
            entry.state = "failed"
            if self._entries.get(name) is entry:
                del self._entries[name]
            if isinstance(exc, Exception):
                self._unavailable.add(name)
                # Fixed message: driver errors can embed the host, DSN or password.
                entry.error = DatabaseUnavailableError(f"Database {name!r} is unavailable")
                logger.warning("Opening pool for database %r failed (%s)", name, type(exc).__name__)
            entry.ready.set()
            await entry.pool.close()
            if entry.error is not None:
                raise entry.error from None
            raise
        entry.state = "open"
        entry.last_used = self._clock()
        self._unavailable.discard(name)
        entry.ready.set()
