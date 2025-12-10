"""Compatibility shim for deprecation stats helpers."""

from scripts.analysis.deprecation_stats import (
    DEPRECATED_IMPORT_PATTERNS,
    UsageStats,
    analyze_file,
    analyze_usage,
    generate_report,
    generate_summary_text,
    get_trend_indicator,
    main,
    save_stats_json,
)

__all__ = [
    "DEPRECATED_IMPORT_PATTERNS",
    "UsageStats",
    "analyze_file",
    "analyze_usage",
    "generate_report",
    "generate_summary_text",
    "get_trend_indicator",
    "main",
    "save_stats_json",
]
