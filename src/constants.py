"""Backward compatibility - use src.config.constants instead."""
import warnings

warnings.warn(
    "Importing from 'src.constants' is deprecated. "
    "Use 'from src.config.constants import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from src.config.constants import *

__all__ = [
    "PRICING_TIERS",
    "GEMINI_API_KEY_LENGTH",
    "DEFAULT_RPM_LIMIT",
    "DEFAULT_RPM_WINDOW_SECONDS",
    "MIN_CACHE_TOKENS",
    "BUDGET_WARNING_THRESHOLDS",
    "PANEL_TITLE_QUERIES",
    "PANEL_TITLE_BUDGET",
    "PANEL_TITLE_COST",
    "PROMPT_EDIT_CANDIDATES",
    "COST_PANEL_TEMPLATE",
    "PROGRESS_WAITING_TEMPLATE",
    "PROGRESS_DONE_TEMPLATE",
    "PROGRESS_RESTORED_TEMPLATE",
    "PROGRESS_PROCESSING_TEMPLATE",
    "PROGRESS_FAILED_TEMPLATE",
    "PANEL_TURN_TITLE_TEMPLATE",
    "PANEL_TURN_BODY_TEMPLATE",
    "USER_INTERRUPT_MESSAGE",
    "LOG_MESSAGES",
    "ERROR_MESSAGES",
    "SENSITIVE_PATTERN",
]
