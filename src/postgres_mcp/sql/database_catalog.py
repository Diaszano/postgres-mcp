"""Discovery and authorization of databases on the bootstrap PostgreSQL instance."""

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


class DatabaseCatalog:
    def __init__(
        self,
        config: DatabaseConfig,
        discover: Callable[[str], Awaitable[set[str]]] = discover_postgres_databases,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._config = config
        self._discover = discover
        self._clock = clock  # used by the TTL logic added in Task 5
        self._discovered: set[str] | None = None

    def _filter(self, discovered: set[str]) -> list[str]:
        allowed = set(self._config.allowed_databases)
        excluded = set(self._config.excluded_databases)
        return sorted(n for n in discovered if n not in excluded and (not allowed or n in allowed))

    async def names(self, refresh: bool = False) -> tuple[list[str], bool]:
        """Return (sorted authorized names, is_stale)."""
        if not self._config.auto_discover:
            default = self._config.default_database
            return ([default] if default else []), False
        if refresh or self._discovered is None:
            self._discovered = await self._discover(self._config.bootstrap_uri)
        return self._filter(self._discovered), False

    async def authorize(self, requested: str) -> str:
        """Validate an exact name; the error never includes the URI or credentials."""
        names, _ = await self.names()
        if requested not in names:
            raise ValueError(f"Database {requested!r} is not available")
        return requested
