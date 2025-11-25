"""Gemini Agent 패키지.

기존 import 경로 유지를 위한 re-export:
    from src.agent import GeminiAgent  # ✅ 기존 방식 그대로 사용 가능

하위 모듈 직접 접근:
    from src.agent.core import GeminiAgent
    from src.agent.cost_tracker import CostTracker
    from src.agent.rate_limiter import RateLimiter
    from src.agent.cache_manager import CacheManager
"""

from src.constants import (
    DEFAULT_RPM_LIMIT,
    DEFAULT_RPM_WINDOW_SECONDS,
    PRICING_TIERS,
)
from src.exceptions import (
    APIRateLimitError,
    BudgetExceededError,
    CacheCreationError,
    SafetyFilterError,
    ValidationFailedError,
)
from src.logging_setup import log_metrics

from .cache_manager import CacheManager
from .core import GeminiAgent
from .cost_tracker import CostTracker
from .rate_limiter import RateLimiter

__all__ = [
    "GeminiAgent",
    "CostTracker",
    "RateLimiter",
    "CacheManager",
    # Backward compatibility re-exports
    "APIRateLimitError",
    "BudgetExceededError",
    "CacheCreationError",
    "SafetyFilterError",
    "ValidationFailedError",
    "DEFAULT_RPM_LIMIT",
    "DEFAULT_RPM_WINDOW_SECONDS",
    "PRICING_TIERS",
    "log_metrics",
]


def __getattr__(name: str):
    """Late import hook for caching module."""
    if name == "caching":
        import google.generativeai.caching as caching_mod

        globals()["caching"] = caching_mod
        return caching_mod
    raise AttributeError(name)
