import asyncio
import logging
import pytest

from postgres_mcp.observability.logging import get_operation_id
from postgres_mcp.observability.logging import operation_context
from postgres_mcp.observability.status import RuntimeStatus


@pytest.mark.asyncio
async def test_request_id_per_tool_operation():
    assert get_operation_id() is None

    async def task_a():
        with operation_context("req-AAA"):
            await asyncio.sleep(0.01)
            return get_operation_id()

    async def task_b():
        with operation_context("req-BBB"):
            await asyncio.sleep(0.01)
            return get_operation_id()

    res_a, res_b = await asyncio.gather(task_a(), task_b())
    assert res_a == "req-AAA"
    assert res_b == "req-BBB"
    assert get_operation_id() is None


def test_readiness_not_equal_database_health():
    status = RuntimeStatus(server_ready=True, catalog_degraded=True)
    assert status.is_ready is True
    assert status.is_healthy is False
    data = status.to_dict()
    assert data["status"] == "degraded"
    assert data["ready"] is True
    assert data["database_health"] == "degraded"


def test_sanitized_failure_logging(caplog):
    from postgres_mcp.security.errors import PublicToolError
    from postgres_mcp.security.errors import log_public_error

    logger = logging.getLogger("test_logger")
    caplog.set_level(logging.ERROR)

    err = PublicToolError("DATABASE_UNAVAILABLE", "Connection refused to secret_db")
    with operation_context("req-999"):
        log_public_error(logger, "test_operation", err, request_id=get_operation_id())

    assert len(caplog.records) == 1
    rec = caplog.records[0]
    assert rec.operation == "test_operation"
    assert rec.request_id == "req-999"
    assert rec.error_class == "PublicToolError"
    # Ensure sensitive payload isn't in record attributes
    assert "secret_db" not in str(rec.__dict__.get("extra", {}))
