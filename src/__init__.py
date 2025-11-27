"""Main package initialization.

This module provides the public API for the shining-quasar package.
In v3.0, backward-compatibility shim files were removed. Code should import
from the appropriate subpackages directly.

Example:
    # Preferred imports (v3.0+)
    from src.core.models import EvaluationItem, WorkflowResult
    from src.config.settings import AppConfig
    from src.config.constants import PRICING_TIERS

    # Module-level aliases (still supported)
    from src import gemini_model_client
    from src import list_models
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__version__ = "3.0.0"

if TYPE_CHECKING:
    # Import types for type checking without circular dependencies
    from src.llm import gemini as gemini_model_client
    from src.llm import lcel_chain as lcel_optimized_chain
    from src.analysis import document_compare as compare_documents
    from src.analysis import cross_validation
    from src.analysis import semantic as semantic_analysis
    from src.infra import callbacks as custom_callback
    from src.infra import budget as budget_tracker
    from src.infra import health as health_check
    from src.features import autocomplete as smart_autocomplete
    from src.processing import example_selector as dynamic_example_selector
    from src.llm import list_models


def __getattr__(name: str) -> Any:
    """Lazy-load module shims to avoid circular imports.

    This provides backward compatibility for code that imports modules
    from src directly (e.g., `from src import gemini_model_client`).
    The actual modules have been reorganized into subpackages.
    """
    # LLM module shims
    if name == "gemini_model_client":
        from src.llm import gemini as gemini_model_client

        return gemini_model_client
    if name == "lcel_optimized_chain":
        from src.llm import lcel_chain as lcel_optimized_chain

        return lcel_optimized_chain
    if name == "list_models":
        from src.llm import list_models

        return list_models

    # Analysis module shims
    if name == "compare_documents":
        from src.analysis import document_compare as compare_documents

        return compare_documents
    if name == "cross_validation":
        from src.analysis import cross_validation

        return cross_validation
    if name == "semantic_analysis":
        from src.analysis import semantic as semantic_analysis

        return semantic_analysis

    # Infra module shims
    if name == "custom_callback":
        from src.infra import callbacks as custom_callback

        return custom_callback
    if name == "budget_tracker":
        from src.infra import budget as budget_tracker

        return budget_tracker
    if name == "health_check":
        from src.infra import health as health_check

        return health_check

    # Features module shims
    if name == "smart_autocomplete":
        from src.features import autocomplete as smart_autocomplete

        return smart_autocomplete

    # Processing module shims
    if name == "dynamic_example_selector":
        from src.processing import example_selector as dynamic_example_selector

        return dynamic_example_selector

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "__version__",
    # Module shims for backward compatibility
    "gemini_model_client",
    "lcel_optimized_chain",
    "list_models",
    "compare_documents",
    "cross_validation",
    "semantic_analysis",
    "custom_callback",
    "budget_tracker",
    "health_check",
    "smart_autocomplete",
    "dynamic_example_selector",
]
