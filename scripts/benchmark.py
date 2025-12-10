"""Compatibility shim for benchmark utilities."""

from scripts.dev.benchmark import (
    BenchmarkRunner,
    calculate_percentile,
    main,
    sample_async_workload,
    sample_sync_workload,
)

__all__ = [
    "BenchmarkRunner",
    "calculate_percentile",
    "main",
    "sample_async_workload",
    "sample_sync_workload",
]
