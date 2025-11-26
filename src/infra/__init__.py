"""Infrastructure package - utilities and system services."""

from typing import Any


def __getattr__(name: str) -> Any:
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

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "setup_logging",
    "log_metrics",
    "health_check",
    "BudgetTracker",
    "SafeDriver",
    "get_neo4j_driver_from_env",
    "write_cache_stats",
    "clean_markdown_code_block",
    "safe_json_parse",
    "RealTimeConstraintEnforcer",
    "CustomCallback",
    "Neo4jLoggingCallback",
]
