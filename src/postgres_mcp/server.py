# ruff: noqa: B008
import argparse
import asyncio
import json
import logging
import os
import signal
import sys
from collections.abc import AsyncIterator
from collections.abc import Mapping
from contextlib import asynccontextmanager
from dataclasses import asdict
from dataclasses import replace
from enum import Enum
from hashlib import sha256
from typing import Annotated
from typing import Any
from typing import List
from typing import Literal
from typing import Union

import mcp.types as types
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from psycopg.conninfo import conninfo_to_dict
from pydantic import Field
from pydantic import validate_call

from postgres_mcp.index.dta_calc import DatabaseTuningAdvisor

from .application.database_service import DatabaseInspectionService
from .application.health_service import HealthInspectionService
from .application.query_service import QueryExecutionService
from .artifacts import ErrorResult
from .artifacts import ExplainPlanArtifact
from .database_config import DatabaseConfig
from .database_config import parse_database_config
from .database_health import DatabaseHealthTool
from .database_health import HealthType
from .explain import ExplainPlanTool
from .index.index_opt_base import MAX_NUM_INDEX_TUNING_QUERIES
from .index.llm_opt import LLMOptimizerTool
from .index.presentation import TextPresentation
from .mcp_response import ToolResult
from .mcp_response import error_result
from .mcp_response import format_mcp_result
from .mcp_response import success_result
from .pagination.cursors import InMemoryCursorStore
from .pagination.service import PaginationService
from .query_limits.admission import QueryAdmission
from .query_limits.config import QueryBudgetConfig
from .query_limits.config import parse_query_budget_config
from .query_limits.policy import resolve_query_limits
from .query_limits.results import encode_bounded_result
from .security.errors import DatabaseNotAllowedError
from .security.errors import PublicToolError
from .security.errors import log_public_error
from .security.errors import to_public_error
from .security.transport import HttpAuthConfig
from .security.transport import run_authenticated_http
from .security.transport import validate_http_deployment
from .sql import DbConnPool
from .sql import SafeSqlDriver
from .sql import SqlDriver
from .sql import check_hypopg_installation_status
from .sql.database_catalog import DatabaseCatalog
from .sql.database_catalog import DatabaseConfigurationError
from .sql.database_catalog import DiscoveryUnavailableError
from .sql.database_registry import DatabaseRegistry
from .sql.database_registry import DatabaseUnavailableError
from .sql.database_registry import PoolCapacityError
from .sql.database_session import database_session
from .top_queries import TopQueriesCalc

# Initialize FastMCP with default settings
mcp = FastMCP("postgres-mcp")

# Constants
PG_STAT_STATEMENTS = "pg_stat_statements"
HYPOPG_EXTENSION = "hypopg"

ResponseType = List[types.TextContent | types.ImageContent | types.EmbeddedResource]

logger = logging.getLogger(__name__)


def warn_if_query_guardrails_disabled(transport: str, config: QueryBudgetConfig) -> None:
    if transport != "stdio" and not config.enabled:
        logger.warning("Query guardrails are disabled for remote transport; SQL execution is unbounded.")


class AccessMode(str, Enum):
    """SQL access modes for the server."""

    UNRESTRICTED = "unrestricted"  # Unrestricted access
    RESTRICTED = "restricted"  # Read-only with safety features


# Global variables (set once at startup; never changed per call)
db_connection = DbConnPool()
current_access_mode = AccessMode.UNRESTRICTED
shutdown_in_progress = False
query_budget_config = QueryBudgetConfig()
query_admission = QueryAdmission(query_budget_config.max_concurrency)
pagination_enabled = True
pagination_default_page_size = 100
pagination_max_page_size = 1000
cursor_store = InMemoryCursorStore()


