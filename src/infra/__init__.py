"""Infrastructure package - utilities and system services."""

from __future__ import annotations

import importlib
from typing import Any

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "setup_logging": ("src.infra.logging", "setup_logging"),
    "log_metrics": ("src.infra.logging", "log_metrics"),
    "health_check": ("src.infra.health", "health_check"),
    "BudgetTracker": ("src.infra.budget", "BudgetTracker"),
    "SafeDriver": ("src.infra.neo4j", "SafeDriver"),
    "get_neo4j_driver_from_env": ("src.infra.neo4j", "get_neo4j_driver_from_env"),
    "write_cache_stats": ("src.infra.utils", "write_cache_stats"),
    "run_async_safely": ("src.infra.utils", "run_async_safely"),
    "clean_markdown_code_block": ("src.infra.utils", "clean_markdown_code_block"),
    "safe_json_parse": ("src.infra.utils", "safe_json_parse"),
    "RealTimeConstraintEnforcer": (
        "src.infra.constraints",
        "RealTimeConstraintEnforcer",
    ),
    "CustomCallback": ("src.infra.callbacks", "Neo4jLoggingCallback"),
    "Neo4jLoggingCallback": ("src.infra.callbacks", "Neo4jLoggingCallback"),
    "AdaptiveRateLimiter": ("src.infra.adaptive_limiter", "AdaptiveRateLimiter"),
    "AdaptiveStats": ("src.infra.adaptive_limiter", "AdaptiveStats"),
    "TwoTierIndexManager": ("src.infra.neo4j_optimizer", "TwoTierIndexManager"),
    "OptimizedQueries": ("src.infra.neo4j_optimizer", "OptimizedQueries"),
    "FeatureFlags": ("src.infra.feature_flags", "FeatureFlags"),
    "measure_latency": ("src.infra.metrics", "measure_latency"),
    "measure_latency_async": ("src.infra.metrics", "measure_latency_async"),
}


def __getattr__(name: str) -> Any:
    """Lazy import of infrastructure module components."""
    try:
        module_name, attr_name = _LAZY_IMPORTS[name]
    except KeyError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}",
        ) from exc

    module = importlib.import_module(module_name)
    return getattr(module, attr_name)


__all__ = [
    "AdaptiveRateLimiter",
    "AdaptiveStats",
    "BudgetTracker",
    "CustomCallback",
    "FeatureFlags",
    "Neo4jLoggingCallback",
    "OptimizedQueries",
    "RealTimeConstraintEnforcer",
    "SafeDriver",
    "TwoTierIndexManager",
    "clean_markdown_code_block",
    "get_neo4j_driver_from_env",
    "health_check",
    "log_metrics",
    "measure_latency",
    "measure_latency_async",
    "run_async_safely",
    "safe_json_parse",
    "setup_logging",
    "write_cache_stats",
]
