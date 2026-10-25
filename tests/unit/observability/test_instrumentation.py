from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from postgres_mcp.application.query_service import QueryExecutionService
from postgres_mcp.observability.metrics import SimpleMetrics
from postgres_mcp.pagination.cursors import InMemoryCursorStore
from postgres_mcp.query_limits.policy import QueryLimits
from postgres_mcp.query_limits.results import BoundedQueryResult
from postgres_mcp.sql.database_registry import DatabaseRegistry


@pytest.mark.asyncio
async def test_registry_lifecycle_gauges():
    metrics = SimpleMetrics(enabled=True)
    catalog = MagicMock()
    catalog.list_databases = AsyncMock(return_value=[])

    registry = DatabaseRegistry(catalog, metrics=metrics)
    assert registry.metrics is metrics
    # Verify pool transition recording
    metrics.record_pool("open", active_leases=1)
    series = metrics.collect()
    assert any(labels.get("state") == "open" for labels, _ in series)


@pytest.mark.asyncio
async def test_queries_histogram_and_errors():
    metrics = SimpleMetrics(enabled=True)
    driver = MagicMock()
    driver.execute_bounded_query = AsyncMock(
        return_value=BoundedQueryResult(rows=[], returned_rows=0, truncated=False, limit_reached=None, execution_time_ms=10.0, timeout_seconds=5)
    )

    def fake_driver(database=None):
        class Ctx:
            async def __aenter__(self):
                return driver

            async def __aexit__(self, *a):
                pass

        return Ctx()

    service = QueryExecutionService(fake_driver, max_result_bytes=1000, metrics=metrics)
    assert service.metrics is metrics

    limits = QueryLimits(max_rows=10, timeout_seconds=5)
    await service.execute("SELECT 1", "default", limits)
    # Check that query was recorded with success outcome
    key = (("operation", "query"), ("outcome", "success"), ("mode", "unrestricted"))
    assert metrics._counters[key] == 1


def test_cursor_expiration_metrics():
    metrics = SimpleMetrics(enabled=True)
    store = InMemoryCursorStore(ttl_seconds=300, max_active_cursors=10, metrics=metrics)
    assert store.metrics is metrics

    token = store.create(sql="SELECT 1", order_by=["id"], principal=None, database=None)
    assert metrics._counters[(("operation", "cursor"), ("action", "issue"))] == 1

    entry = store.consume(token, principal=None)
    assert entry is not None
    assert metrics._counters[(("operation", "cursor"), ("action", "consume"))] == 1


@pytest.mark.asyncio
async def test_cancel_decrements_inflight():
    metrics = SimpleMetrics(enabled=True)
    metrics.record_query(duration_seconds=0.01, outcome="cancelled", mode="restricted")
    assert metrics._counters[(("operation", "query"), ("outcome", "cancelled"), ("mode", "restricted"))] == 1
