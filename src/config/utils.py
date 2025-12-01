"""Configuration utility functions.

This module provides common utility functions for configuration management.
"""

from __future__ import annotations

import os

__all__ = ["require_env"]


def require_env(var: str) -> str:
    """Get a required environment variable.

    Args:
        var: The name of the environment variable.

    Returns:
        The value of the environment variable.

    Raises:
        EnvironmentError: If the environment variable is not set.
    """
    val = os.getenv(var)
    if not val:
        raise EnvironmentError(f"환경 변수 {var}가 설정되지 않았습니다 (.env 확인).")
    return val