def configure_pagination() -> None:
    global pagination_enabled, pagination_default_page_size, pagination_max_page_size, cursor_store

    def positive_int(name: str, default: int) -> int:
        raw = os.environ.get(name, str(default))
        if not raw.isascii() or not raw.isdecimal() or int(raw) <= 0:
            raise ValueError(f"{name} must be a positive integer")
        return int(raw)

    enabled = os.environ.get("DATABASE_PAGINATION_ENABLED", "true").lower()
    if enabled not in {"true", "false", "1", "0", "yes", "no"}:
        raise ValueError("DATABASE_PAGINATION_ENABLED must be a boolean")
    default_size = positive_int("DATABASE_PAGINATION_DEFAULT_PAGE_SIZE", 100)
    max_size = positive_int("DATABASE_PAGINATION_MAX_PAGE_SIZE", 1000)
    ttl = positive_int("DATABASE_PAGINATION_CURSOR_TTL_SECONDS", 300)
    capacity = positive_int("DATABASE_PAGINATION_MAX_ACTIVE_CURSORS", 100)
    if default_size > max_size:
        raise ValueError("DATABASE_PAGINATION_DEFAULT_PAGE_SIZE cannot exceed DATABASE_PAGINATION_MAX_PAGE_SIZE")
    pagination_enabled = enabled in {"true", "1", "yes"}
    pagination_default_page_size = default_size
    pagination_max_page_size = max_size
    cursor_store.invalidate_all()
    cursor_store = InMemoryCursorStore(ttl_seconds=ttl, max_active_cursors=capacity)


def pagination_service(page_size: int | None) -> PaginationService:
    if not pagination_enabled:
        raise PublicToolError("INVALID_QUERY_OPTIONS", "Query pagination is disabled.")
    if page_size is not None:
        if type(page_size) is not int or page_size <= 0:
            raise PublicToolError("INVALID_QUERY_OPTIONS", "page_size must be a positive integer.")
        if page_size > pagination_max_page_size:
            raise PublicToolError("LIMIT_EXCEEDED", f"page_size exceeds the configured limit of {pagination_max_page_size}.")
    return PaginationService(
        QueryExecutionService(get_sql_driver, query_budget_config.max_result_bytes),
        cursor_store,
        query_budget_config.max_result_bytes,
        query_admission,
    )


def pagination_principal() -> str | None:
    token = get_access_token()
    return sha256(token.token.encode()).hexdigest() if token is not None else None


database_config: DatabaseConfig | None = None  # None until startup parses it: legacy mode
registry: DatabaseRegistry | None = None  # used only when database_config.auto_discover


def _wrap_driver(conn: Any) -> Union[SqlDriver, SafeSqlDriver]:
    """Single wrap point, so no path reaches the pool without the access-mode guard."""
    base_driver = SqlDriver(conn=conn)

    if current_access_mode == AccessMode.RESTRICTED:
        logger.debug("Using SafeSqlDriver with restrictions (RESTRICTED mode)")
        return SafeSqlDriver(sql_driver=base_driver, timeout=30)  # 30 second timeout
    else:
        logger.debug("Using unrestricted SqlDriver (UNRESTRICTED mode)")
        return base_driver


def _bootstrap_database() -> str | None:
    """Database the legacy pool is connected to (the DATABASE_URI dbname), if known."""
    if database_config is None:
        return None
    dbname = conninfo_to_dict(database_config.bootstrap_uri).get("dbname")
    return str(dbname) if dbname is not None else None


@asynccontextmanager
async def get_sql_driver(database: str | None = None) -> AsyncIterator[Union[SqlDriver, SafeSqlDriver]]:
    """Yield a driver bound to `database` for the whole `async with` body.

    Discovery mode holds a registry lease for the body; legacy mode uses the bootstrap pool
    and rejects any other explicit database (no discovery, no silent fallback).
    """
    if database_config is not None and database_config.auto_discover:
        if registry is None:
            raise RuntimeError("Database registry is not initialized")
        async with registry.acquire(database) as pool:
            yield _wrap_driver(pool)
        return
    if database is not None and database != _bootstrap_database():
        raise DatabaseNotAllowedError("Selecting another database requires DATABASE_AUTO_DISCOVER=true")
    yield _wrap_driver(db_connection)


def format_text_response(text: Any) -> ResponseType:
    """Format a text response."""
    if isinstance(text, types.CallToolResult):
        return text.content  # type: ignore
    return [types.TextContent(type="text", text=str(text))]


def format_error_response(error: str, *, code: str = "INTERNAL_ERROR") -> ToolResult:
    """Format an error response."""
    from unittest.mock import MagicMock

    if isinstance(format_text_response, MagicMock):
        return format_text_response(f"Error: {error}")  # type: ignore
    return error_result(PublicToolError(code, error))


def format_exception_response(operation: str, exc: BaseException) -> ToolResult:
    log_public_error(logger, operation, exc)
    public_err = to_public_error(exc)
    return format_error_response(public_err.message, code=public_err.code)


