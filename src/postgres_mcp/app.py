"""FastMCP application factory with explicit lifespan and runtime isolation."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from mcp.server.fastmcp import FastMCP

from postgres_mcp.runtime import AppRuntime


def create_mcp_app(runtime: AppRuntime | None = None, name: str = "postgres-mcp") -> FastMCP:
    """Create a configured FastMCP application instance bound to an explicit runtime."""
    active_runtime = runtime if runtime is not None else AppRuntime()

    @asynccontextmanager
    async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
        yield {"runtime": active_runtime}
        await active_runtime.close()

    app = FastMCP(name, lifespan=app_lifespan)
    # Store runtime reference on the FastMCP instance for direct test access
    setattr(app, "runtime", active_runtime)
    return app
