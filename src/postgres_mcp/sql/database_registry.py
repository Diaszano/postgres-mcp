"""Per-database lazy connection pools with single-flight creation and per-call leases.

Concurrency model: every state transition is a synchronous block with no `await`
inside, so under asyncio it is atomic (this is the "short lock"). Pool I/O
(open/close) always happens outside those blocks, so one database never waits
on another.

Lifecycle: opening -> open -> closing -> (removed). Every registered entry counts
against `max_pools`. Only an `open` entry with zero leases may be closed, and it
is switched to `closing` in the same synchronous block that picks it, so no
caller can lease it afterwards. Closes run as tracked tasks, shielded from the
callers' cancellation.
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
from postgres_mcp.security.errors import DatabaseNotAllowedError

from .database_catalog import DatabaseCatalog
from .database_catalog import DiscoveryUnavailableError
from .sql_driver import DbConnPool

logger = logging.getLogger(__name__)

_SHUTDOWN_GRACE_SECONDS = 10.0

ConnectionState = Literal["not_connected", "connected", "unavailable"]


class DatabaseUnavailableError(Exception):
    """A pool for an authorized database could not be opened."""


class PoolCapacityError(Exception):
    """Every pool slot is held by an active lease; nothing may be evicted."""


@dataclass(frozen=True)
class DatabaseInfo:
    name: str
    is_default: bool
    connection_state: ConnectionState
    catalog_stale: bool


@dataclass(eq=False)
class _Entry:
    name: str
    pool: DbConnPool
    state: Literal["opening", "open", "closing", "failed"] = "opening"
    leases: int = 0
    last_used: float = 0.0
    revoked: bool = False  # close once the last lease is released
    ready: asyncio.Event = field(default_factory=asyncio.Event)
    closed: asyncio.Event = field(default_factory=asyncio.Event)
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
        self._closers: set[asyncio.Task[None]] = set()
        self._shut_down = False

    def _default_factory(self, name: str) -> DbConnPool:
        # DSN always derived from the bootstrap URI, never from agent input.
        min_size = 0 if self._config.auto_discover else 1
        return DbConnPool(build_database_conninfo(self._config, name), min_size=min_size, max_size=self._config.pool_max_size)

    async def start(self) -> None:
        """Validate the default database; a transient discovery outage starts degraded."""
        try:
            await self._catalog.names()
        except DiscoveryUnavailableError:
            logger.warning("Database discovery is unavailable at startup; starting degraded")

    def active_leases(self, name: str) -> int:
        entry = self._entries.get(name)
        return entry.leases if entry else 0

    async def list_databases(self, *, refresh: bool = False) -> list[DatabaseInfo]:
        """Report authorized databases and pool state; never opens a pool."""
        names, stale = await self._catalog.names(refresh=refresh)
        self._sweep(names, keep=None)
        return [DatabaseInfo(n, n == self._config.default_database, self._state(n), stale) for n in names]

    def _state(self, name: str) -> ConnectionState:
        entry = self._entries.get(name)
        if entry is not None and entry.state == "open":
            return "connected"
        return "unavailable" if name in self._unavailable else "not_connected"

    @asynccontextmanager
    async def acquire(self, database: str | None = None) -> AsyncIterator[DbConnPool]:
        """Hold a lease on the database's pool for the whole `async with` body."""
        self._ensure_running()
        requested = database if database is not None else self._config.default_database
        if requested is None:
            raise ValueError("No default database is configured")
        name = await self._catalog.authorize(requested)
        # Read after authorize, so a forced refresh inside it is reflected (cache hit).
        names, _ = await self._catalog.names()
        authorized = name in names
        self._sweep(names, keep=name if authorized else None)
        if not authorized:
            raise DatabaseNotAllowedError("The requested database is not available.")
        entry = await self._lease(name)
        try:
            yield entry.pool
        finally:
            self._release(entry)

    async def close_all(self) -> None:
        """Idempotent shutdown: refuse new leases, drain active ones, close every pool."""
        self._shut_down = True
        for entry in list(self._entries.values()):
            entry.revoked = True
            if entry.state == "open" and entry.leases == 0:
                self._retire(entry)
        try:
            async with asyncio.timeout(_SHUTDOWN_GRACE_SECONDS):
                while self._entries:
                    await next(iter(self._entries.values())).closed.wait()
        except TimeoutError:
            # Leases still active after the grace period: their calls fail on a closed pool.
            logger.warning("Closing database pools with active leases: %s", ", ".join(sorted(self._entries)))
            for entry in list(self._entries.values()):
                if entry.state == "open":
                    self._retire(entry)
        # Shielded: cancelling close_all must not cancel the pool closes themselves.
        await asyncio.shield(asyncio.gather(*self._closers))

    def _ensure_running(self) -> None:
        if self._shut_down:
            raise DatabaseUnavailableError("The database registry is shut down")

    def _sweep(self, names: list[str], keep: str | None) -> None:
        """Opportunistic cleanup: close idle pools that expired or whose database was revoked."""
        authorized = set(names)
        idle_before = self._clock() - self._config.pool_idle_seconds
        for entry in list(self._entries.values()):
            entry.revoked = self._shut_down or entry.name not in authorized
            if entry.name == keep or entry.state != "open" or entry.leases:
                continue
            if entry.revoked or entry.last_used <= idle_before:
                self._retire(entry)

    def _release(self, entry: _Entry) -> None:
        entry.leases -= 1
        entry.last_used = self._clock()
        if entry.leases == 0 and entry.revoked and entry.state == "open":
            self._retire(entry)

    def _make_room(self) -> asyncio.Event | None:
        """Return None when a slot is free, else an event to wait on; raise when all slots are leased."""
        if len(self._entries) < self._config.max_pools:
            return None
        idle = [e for e in self._entries.values() if e.state == "open" and e.leases == 0]
        if idle:
            victim = min(idle, key=lambda e: e.last_used)  # ties: oldest registration wins
            self._retire(victim)
            return victim.closed
        for entry in self._entries.values():
            if entry.state == "closing":
                return entry.closed
        raise PoolCapacityError(f"All {self._config.max_pools} database pools are in use; retry later")

    def _retire(self, entry: _Entry) -> None:
        """Switch an unleased entry to closing; it keeps its slot until the pool is closed."""
        entry.state = "closing"
        self._close_later(entry.pool).add_done_callback(lambda _: self._forget(entry))

    def _forget(self, entry: _Entry) -> None:
        if self._entries.get(entry.name) is entry:
            del self._entries[entry.name]
        entry.closed.set()

    def _close_later(self, pool: DbConnPool) -> "asyncio.Task[None]":
        task = asyncio.ensure_future(self._close_pool(pool))
        self._closers.add(task)
        task.add_done_callback(self._closers.discard)
        return task

    @staticmethod
    async def _close_pool(pool: DbConnPool) -> None:
        try:
            await pool.close()
        except Exception as exc:
            logger.warning("Closing a database pool failed (%s)", type(exc).__name__)

    async def _lease(self, name: str) -> _Entry:
        """Return an open entry with one lease already counted for the caller."""
        while True:
            self._ensure_running()
            entry = self._entries.get(name)
            if entry is not None and entry.state == "closing":
                await entry.closed.wait()
                continue
            if entry is None:
                wait = self._make_room()
                if wait is not None:
                    await wait.wait()
                    continue
                entry = _Entry(name=name, pool=self._factory(name))
                self._entries[name] = entry
                entry.leases += 1
                await self._open(entry)
            else:
                # Reserve the lease before waiting, so the pool is never open with zero leases.
                entry.leases += 1
                if entry.state == "opening":
                    try:
                        await entry.ready.wait()
                    except BaseException:
                        if entry.state == "open":
                            self._release(entry)
                        else:
                            entry.leases -= 1
                        raise
            if entry.state == "open":
                if self._shut_down:
                    self._release(entry)
                    self._ensure_running()
                entry.last_used = self._clock()
                return entry
            entry.leases -= 1
            if entry.error is not None:
                raise DatabaseUnavailableError(str(entry.error))
            # Opener was cancelled and already dropped the entry: retry with a fresh one.
            assert self._entries.get(name) is not entry, "retry on a registered non-open entry"

    async def _open(self, entry: _Entry) -> None:
        """Open the pool outside any critical section; the caller's lease is already counted."""
        name = entry.name
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
            entry.closed.set()
            # Shielded: a second cancel must not leave a half-closed pool.
            await asyncio.shield(self._close_later(entry.pool))
            if entry.error is not None:
                raise entry.error from None
            raise
        entry.state = "open"
        entry.last_used = self._clock()
        self._unavailable.discard(name)
        entry.ready.set()
