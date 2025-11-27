"""Enhanced deprecation warning system for v2.5.

This module provides an improved deprecation warning mechanism that ensures
warnings are always visible to users, regardless of Python's default warning filters.

Features:
- Always-visible warnings (bypasses Python's default 'once' filter)
- Environment variable control (DEPRECATION_LEVEL)
- Configurable verbosity levels (normal/strict/verbose)
- Caller information tracking

Environment Variables:
    DEPRECATION_LEVEL: Controls deprecation behavior
        - "normal" (default): Always show warnings
        - "strict": Raise ImportError for deprecated imports
        - "verbose": Include full stack trace in warnings
"""

from __future__ import annotations

import inspect
import os
import warnings

__all__ = ["EnhancedDeprecationWarning", "warn_deprecated"]


class EnhancedDeprecationWarning(DeprecationWarning):
    """Enhanced deprecation warning with improved visibility.

    This warning class is used for deprecated import paths and always
    displays to users, unlike the standard DeprecationWarning which is
    filtered by default in Python.
    """

    pass


# Ensure EnhancedDeprecationWarning is always shown
warnings.filterwarnings("always", category=EnhancedDeprecationWarning)


def _get_caller_info(stacklevel: int = 3) -> str:
    """Extract caller information from the call stack.

    Args:
        stacklevel: Number of stack frames to skip to find the caller.

    Returns:
        A formatted string with caller file, line, and function name.
    """
    frame = None
    try:
        frame = inspect.currentframe()
        if frame is None:
            return ""

        # Walk up the stack
        for _ in range(stacklevel):
            if frame.f_back is None:
                break
            frame = frame.f_back

        filename = frame.f_code.co_filename
        lineno = frame.f_lineno
        funcname = frame.f_code.co_name

        return f"  Called from: {filename}:{lineno} in {funcname}()"
    except (AttributeError, ValueError):
        return ""
    finally:
        if frame is not None:
            del frame


def _get_deprecation_level() -> str:
    """Get the deprecation level from environment variable.

    Returns:
        The deprecation level: 'normal', 'strict', or 'verbose'.
    """
    level = os.environ.get("DEPRECATION_LEVEL", "normal").lower()
    if level not in ("normal", "strict", "verbose"):
        level = "normal"
    return level


def warn_deprecated(
    old_path: str,
    new_path: str,
    removal_version: str = "v3.0",
    stacklevel: int = 2,
) -> None:
    """Emit an enhanced deprecation warning for deprecated import paths.

    This function provides visibility-enhanced deprecation warnings that are
    always displayed to users, with optional strict mode that raises errors.

    Args:
        old_path: The deprecated import path (e.g., "src.models").
        new_path: The recommended new import path (e.g., "src.core.models").
        removal_version: Version when the deprecated path will be removed.
        stacklevel: Number of stack levels to skip for warning location.

    Raises:
        ImportError: When DEPRECATION_LEVEL=strict, instead of just warning.

    Examples:
        >>> warn_deprecated("src.models", "src.core.models", "v3.0")
        # Emits: DeprecationWarning: 'src.models' is deprecated...

        >>> os.environ["DEPRECATION_LEVEL"] = "strict"
        >>> warn_deprecated("src.models", "src.core.models")
        # Raises: ImportError: Cannot import from deprecated path...
    """
    level = _get_deprecation_level()

    # Build the base message
    message = (
        f"⚠️ DEPRECATED: Importing from '{old_path}' is deprecated since v2.0. "
        f"Use '{new_path}' instead. Will be removed in {removal_version}."
    )

    # Handle strict mode - raise ImportError
    if level == "strict":
        error_msg = (
            f"Cannot import from deprecated path '{old_path}' "
            f"(DEPRECATION_LEVEL=strict). Use '{new_path}' instead."
        )
        raise ImportError(error_msg)

    # Handle verbose mode - add stack trace
    if level == "verbose":
        caller_info = _get_caller_info(stacklevel=stacklevel + 1)
        if caller_info:
            message = f"{message}\n{caller_info}"

    # Emit the warning (always visible due to filter configuration)
    warnings.warn(
        message,
        category=EnhancedDeprecationWarning,
        stacklevel=stacklevel + 1,  # +1 to account for this function
    )
