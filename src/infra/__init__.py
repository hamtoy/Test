"""Infrastructure package - utilities and system services."""

from typing import Any


def __getattr__(name: str) -> Any:
    """Lazy import of infrastructure module components.

    Args:
        name: The attribute name to retrieve.

    Returns:
        The requested infrastructure class or function.

    Raises:
        AttributeError: If name is not a valid module attribute.
    """
    # logging.py exports
    if name == "setup_logging":
        from src.infra.logging import setup_logging

        return setup_logging
    if name == "log_metrics":
        from src.infra.logging import log_metrics

        return log_metrics

    # health.py exports
    if name == "health_check":
        from src.infra.health import health_check

        return health_check

    # budget.py exports
    if name == "BudgetTracker":
        from src.infra.budget import BudgetTracker

        return BudgetTracker

    # neo4j.py exports
    if name == "SafeDriver":
        from src.infra.neo4j import SafeDriver

        return SafeDriver
    if name == "get_neo4j_driver_from_env":
        from src.infra.neo4j import get_neo4j_driver_from_env

        return get_neo4j_driver_from_env

    # utils.py exports
    if name == "write_cache_stats":
        from src.infra.utils import write_cache_stats

        return write_cache_stats
    if name == "run_async_safely":
        from src.infra.utils import run_async_safely

        return run_async_safely
    if name == "clean_markdown_code_block":
        from src.infra.utils import clean_markdown_code_block

        return clean_markdown_code_block
    if name == "safe_json_parse":
        from src.infra.utils import safe_json_parse

        return safe_json_parse

    # constraints.py exports
    if name == "RealTimeConstraintEnforcer":
        from src.infra.constraints import RealTimeConstraintEnforcer

        return RealTimeConstraintEnforcer

    # callbacks.py exports
    if name == "CustomCallback":
        from src.infra.callbacks import Neo4jLoggingCallback

        return Neo4jLoggingCallback
    if name == "Neo4jLoggingCallback":
        from src.infra.callbacks import Neo4jLoggingCallback

        return Neo4jLoggingCallback

    # adaptive_limiter.py exports
    if name == "AdaptiveRateLimiter":
        from src.infra.adaptive_limiter import AdaptiveRateLimiter

        return AdaptiveRateLimiter
    if name == "AdaptiveStats":
        from src.infra.adaptive_limiter import AdaptiveStats

        return AdaptiveStats

    # neo4j_optimizer.py exports
    if name == "TwoTierIndexManager":
        from src.infra.neo4j_optimizer import TwoTierIndexManager

        return TwoTierIndexManager
    if name == "OptimizedQueries":
        from src.infra.neo4j_optimizer import OptimizedQueries

        return OptimizedQueries

    # feature_flags.py exports
    if name == "FeatureFlags":
        from src.infra.feature_flags import FeatureFlags

        return FeatureFlags
    if name == "measure_latency":
        from src.infra.metrics import measure_latency

        return measure_latency
    if name == "measure_latency_async":
        from src.infra.metrics import measure_latency_async

        return measure_latency_async

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
