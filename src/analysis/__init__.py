"""Analysis package - semantic analysis and document comparison."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.analysis.semantic import SemanticAnalyzer
    from src.analysis.cross_validation import CrossValidator
    from src.analysis.document_compare import DocumentComparer


def __getattr__(name: str) -> Any:
    """Lazy-load modules to avoid circular imports."""
    if name == "SemanticAnalyzer":
        from src.analysis.semantic import SemanticAnalyzer
        return SemanticAnalyzer
    if name == "CrossValidator":
        from src.analysis.cross_validation import CrossValidator
        return CrossValidator
    if name == "DocumentComparer":
        from src.analysis.document_compare import DocumentComparer
        return DocumentComparer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "SemanticAnalyzer",
    "CrossValidator",
    "DocumentComparer",
]
