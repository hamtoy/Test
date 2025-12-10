"""Expose forbidden-pattern helpers under the checks namespace."""

from scripts.validation.detect_forbidden_patterns import (
    find_formatting_violations,
    find_violations,
)

__all__ = ["find_violations", "find_formatting_violations"]
