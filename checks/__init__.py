"""Compatibility aliases for validation utilities."""

from scripts.validation.detect_forbidden_patterns import (
    find_formatting_violations,
    find_violations,
)

__all__ = [
    "find_formatting_violations",
    "find_violations",
]
