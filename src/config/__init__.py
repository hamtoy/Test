"""Configuration package - centralized settings management."""

from functools import lru_cache

from src.config.constants import (
    BUDGET_WARNING_THRESHOLDS,
    COST_PANEL_TEMPLATE,
    DEFAULT_RPM_LIMIT,
    DEFAULT_RPM_WINDOW_SECONDS,
    ERROR_MESSAGES,
    GEMINI_API_KEY_LENGTH,
    LOG_MESSAGES,
    MIN_CACHE_TOKENS,
    PANEL_TITLE_BUDGET,
    PANEL_TITLE_COST,
    PANEL_TITLE_QUERIES,
    PANEL_TURN_BODY_TEMPLATE,
    PANEL_TURN_TITLE_TEMPLATE,
    PRICING_TIERS,
    PROGRESS_DONE_TEMPLATE,
    PROGRESS_FAILED_TEMPLATE,
    PROGRESS_PROCESSING_TEMPLATE,
    PROGRESS_RESTORED_TEMPLATE,
    PROGRESS_WAITING_TEMPLATE,
    PROMPT_EDIT_CANDIDATES,
    SENSITIVE_PATTERN,
    USER_INTERRUPT_MESSAGE,
    CacheConfig,
)
from src.config.database import DatabaseSettingsMixin
from src.config.exceptions import (
    APICallError,
    APIRateLimitError,
    BudgetExceededError,
    CacheCreationError,
    SafetyFilterError,
    ValidationFailedError,
)
from src.config.features import FeatureSettingsMixin
from src.config.llm import LLMSettingsMixin
from src.config.settings import AppConfig
from src.config.utils import require_env
from src.config.web import WebSettingsMixin


@lru_cache(maxsize=1)
def get_settings() -> AppConfig:
    """Return a cached singleton instance of AppConfig.

    This function ensures that environment variable parsing and .env file
    loading happens only once per application lifecycle, improving startup
    performance and reducing redundant I/O operations.

    Returns:
        AppConfig: The cached application configuration instance.
    """
    return AppConfig()


__all__ = [
    "BUDGET_WARNING_THRESHOLDS",
    "COST_PANEL_TEMPLATE",
    "DEFAULT_RPM_LIMIT",
    "DEFAULT_RPM_WINDOW_SECONDS",
    "ERROR_MESSAGES",
    "GEMINI_API_KEY_LENGTH",
    "LOG_MESSAGES",
    "MIN_CACHE_TOKENS",
    "PANEL_TITLE_BUDGET",
    "PANEL_TITLE_COST",
    "PANEL_TITLE_QUERIES",
    "PANEL_TURN_BODY_TEMPLATE",
    "PANEL_TURN_TITLE_TEMPLATE",
    "PRICING_TIERS",
    "PROGRESS_DONE_TEMPLATE",
    "PROGRESS_FAILED_TEMPLATE",
    "PROGRESS_PROCESSING_TEMPLATE",
    "PROGRESS_RESTORED_TEMPLATE",
    "PROGRESS_WAITING_TEMPLATE",
    "PROMPT_EDIT_CANDIDATES",
    "SENSITIVE_PATTERN",
    "USER_INTERRUPT_MESSAGE",
    "APICallError",
    "APIRateLimitError",
    "AppConfig",
    "BudgetExceededError",
    "CacheConfig",
    "CacheCreationError",
    "DatabaseSettingsMixin",
    "FeatureSettingsMixin",
    "LLMSettingsMixin",
    "SafetyFilterError",
    "ValidationFailedError",
    "WebSettingsMixin",
    "get_settings",
    "require_env",
]
