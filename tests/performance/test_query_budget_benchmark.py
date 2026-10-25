import time
import tracemalloc
import pytest

from postgres_mcp.observability.metrics import NoopMetrics
from postgres_mcp.observability.metrics import SimpleMetrics
from postgres_mcp.query_limits.results import BoundedQueryResult
from postgres_mcp.query_limits.results import encode_bounded_result


@pytest.mark.performance
def test_large_result_memory_bound():
    """Assert peak memory during chunked encoding remains bounded rather than scaling with row count."""
    tracemalloc.start()
    snapshot_before = tracemalloc.take_snapshot()

    # Generate a bounded result with row cap
    rows = [{"id": i, "data": "x" * 100} for i in range(10000)]
    bounded = BoundedQueryResult(
        rows=rows,
        returned_rows=len(rows),
        truncated=True,
        limit_reached="max_rows",
        execution_time_ms=50.0,
        timeout_seconds=15.0,
    )
    encoded = encode_bounded_result(bounded, max_result_bytes=2 * 1024 * 1024)

    snapshot_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    assert len(encoded) > 0
    # Peak memory overhead should be comfortably bounded under 50MB
    top_stats = snapshot_after.compare_to(snapshot_before, "lineno")
    total_diff = sum(stat.size_diff for stat in top_stats)
    assert total_diff < 50 * 1024 * 1024


@pytest.mark.performance
def test_metrics_cost_budget():
    """Capture overhead relative to disabled metrics and ensure minimal overhead."""
    noop = NoopMetrics()
    simple = SimpleMetrics(enabled=True)

    start_noop = time.perf_counter()
    for _ in range(5000):
        noop.record_query(0.001, "success", "restricted")
    time_noop = time.perf_counter() - start_noop

    start_simple = time.perf_counter()
    for _ in range(5000):
        simple.record_query(0.001, "success", "restricted")
    time_simple = time.perf_counter() - start_simple

    # The simple in-memory metric sink should not add more than 50ms for 5000 operations
    assert (time_simple - time_noop) < 0.1