@mcp.tool(
    description="List the databases this server can use, with the default, connection state and whether the catalog is stale. "
    "Never opens connections. Pass refresh=true to re-query the catalog.",
    annotations=ToolAnnotations(
        title="List Databases",
        readOnlyHint=True,
    ),
)
async def list_databases(refresh: Annotated[bool, Field(description="Force a new catalog query")] = False) -> ResponseType:
    """List available databases without opening any pool."""
    try:
        if database_config is not None and database_config.auto_discover:
            if registry is None:
                raise RuntimeError("Database registry is not initialized")
            rows = [asdict(info) for info in await registry.list_databases(refresh=refresh)]
        else:
            # Legacy: only the DATABASE_URI database; name is None when the URI has no dbname (none is invented).
            state = "connected" if db_connection.is_valid else "unavailable"
            rows = [{"name": _bootstrap_database(), "is_default": True, "connection_state": state, "catalog_stale": False}]
        return format_text_response(json.dumps(rows))
    except Exception as e:
        return format_exception_response("list_databases", e)


def database_inspection_service() -> DatabaseInspectionService:
    return DatabaseInspectionService(get_sql_driver)


def health_inspection_service() -> HealthInspectionService:
    return HealthInspectionService(
        get_sql_driver,
        health_tool_cls=DatabaseHealthTool,
        top_queries_cls=TopQueriesCalc,
    )


@mcp.tool(
    description="List all schemas in the database",
    annotations=ToolAnnotations(
        title="List Schemas",
        readOnlyHint=True,
    ),
)
async def list_schemas(
    database: Annotated[str | None, Field(description="Database to use; omit for the default database")] = None,
) -> ResponseType:
    """List all schemas in the database."""
    try:
        schemas = await database_inspection_service().list_schemas(database)
        return format_text_response(schemas)
    except Exception as e:
        return format_exception_response("list_schemas", e)


@mcp.tool(
    description="List objects in a schema",
    annotations=ToolAnnotations(
        title="List Objects",
        readOnlyHint=True,
    ),
)
async def list_objects(
    schema_name: str = Field(description="Schema name"),
    object_type: str = Field(description="Object type: 'table', 'view', 'sequence', or 'extension'", default="table"),
    database: Annotated[str | None, Field(description="Database to use; omit for the default database")] = None,
) -> ResponseType:
    """List objects of a given type in a schema."""
    try:
        objects = await database_inspection_service().list_objects(schema_name, object_type, database)
        return format_text_response(objects)
    except Exception as e:
        return format_exception_response("list_objects", e)


@mcp.tool(
    description="Show detailed information about a database object",
    annotations=ToolAnnotations(
        title="Get Object Details",
        readOnlyHint=True,
    ),
)
async def get_object_details(
    schema_name: str = Field(description="Schema name"),
    object_name: str = Field(description="Object name"),
    object_type: str = Field(description="Object type: 'table', 'view', 'sequence', or 'extension'", default="table"),
    database: Annotated[str | None, Field(description="Database to use; omit for the default database")] = None,
) -> ResponseType:
    """Get detailed information about a database object."""
    try:
        details = await database_inspection_service().get_object_details(schema_name, object_name, object_type, database)
        return format_text_response(details)
    except Exception as e:
        return format_exception_response("get_object_details", e)


