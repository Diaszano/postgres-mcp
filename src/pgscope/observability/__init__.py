"""Observability package for PostgreSQL MCP."""

from .metrics import MetricsSink
from .metrics import NoopMetrics
from .metrics import SimpleMetrics
from .metrics import get_metrics_sink

__all__ = ["MetricsSink", "NoopMetrics", "SimpleMetrics", "get_metrics_sink"]
