"""Compatibility shim for latency baseline utilities."""

from scripts.dev.latency_baseline import (
    LATENCY_PATTERN,
    extract_latencies,
    main,
    percentile,
    print_table,
    summarise,
)

__all__ = [
    "LATENCY_PATTERN",
    "extract_latencies",
    "main",
    "percentile",
    "print_table",
    "summarise",
]