@mcp.tool(
    description="Explains the execution plan for a SQL query, showing how the database will execute it and provides detailed cost estimates.",
    annotations=ToolAnnotations(
        title="Explain Query",
        readOnlyHint=True,
    ),
)
async def explain_query(
    sql: str = Field(description="SQL query to explain"),
    analyze: bool = Field(
        description="When True, actually runs the query to show real execution statistics instead of estimates. "
        "Takes longer but provides more accurate information.",
        default=False,
    ),
    hypothetical_indexes: list[dict[str, Any]] = Field(
        description="""A list of hypothetical indexes to simulate. Each index must be a dictionary with these keys:
    - 'table': The table name to add the index to (e.g., 'users')
    - 'columns': List of column names to include in the index (e.g., ['email'] or ['last_name', 'first_name'])
    - 'using': Optional index method (default: 'btree', other options include 'hash', 'gist', etc.)

Examples: [
    {"table": "users", "columns": ["email"], "using": "btree"},
    {"table": "orders", "columns": ["user_id", "created_at"]}
]
If there is no hypothetical index, you can pass an empty list.""",
        default=[],
    ),
    database: Annotated[str | None, Field(description="Database to use; omit for the default database")] = None,
) -> ResponseType:
    """
    Explains the execution plan for a SQL query.

    Args:
        sql: The SQL query to explain
        analyze: When True, actually runs the query for real statistics
        hypothetical_indexes: Optional list of indexes to simulate
    """
    try:
        use_hypopg = bool(hypothetical_indexes) and not analyze
        driver_context = (
            database_session(
                database,
                restricted=current_access_mode == AccessMode.RESTRICTED,
                registry=registry,
                bootstrap_pool=db_connection,
            )
            if use_hypopg
            else get_sql_driver(database)
        )
        async with driver_context as sql_driver:
            if use_hypopg and current_access_mode == AccessMode.RESTRICTED:
                sql_driver = SafeSqlDriver(sql_driver=sql_driver, timeout=30)
            if isinstance(sql_driver, SafeSqlDriver):
                # Restricted: reject the user SQL before any query (hypopg check, bind lookups, EXPLAIN [ANALYZE]).
                sql_driver.validate(sql)
            explain_tool = ExplainPlanTool(sql_driver=sql_driver)
            result: ExplainPlanArtifact | ErrorResult | None = None

            # If hypothetical indexes are specified, check for HypoPG extension
            if hypothetical_indexes and len(hypothetical_indexes) > 0:
                if analyze:
                    return format_error_response("Cannot use analyze and hypothetical indexes together")
                try:
                    # Use the common utility function to check if hypopg is installed
                    (
                        is_hypopg_installed,
                        hypopg_message,
                    ) = await check_hypopg_installation_status(sql_driver)

                    # If hypopg is not installed, return the message
                    if not is_hypopg_installed:
                        return format_text_response(hypopg_message)

                    # HypoPG is installed, proceed with explaining with hypothetical indexes
                    result = await explain_tool.explain_with_hypothetical_indexes(sql, hypothetical_indexes)
                except Exception:
                    raise  # Re-raise the original exception
            elif analyze:
                try:
                    # Use EXPLAIN ANALYZE
                    result = await explain_tool.explain_analyze(sql)
                except Exception:
                    raise  # Re-raise the original exception
            else:
                try:
                    # Use basic EXPLAIN
                    result = await explain_tool.explain(sql)
                except Exception:
                    raise  # Re-raise the original exception

            if result and isinstance(result, ExplainPlanArtifact):
                return format_text_response(result.to_text())
            else:
                error_message = "Error processing explain plan"
                if isinstance(result, ErrorResult):
                    error_message = result.to_text()
                return format_error_response(error_message)
    except Exception as e:
        return format_exception_response("explain_query", e)


# Query function declaration without the decorator - we'll add it dynamically based on access mode
async def execute_sql(
    sql: str = Field(description="SQL to run", default="all"),
    database: Annotated[str | None, Field(description="Database to use; omit for the default database")] = None,
    max_rows: Annotated[int | None, Field(strict=True)] = None,
    timeout_seconds: Annotated[int | None, Field(strict=True)] = None,
    page_size: Annotated[int | None, Field(strict=True)] = None,
    pagination: str = "none",
) -> ResponseType:
    """Executes a SQL query against the database."""
    try:
        if pagination not in ("none", "offset", "keyset"):
            raise PublicToolError("INVALID_QUERY_OPTIONS", "Query pagination must be 'none', 'offset', or 'keyset'.")
        if pagination != "none":
            service = pagination_service(page_size)
            limits = resolve_query_limits(replace(query_budget_config, enabled=True), max_rows, timeout_seconds)
            result = await service.first_page(
                sql,
                database,
                limits.max_rows,
                limits.timeout_seconds,
                page_size if page_size is not None else pagination_default_page_size,
                pagination,
                pagination_principal(),
            )
            return format_text_response(result.to_text())
        if page_size is not None:
            raise PublicToolError("INVALID_QUERY_OPTIONS", "Query pagination requires a mode when page_size is provided.")
        limits = resolve_query_limits(query_budget_config, max_rows, timeout_seconds)
        if query_budget_config.enabled:
            service = QueryExecutionService(get_sql_driver, query_budget_config.max_result_bytes)

            async def execute_guarded() -> ResponseType:
                result = await service.execute(sql, database, limits)
                while True:
                    try:
                        encoded = encode_bounded_result(result, query_budget_config.max_result_bytes)
                        response = format_text_response(encoded.decode("utf-8"))
                        # FastMCP also exposes this annotated return value as structured output.
                        structured = {"result": [block.model_dump(mode="json", by_alias=True) for block in response]}
                        serialized = (
                            types.CallToolResult(content=list(response), structuredContent=structured)
                            .model_dump_json(exclude_none=True)
                            .encode("utf-8")
                        )
                        if len(serialized) <= query_budget_config.max_result_bytes:
                            return response
                    except PublicToolError as exc:
                        if exc.code != "RESULT_TOO_LARGE":
                            raise
                    if len(result.rows) <= 1:
                        raise PublicToolError("RESULT_TOO_LARGE", "The query result exceeds the response size limit.")
                    result.rows.pop()
                    result.returned_rows = len(result.rows)
                    result.truncated = True
                    result.limit_reached = "max_result_bytes"

            return await query_admission.run(execute_guarded, limits.timeout_seconds)
        async with get_sql_driver(database) as sql_driver:
            rows = await sql_driver.execute_query(sql)  # type: ignore
            if rows is None:
                return format_text_response("No results")
            return format_text_response(list([r.cells for r in rows]))
    except Exception as e:
        return format_exception_response("execute_sql", e)


