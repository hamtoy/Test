"""Compatibility wrapper for legacy `checks` imports.

The actual implementations live under `scripts.checks.*`.
"""

from scripts.checks.detect_forbidden_patterns import (
    find_formatting_violations,
    find_violations,
)
from scripts.checks.validate_session import validate_turns

__all__ = ["find_violations", "find_formatting_violations", "validate_turns"]
