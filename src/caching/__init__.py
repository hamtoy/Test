"""Caching package - cache management and analytics."""

__all__ = [
    "CachingLayer",
    "analyze_cache_stats",
    "print_cache_report",
    "RedisEvalCache",
]


def __getattr__(name: str) -> object:
    """Lazy import to avoid circular dependencies."""
    if name == "CachingLayer":
        from src.caching.layer import CachingLayer

        return CachingLayer
    elif name == "analyze_cache_stats":
        from src.caching.analytics import analyze_cache_stats

        return analyze_cache_stats
    elif name == "print_cache_report":
        from src.caching.analytics import print_cache_report

        return print_cache_report
    elif name == "RedisEvalCache":
        from src.caching.redis_cache import RedisEvalCache

        return RedisEvalCache
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