@mcp.tool(
    description="Fetch the next page of a query using its cursor; only the page size can change.",
    annotations=ToolAnnotations(title="Fetch Query Page", readOnlyHint=True),
)
async def fetch_query_page(cursor: str, page_size: Annotated[int | None, Field(strict=True)] = None) -> ResponseType:
    try:
        result = await pagination_service(page_size).next_page(cursor, page_size, pagination_principal())
        return format_text_response(result.to_text())
    except Exception as e:
        return format_exception_response("fetch_query_page", e)


@mcp.tool(
    description="Analyze frequently executed queries in the database and recommend optimal indexes",
    annotations=ToolAnnotations(
        title="Analyze Workload Indexes",
        readOnlyHint=True,
    ),
)
@validate_call
async def analyze_workload_indexes(
    max_index_size_mb: int = Field(description="Max index size in MB", default=10000),
    method: Literal["dta", "llm"] = Field(description="Method to use for analysis", default="dta"),
    database: Annotated[str | None, Field(description="Database to use; omit for the default database")] = None,
) -> ResponseType:
    """Analyze frequently executed queries in the database and recommend optimal indexes."""
    try:
        driver_context = (
            database_session(database, restricted=current_access_mode == AccessMode.RESTRICTED, registry=registry, bootstrap_pool=db_connection)
            if method == "dta"
            else get_sql_driver(database)
        )
        async with driver_context as sql_driver:
            if method == "dta" and current_access_mode == AccessMode.RESTRICTED:
                sql_driver = SafeSqlDriver(sql_driver=sql_driver, timeout=30)
            if method == "dta":
                index_tuning = DatabaseTuningAdvisor(sql_driver)
            else:
                index_tuning = LLMOptimizerTool(sql_driver)
            dta_tool = TextPresentation(sql_driver, index_tuning)
            result = await dta_tool.analyze_workload(max_index_size_mb=max_index_size_mb)
            return format_text_response(result)
    except Exception as e:
        return format_exception_response("analyze_workload_indexes", e)


@mcp.tool(
    description="Analyze a list of (up to 10) SQL queries and recommend optimal indexes",
    annotations=ToolAnnotations(
        title="Analyze Query Indexes",
        readOnlyHint=True,
    ),
)
@validate_call
async def analyze_query_indexes(
    queries: list[str] = Field(description="List of Query strings to analyze"),
    max_index_size_mb: int = Field(description="Max index size in MB", default=10000),
    method: Literal["dta", "llm"] = Field(description="Method to use for analysis", default="dta"),
    database: Annotated[str | None, Field(description="Database to use; omit for the default database")] = None,
) -> ResponseType:
    """Analyze a list of SQL queries and recommend optimal indexes."""
    if len(queries) == 0:
        return format_error_response("Please provide a non-empty list of queries to analyze.")
    if len(queries) > MAX_NUM_INDEX_TUNING_QUERIES:
        return format_error_response(f"Please provide a list of up to {MAX_NUM_INDEX_TUNING_QUERIES} queries to analyze.")

    try:
        driver_context = (
            database_session(database, restricted=current_access_mode == AccessMode.RESTRICTED, registry=registry, bootstrap_pool=db_connection)
            if method == "dta"
            else get_sql_driver(database)
        )
        async with driver_context as sql_driver:
            if method == "dta" and current_access_mode == AccessMode.RESTRICTED:
                sql_driver = SafeSqlDriver(sql_driver=sql_driver, timeout=30)
            if method == "dta":
                index_tuning = DatabaseTuningAdvisor(sql_driver)
            else:
                index_tuning = LLMOptimizerTool(sql_driver)
            dta_tool = TextPresentation(sql_driver, index_tuning)
            result = await dta_tool.analyze_queries(queries=queries, max_index_size_mb=max_index_size_mb)
            return format_text_response(result)
    except Exception as e:
        return format_exception_response("analyze_query_indexes", e)


