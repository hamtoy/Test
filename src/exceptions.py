"""Backward compatibility - use src.config.exceptions instead."""
import warnings

warnings.warn(
    "Importing from 'src.exceptions' is deprecated. "
    "Use 'from src.config.exceptions import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from src.config.exceptions import *

__all__ = [
    "APIRateLimitError",
    "ValidationFailedError",
    "CacheCreationError",
    "SafetyFilterError",
    "BudgetExceededError",
]
