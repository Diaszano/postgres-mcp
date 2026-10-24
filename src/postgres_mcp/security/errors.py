"""Stable, sanitized errors for application and MCP tool boundaries."""

import logging

from psycopg import OperationalError
from psycopg.errors import QueryCanceled


class PublicToolError(Exception):
    """An error whose message and code are safe to return to a tool caller."""

    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class SQLValidationError(ValueError):
    """A rejected restricted SQL statement."""


class DatabaseNotAllowedError(ValueError):
    """A database selection rejected by the configured access policy."""


def to_public_error(exc: BaseException) -> PublicToolError:
    """Map internal failures to a stable public code and fixed safe message."""
    if isinstance(exc, PublicToolError):
        return exc

    from postgres_mcp.sql.database_catalog import DatabaseConfigurationError
    from postgres_mcp.sql.database_catalog import DiscoveryUnavailableError
    from postgres_mcp.sql.database_registry import DatabaseUnavailableError
    from postgres_mcp.sql.database_registry import PoolCapacityError

    if isinstance(exc, PoolCapacityError):
        return PublicToolError("POOL_CAPACITY_EXCEEDED", "The database connection pool is at capacity.", retryable=True)
    if isinstance(exc, (DiscoveryUnavailableError, DatabaseUnavailableError)):
        return PublicToolError("DATABASE_UNAVAILABLE", "The database is temporarily unavailable.", retryable=True)
    if isinstance(exc, (DatabaseConfigurationError, DatabaseNotAllowedError)):
        return PublicToolError("DATABASE_NOT_ALLOWED", "The requested database is not available.")
    if isinstance(exc, SQLValidationError):
        return PublicToolError("SQL_VALIDATION_FAILED", "The SQL statement is not allowed.")
    if isinstance(exc, QueryCanceled):
        return PublicToolError("QUERY_TIMEOUT", "The query exceeded its time limit.", retryable=True)
    if isinstance(exc, OperationalError):
        return PublicToolError("DATABASE_UNAVAILABLE", "The database is temporarily unavailable.", retryable=True)
    return PublicToolError("INTERNAL_ERROR", "The operation failed.")


def log_public_error(
    logger: logging.Logger,
    operation: str,
    exc: BaseException,
    *,
    request_id: str | None = None,
    level: int = logging.ERROR,
) -> None:
    """Log only stable operation metadata and the exception class."""
    logger.log(
        level,
        "Application operation failed",
        extra={
            "operation": operation,
            "request_id": request_id or "-",
            "error_class": type(exc).__name__,
        },
    )