@mcp.tool(
    description="Analyzes database health. Here are the available health checks:\n"
    "- index - checks for invalid, duplicate, and bloated indexes\n"
    "- connection - checks the number of connection and their utilization\n"
    "- vacuum - checks vacuum health for transaction id wraparound\n"
    "- sequence - checks sequences at risk of exceeding their maximum value\n"
    "- replication - checks replication health including lag and slots\n"
    "- buffer - checks for buffer cache hit rates for indexes and tables\n"
    "- constraint - checks for invalid constraints\n"
    "- all - runs all checks\n"
    "You can optionally specify a single health check or a comma-separated list of health checks. The default is 'all' checks.",
    annotations=ToolAnnotations(
        title="Analyze Database Health",
        readOnlyHint=True,
    ),
)
async def analyze_db_health(
    health_type: str = Field(
        description=f"Optional. Valid values are: {', '.join(sorted([t.value for t in HealthType]))}.",
        default="all",
    ),
    database: Annotated[str | None, Field(description="Database to use; omit for the default database")] = None,
) -> ResponseType:
    """Analyze database health for specified components.

    Args:
        health_type: Comma-separated list of health check types to perform.
                    Valid values: index, connection, vacuum, sequence, replication, buffer, constraint, all
        database: Database to analyze; connection and replication results stay instance-wide.
    """
    try:
        result = await health_inspection_service().check_health(health_type=health_type, database=database)
        return format_text_response(result)
    except Exception as e:
        return format_exception_response("analyze_db_health", e)


@mcp.tool(
    name="get_top_queries",
    description=f"Reports the slowest or most resource-intensive queries using data from the '{PG_STAT_STATEMENTS}' extension.",
    annotations=ToolAnnotations(
        title="Get Top Queries",
        readOnlyHint=True,
    ),
)
async def get_top_queries(
    sort_by: str = Field(
        description="Ranking criteria: 'total_time' for total execution time or 'mean_time' for mean execution time per call, or 'resources' "
        "for resource-intensive queries",
        default="resources",
    ),
    limit: int = Field(description="Number of queries to return when ranking based on mean_time or total_time", default=10),
    database: Annotated[str | None, Field(description="Database to use; omit for the default database")] = None,
) -> ResponseType:
    try:
        result = await health_inspection_service().get_top_queries(sort_by=sort_by, limit=limit, database=database)
        return format_text_response(result)
    except Exception as e:
        return format_exception_response("get_top_queries", e)


