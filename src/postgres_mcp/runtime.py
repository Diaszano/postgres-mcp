"""Explicit application runtime and lifecycle dependencies."""

from dataclasses import dataclass
from dataclasses import field
from typing import Any

from postgres_mcp.database_config import DatabaseConfig
from postgres_mcp.observability.status import RuntimeStatus
from postgres_mcp.pagination.cursors import InMemoryCursorStore
from postgres_mcp.query_limits.admission import QueryAdmission
from postgres_mcp.query_limits.config import QueryBudgetConfig
from postgres_mcp.sql import DbConnPool
from postgres_mcp.sql.database_registry import DatabaseRegistry


@dataclass
class AppRuntime:
    """Encapsulates the state and lifecycle dependencies for an MCP instance."""

    access_mode: str = "unrestricted"
    database_config: DatabaseConfig | None = None
    registry: DatabaseRegistry | None = None
    db_connection: Any = field(default_factory=DbConnPool)
    query_budget_config: QueryBudgetConfig = field(default_factory=QueryBudgetConfig)
    query_admission: QueryAdmission = field(init=False)
    cursor_store: InMemoryCursorStore = field(default_factory=InMemoryCursorStore)
    pagination_enabled: bool = True
    pagination_default_page_size: int = 100
    pagination_max_page_size: int = 1000
    shutdown_in_progress: bool = False

    def __post_init__(self) -> None:
        self.query_admission = QueryAdmission(self.query_budget_config.max_concurrency)

    async def close(self) -> None:
        """Idempotently close all pools, registries, and cursor stores."""
        if self.shutdown_in_progress:
            return
        self.shutdown_in_progress = True
        self.cursor_store.invalidate_all()
        if self.registry is not None:
            if hasattr(self.registry, "close"):
                await self.registry.close()
            elif hasattr(self.registry, "close_all"):
                await self.registry.close_all()
        if self.db_connection is not None:
            if hasattr(self.db_connection, "close"):
                await self.db_connection.close()

    def status(self) -> RuntimeStatus:
        """Return the current operational status snapshot."""
        return RuntimeStatus(
            server_ready=not self.shutdown_in_progress,
            catalog_degraded=False,
            active_pools=len(getattr(self.registry, "_entries", {})) if self.registry else 1,
            active_cursors=len(getattr(self.cursor_store, "_entries", {})),
        )
