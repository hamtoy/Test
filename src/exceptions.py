"""Backward compatibility - use src.config.exceptions instead."""
import warnings

from src.config.exceptions import (
    APIRateLimitError,
    BudgetExceededError,
    CacheCreationError,
    SafetyFilterError,
    ValidationFailedError,
)

warnings.warn(
    "Importing from 'src.exceptions' is deprecated. "
    "Use 'from src.config.exceptions import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "APIRateLimitError",
    "ValidationFailedError",
    "CacheCreationError",
    "SafetyFilterError",
    "BudgetExceededError",
]
