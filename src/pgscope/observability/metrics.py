"""Low-cardinality operational metrics sink and adapters."""

import os
from collections import defaultdict
from typing import Protocol


class MetricsSink(Protocol):
    """Protocol for capturing operational metrics without leaking sensitive data."""

    def record_query(self, duration_seconds: float, outcome: str = "success", mode: str = "unrestricted") -> None:
        """Record query duration and outcome."""
        ...

    def record_pool(self, state: str, active_leases: int = 0) -> None:
        """Record connection pool state transitions and active leases."""
        ...

    def record_cursor(self, action: str) -> None:
        """Record cursor lifecycle events (issue, consume, expire, evict)."""
        ...


class NoopMetrics:
    """Default no-overhead metrics sink with no side effects."""

    def record_query(self, duration_seconds: float, outcome: str = "success", mode: str = "unrestricted") -> None:
        pass

    def record_pool(self, state: str, active_leases: int = 0) -> None:
        pass

    def record_cursor(self, action: str) -> None:
        pass


class SimpleMetrics:
    """In-memory metrics collector with strictly allowlisted low-cardinality labels."""

    ALLOWED_LABELS = frozenset({"operation", "outcome", "mode", "state", "action"})

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._counters: dict[tuple[tuple[str, str], ...], int] = defaultdict(int)
        self._gauges: dict[tuple[tuple[str, str], ...], float] = {}

    def record_query(self, duration_seconds: float, outcome: str = "success", mode: str = "unrestricted") -> None:
        if not self.enabled:
            return
        key = (("operation", "query"), ("outcome", outcome), ("mode", mode))
        self._counters[key] += 1
        self._gauges[key] = duration_seconds

    def record_pool(self, state: str, active_leases: int = 0) -> None:
        if not self.enabled:
            return
        key = (("operation", "pool"), ("state", state))
        self._counters[key] += 1
        self._gauges[(("operation", "pool_leases"),)] = float(active_leases)

    def record_cursor(self, action: str) -> None:
        if not self.enabled:
            return
        key = (("operation", "cursor"), ("action", action))
        self._counters[key] += 1

    def collect(self) -> list[tuple[dict[str, str], float]]:
        """Return snapshot of collected time series as (labels_dict, value)."""
        result = []
        for k, v in self._counters.items():
            result.append((dict(k), float(v)))
        return result


def get_metrics_sink() -> MetricsSink:
    """Return the configured metrics sink according to environment configuration."""
    if os.environ.get("DATABASE_METRICS_ENABLED", "").lower() in ("true", "1", "yes"):
        return SimpleMetrics(enabled=True)
    return NoopMetrics()