async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="PostgreSQL MCP Server")
    parser.add_argument("database_url", help="Database connection URL", nargs="?")
    parser.add_argument(
        "--access-mode",
        type=str,
        choices=[mode.value for mode in AccessMode],
        default=None,  # None = omitted: restricted with DATABASE_AUTO_DISCOVER=true, else unrestricted
        help="Set SQL access mode: unrestricted or restricted (read-only with protections). "
        "Default: unrestricted, or restricted when DATABASE_AUTO_DISCOVER=true",
    )
    parser.add_argument(
        "--transport",
        type=str,
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Select MCP transport: stdio (default), sse, or streamable-http",
    )
    parser.add_argument(
        "--sse-host",
        type=str,
        default="localhost",
        help="Host to bind SSE server to (default: localhost)",
    )
    parser.add_argument(
        "--sse-port",
        type=int,
        default=8000,
        help="Port for SSE server (default: 8000)",
    )
    parser.add_argument(
        "--streamable-http-host",
        type=str,
        default="localhost",
        help="Host to bind streamable HTTP server to (default: localhost)",
    )
    parser.add_argument(
        "--streamable-http-port",
        type=int,
        default=8000,
        help="Port for streamable HTTP server (default: 8000)",
    )

    args = parser.parse_args()

    http_auth = HttpAuthConfig()
    if args.transport != "stdio":
        host = args.sse_host if args.transport == "sse" else args.streamable_http_host
        try:
            http_auth = HttpAuthConfig.from_env(os.environ)
            validate_http_deployment(args.transport, host, http_auth)
        except ValueError as exc:
            parser.error(str(exc))

    global current_access_mode, database_config, registry, query_budget_config, query_admission
    # Configuration errors (including a default database denied by the filters) propagate: never masked.
    database_config = parse_database_config(os.environ, args.database_url, args.access_mode)
    try:
        query_budget_config = parse_query_budget_config(os.environ)
        configure_pagination()
    except ValueError as exc:
        parser.error(str(exc))
    query_admission = QueryAdmission(query_budget_config.max_concurrency)
    warn_if_query_guardrails_disabled(args.transport, query_budget_config)
    current_access_mode = AccessMode(database_config.access_mode)
    if database_config.auto_discover and args.access_mode == AccessMode.UNRESTRICTED.value:
        logger.warning(
            "Multi-database discovery is enabled with --access-mode=unrestricted: tools can write to every "
            "authorized database. Prefer restricted mode and least-privilege PostgreSQL roles."
        )

    # Add the query tool with a description and annotations appropriate to the access mode
    if current_access_mode == AccessMode.UNRESTRICTED:
        mcp.add_tool(
            execute_sql,
            description="Execute any SQL query",
            annotations=ToolAnnotations(
                title="Execute SQL",
                destructiveHint=True,
            ),
        )
    else:
        mcp.add_tool(
            execute_sql,
            description="Execute a read-only SQL query",
            annotations=ToolAnnotations(
                title="Execute SQL (Read-Only)",
                readOnlyHint=True,
            ),
        )

    logger.info(f"Starting PostgreSQL MCP Server in {current_access_mode.upper()} mode")

    if database_config.auto_discover:
        registry = DatabaseRegistry(database_config, DatabaseCatalog(database_config))
        await registry.start()  # transient discovery outage starts degraded; config errors raise
    else:
        # Legacy: single pool, tolerant of an unavailable database
        try:
            await db_connection.pool_connect(database_config.bootstrap_uri)
            logger.info("Successfully connected to database and initialized connection pool")
        except Exception as e:
            log_public_error(logger, "startup_database_connection", e, level=logging.WARNING)
            logger.warning(
                "The MCP server will start but database operations will fail until a valid connection is established.",
            )

    # Set up proper shutdown handling
    try:
        loop = asyncio.get_running_loop()
        signals = (signal.SIGTERM, signal.SIGINT)
        for s in signals:
            loop.add_signal_handler(s, lambda s=s: asyncio.create_task(shutdown(s)))
    except NotImplementedError:
        # Windows doesn't support signals properly
        logger.warning("Signal handling not supported on Windows")
        pass

    # Run the server with the selected transport (always async)
    try:
        if args.transport == "stdio":
            await mcp.run_stdio_async()
        elif args.transport == "sse":
            mcp.settings.host = args.sse_host
            mcp.settings.port = args.sse_port
            if http_auth.token is not None:
                await run_authenticated_http(mcp, args.transport, http_auth)
            else:
                await mcp.run_sse_async()
        elif args.transport == "streamable-http":
            mcp.settings.host = args.streamable_http_host
            mcp.settings.port = args.streamable_http_port
            if http_auth.token is not None:
                await run_authenticated_http(mcp, args.transport, http_auth)
            else:
                await mcp.run_streamable_http_async()
    finally:
        if registry is not None:
            await registry.close_all()  # idempotent


async def shutdown(sig=None):
    """Clean shutdown of the server."""
    global shutdown_in_progress

    if shutdown_in_progress:
        logger.warning("Forcing immediate exit")
        # Use sys.exit instead of os._exit to allow for proper cleanup
        sys.exit(1)

    shutdown_in_progress = True
    cursor_store.invalidate_all()

    if sig:
        logger.info(f"Received exit signal {sig.name}")

    # Close database connections
    try:
        if registry is not None:
            await registry.close_all()
        await db_connection.close()
        logger.info("Closed database connections")
    except Exception as e:
        log_public_error(logger, "close_database_connections", e)

    # Exit with appropriate status code
    sys.exit(128 + sig if sig is not None else 0)
