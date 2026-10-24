import logging

import pytest
from psycopg import OperationalError

from postgres_mcp.security.errors import DatabaseNotAllowedError
from postgres_mcp.security.errors import PublicToolError
from postgres_mcp.security.errors import log_public_error
from postgres_mcp.security.errors import to_public_error
from postgres_mcp.sql.database_catalog import DiscoveryUnavailableError
from postgres_mcp.sql.database_registry import PoolCapacityError
from postgres_mcp.sql.safe_sql import SafeSqlDriver


def test_public_errors_hide_dsn_and_bind_params():
    secret = "postgresql://alice:secret@db.example/app"
    sql = "SELECT 'private literal'"
    try:
        try:
            raise RuntimeError(f"nested failure {secret}")
        except RuntimeError as nested:
            raise OperationalError(f"query {sql}; {secret}") from nested
    except OperationalError as exc:
        error = to_public_error(exc)

    assert error.code in {"INTERNAL_ERROR", "DATABASE_UNAVAILABLE"}
    assert secret not in str(error)
    assert "private literal" not in str(error)
    assert error.__cause__ is None


def test_expected_errors_preserve_safe_code():
    assert to_public_error(PoolCapacityError("secret db name")).code == "POOL_CAPACITY_EXCEEDED"
    assert to_public_error(DiscoveryUnavailableError("secret URI")).code == "DATABASE_UNAVAILABLE"
    assert to_public_error(DatabaseNotAllowedError("secret database")).code == "DATABASE_NOT_ALLOWED"
    with pytest.raises(ValueError) as exc:
        SafeSqlDriver(None).validate("SELECT pg_sleep('secret SQL')")
    error = to_public_error(exc.value)
    assert error.code == "SQL_VALIDATION_FAILED"
    assert "secret SQL" not in str(error)


def test_logger_uses_allowlisted_fields_only(caplog):
    exc = OperationalError("postgresql://alice:secret@db.example/app query SELECT 'private'")
    with caplog.at_level(logging.ERROR):
        log_public_error(logging.getLogger("security-test"), "execute_sql", exc, request_id="req-123")

    record = caplog.records[0]
    assert record.operation == "execute_sql"
    assert record.request_id == "req-123"
    assert record.error_class == "OperationalError"
    assert "secret" not in caplog.text
    assert "private" not in caplog.text
    assert not caplog.records[0].exc_info


def test_public_tool_error_has_stable_text_contract():
    error = PublicToolError("INTERNAL_ERROR", "The operation failed.")
    assert str(error) == "The operation failed."
    assert error.retryable is False
