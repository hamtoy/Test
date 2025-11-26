"""Analysis package - semantic analysis and document comparison."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def __getattr__(name: str) -> Any:
    """Lazy-load modules to avoid circular imports."""
    if name == "CrossValidationSystem":
        from src.analysis.cross_validation import CrossValidationSystem

        return CrossValidationSystem
    # semantic.py and document_compare.py contain utility functions, not classes
    # They can be imported directly from their modules
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CrossValidationSystem",
]
