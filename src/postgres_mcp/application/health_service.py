"""Application service for database health and top queries inspection."""

from collections.abc import Callable
from typing import Any

from postgres_mcp.database_health import DatabaseHealthTool
from postgres_mcp.top_queries import TopQueriesCalc


class HealthInspectionService:
    """Service encapsulating health checks and query resource stats."""

    def __init__(
        self,
        driver_factory: Callable[..., Any],
        health_tool_cls: type = DatabaseHealthTool,
        top_queries_cls: type = TopQueriesCalc,
    ) -> None:
        self.driver_factory = driver_factory
        self.health_tool_cls = health_tool_cls
        self.top_queries_cls = top_queries_cls

    async def check_health(self, health_type: str = "all", database: str | None = None) -> Any:
        """Run requested database health checks."""
        async with self.driver_factory(database) as sql_driver:
            health_tool = self.health_tool_cls(sql_driver)
            return await health_tool.health(health_type=health_type)

    async def get_top_queries(
        self,
        sort_by: str = "resources",
        limit: int = 10,
        database: str | None = None,
    ) -> Any:
        """Get resource-intensive or slow queries."""
        async with self.driver_factory(database) as sql_driver:
            top_queries_tool = self.top_queries_cls(sql_driver=sql_driver)
            if sort_by == "resources":
                return await top_queries_tool.get_top_resource_queries()
            if sort_by in ("mean_time", "total_time"):
                return await top_queries_tool.get_top_queries_by_time(
                    limit=limit,
                    sort_by="mean" if sort_by == "mean_time" else "total",
                )
            raise ValueError("Invalid sort criteria. Please use 'resources' or 'mean_time' or 'total_time'.")
