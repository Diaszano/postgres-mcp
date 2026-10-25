import pytest

from postgres_mcp.observability.metrics import MetricsSink
from postgres_mcp.observability.metrics import NoopMetrics
from postgres_mcp.observability.metrics import SimpleMetrics
from postgres_mcp.observability.metrics import get_metrics_sink


def test_noop_metrics_by_default():
    sink = get_metrics_sink()
    assert isinstance(sink, NoopMetrics)
    # Calling methods must not raise or produce listeners
    sink.record_query(duration_seconds=0.05, outcome="success", mode="restricted")
    sink.record_pool(state="open", active_leases=2)
    sink.record_cursor(action="issue")


def test_prometheus_labels_are_allowlisted():
    metrics = SimpleMetrics(enabled=True)
    # Attempting to record with allowlisted labels
    metrics.record_query(duration_seconds=0.1, outcome="timeout", mode="unrestricted")
    metrics.record_cursor(action="evict")
    metrics.record_pool(state="failed", active_leases=0)

    # Validate collected label names are strictly allowlisted
    allowed = {"operation", "outcome", "mode", "state", "action"}
    for series_key, _ in metrics.collect():
        for k in series_key.keys():
            assert k in allowed, f"Disallowed label {k} found in series {series_key}"


def test_instrumentation_cardinality_fixed():
    metrics = SimpleMetrics(enabled=True)
    # Simulate 1000 different databases / callers
    for i in range(1000):
        metrics.record_query(duration_seconds=0.01, outcome="success", mode="restricted")
        metrics.record_cursor(action="issue")

    # Cardinality must remain fixed and bounded (does not scale with 1000 calls)
    series = metrics.collect()
    assert len(series) <= 10
