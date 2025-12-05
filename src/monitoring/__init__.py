"""Monitoring package for metrics and observability."""

from src.monitoring.metrics import (
    get_metrics,
    record_api_call,
    record_api_error,
    record_cache_access,
    record_token_usage,
    record_workflow_completion,
    PROMETHEUS_AVAILABLE,
)

# New PROMPT-005 exports
from src.monitoring.metrics_exporter import MetricsExporter, get_exporter

__all__ = [
    "get_metrics",
    "record_api_call",
    "record_api_error",
    "record_cache_access",
    "record_token_usage",
    "record_workflow_completion",
    "PROMETHEUS_AVAILABLE",
    # PROMPT-005 additions
    "MetricsExporter",
    "get_exporter",
]
