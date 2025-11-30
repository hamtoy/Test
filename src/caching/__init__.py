"""Caching package - cache management and analytics."""

from typing import Any

__all__ = [
    "CachingLayer",
    "analyze_cache_stats",
    "print_cache_report",
    "print_realtime_report",
    "RedisEvalCache",
    "CacheTTL",
    "CacheTTLPolicy",
    "calculate_ttl_by_token_count",
    "CacheAnalytics",
    "CacheMetrics",
    "RealTimeTracker",
    "MemoryMonitor",
]

_ANALYTICS_NAMES = frozenset((
    "analyze_cache_stats",
    "print_cache_report",
    "print_realtime_report",
    "CacheAnalytics",
    "CacheMetrics",
    "RealTimeTracker",
    "MemoryMonitor",
))

_TTL_NAMES = frozenset(("CacheTTL", "CacheTTLPolicy", "calculate_ttl_by_token_count"))


def __getattr__(name: str) -> Any:
    """Lazy import to avoid circular dependencies."""
    if name == "CachingLayer":
        from src.caching.layer import CachingLayer

        return CachingLayer
    if name in _ANALYTICS_NAMES:
        from src.caching.analytics import (
            CacheAnalytics,
            CacheMetrics,
            MemoryMonitor,
            RealTimeTracker,
            analyze_cache_stats,
            print_cache_report,
            print_realtime_report,
        )

        analytics_map = {
            "analyze_cache_stats": analyze_cache_stats,
            "print_cache_report": print_cache_report,
            "print_realtime_report": print_realtime_report,
            "CacheAnalytics": CacheAnalytics,
            "CacheMetrics": CacheMetrics,
            "RealTimeTracker": RealTimeTracker,
            "MemoryMonitor": MemoryMonitor,
        }
        return analytics_map[name]
    if name == "RedisEvalCache":
        from src.caching.redis_cache import RedisEvalCache

        return RedisEvalCache
    if name in _TTL_NAMES:
        from src.caching.ttl_policy import (
            CacheTTL,
            CacheTTLPolicy,
            calculate_ttl_by_token_count,
        )

        ttl_map = {
            "CacheTTL": CacheTTL,
            "CacheTTLPolicy": CacheTTLPolicy,
            "calculate_ttl_by_token_count": calculate_ttl_by_token_count,
        }
        return ttl_map[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
