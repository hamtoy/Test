"""
⚠️ DEPRECATED: This module is deprecated since v2.0.
Use 'src.config.exceptions' instead. Will be removed in v3.0.
"""

from src._deprecation import warn_deprecated
from src.config.exceptions import (
    APIRateLimitError,
    BudgetExceededError,
    CacheCreationError,
    SafetyFilterError,
    ValidationFailedError,
)

warn_deprecated(
    old_path="src.exceptions",
    new_path="src.config.exceptions",
    removal_version="v3.0",
)

__all__ = [
    "APIRateLimitError",
    "ValidationFailedError",
    "CacheCreationError",
    "SafetyFilterError",
    "BudgetExceededError",
]
