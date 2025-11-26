# -*- coding: utf-8 -*-
"""Gemini Agent package.

Provides the main GeminiAgent class and re-exports common exceptions,
constants, and utility functions for backward compatibility.
"""

# Core agent class
from src.agent.core import GeminiAgent

# Exceptions (re-export for legacy imports)
from src.config.exceptions import (
    APIRateLimitError,
    BudgetExceededError,
    CacheCreationError,
    SafetyFilterError,
    ValidationFailedError,
)

# Constants
from src.config.constants import (
    DEFAULT_RPM_LIMIT,
    DEFAULT_RPM_WINDOW_SECONDS,
    PRICING_TIERS,
)

# Logging utility
from src.infra.logging import log_metrics

# Sub‑components
from .cache_manager import CacheManager
from .cost_tracker import CostTracker
from .rate_limiter import RateLimiter

# Public API
__all__ = [
    "GeminiAgent",
    "CacheManager",
    "CostTracker",
    "RateLimiter",
    # Exceptions
    "APIRateLimitError",
    "BudgetExceededError",
    "CacheCreationError",
    "SafetyFilterError",
    "ValidationFailedError",
    # Constants
    "DEFAULT_RPM_LIMIT",
    "DEFAULT_RPM_WINDOW_SECONDS",
    "PRICING_TIERS",
    # Logging
    "log_metrics",
]


def __getattr__(name: str):
    """Lazy import for optional caching module.

    Allows ``from src.agent import caching`` without importing the heavy
    ``google.generativeai.caching`` module unless actually used.
    """
    if name == "caching":
        import google.generativeai.caching as caching_mod

        globals()["caching"] = caching_mod
        return caching_mod
    raise AttributeError(name)
