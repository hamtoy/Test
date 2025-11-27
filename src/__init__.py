"""
shining-quasar v3.0 - Pure Package Architecture

Public API:
- Agent: GeminiAgent
- Config: AppConfig
- Models: WorkflowResult, EvaluationResultSchema, QueryResult
- Exceptions: BudgetExceededError, APIRateLimitError, ValidationFailedError

This module provides the public API for shining-quasar v3.0.
Legacy module shims are deprecated and will be removed in v4.0.
"""

from __future__ import annotations

import sys
import warnings
from typing import TYPE_CHECKING, Any

__version__ = "3.0.0"

# Version guard - Python 3.10+ required for v3.0
if sys.version_info < (3, 10):
    raise RuntimeError(
        "shining-quasar v3.0+ requires Python 3.10 or higher.\n"
        "For Python 3.9 support, use v2.5.x:\n"
        "  pip install shining-quasar~=2.5.0"
    )

# Public API Exports (explicit)
from src.agent import GeminiAgent
from src.config import AppConfig
from src.config.exceptions import (
    APIRateLimitError,
    BudgetExceededError,
    ValidationFailedError,
)
from src.core.models import (
    EvaluationResultSchema,
    QueryResult,
    WorkflowResult,
)

if TYPE_CHECKING:
    # Import types for type checking without circular dependencies
    from src.analysis import cross_validation
    from src.analysis import document_compare as compare_documents
    from src.analysis import semantic as semantic_analysis
    from src.features import autocomplete as smart_autocomplete
    from src.infra import budget as budget_tracker
    from src.infra import callbacks as custom_callback
    from src.infra import health as health_check
    from src.llm import gemini as gemini_model_client
    from src.llm import lcel_chain as lcel_optimized_chain
    from src.llm import list_models
    from src.processing import example_selector as dynamic_example_selector


def _emit_deprecation_warning(name: str, new_path: str) -> None:
    """Emit a deprecation warning for legacy module shims."""
    warnings.warn(
        f"Importing '{name}' from 'src' is deprecated and will be removed in v4.0. "
        f"Use 'from {new_path} import ...' instead.",
        DeprecationWarning,
        stacklevel=3,
    )


def __getattr__(name: str) -> Any:
    """Lazy-load module shims to avoid circular imports.

    This provides backward compatibility for code that imports modules
    from src directly (e.g., `from src import gemini_model_client`).
    The actual modules have been reorganized into subpackages.

    DEPRECATED: These shims are deprecated and will be removed in v4.0.
    """
    # LLM module shims
    if name == "gemini_model_client":
        from src.llm import gemini as gemini_model_client

        _emit_deprecation_warning("gemini_model_client", "src.llm.gemini")
        return gemini_model_client
    if name == "lcel_optimized_chain":
        from src.llm import lcel_chain as lcel_optimized_chain

        _emit_deprecation_warning("lcel_optimized_chain", "src.llm.lcel_chain")
        return lcel_optimized_chain
    if name == "list_models":
        from src.llm import list_models

        _emit_deprecation_warning("list_models", "src.llm.list_models")
        return list_models

    # Analysis module shims
    if name == "compare_documents":
        from src.analysis import document_compare as compare_documents

        _emit_deprecation_warning("compare_documents", "src.analysis.document_compare")
        return compare_documents
    if name == "cross_validation":
        from src.analysis import cross_validation

        _emit_deprecation_warning("cross_validation", "src.analysis.cross_validation")
        return cross_validation
    if name == "semantic_analysis":
        from src.analysis import semantic as semantic_analysis

        _emit_deprecation_warning("semantic_analysis", "src.analysis.semantic")
        return semantic_analysis

    # Infra module shims
    if name == "custom_callback":
        from src.infra import callbacks as custom_callback

        _emit_deprecation_warning("custom_callback", "src.infra.callbacks")
        return custom_callback
    if name == "budget_tracker":
        from src.infra import budget as budget_tracker

        _emit_deprecation_warning("budget_tracker", "src.infra.budget")
        return budget_tracker
    if name == "health_check":
        from src.infra import health as health_check

        _emit_deprecation_warning("health_check", "src.infra.health")
        return health_check

    # Features module shims
    if name == "smart_autocomplete":
        from src.features import autocomplete as smart_autocomplete

        _emit_deprecation_warning("smart_autocomplete", "src.features.autocomplete")
        return smart_autocomplete

    # Processing module shims
    if name == "dynamic_example_selector":
        from src.processing import example_selector as dynamic_example_selector

        _emit_deprecation_warning(
            "dynamic_example_selector", "src.processing.example_selector"
        )
        return dynamic_example_selector

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Version
    "__version__",
    # Core
    "GeminiAgent",
    "AppConfig",
    # Models
    "WorkflowResult",
    "EvaluationResultSchema",
    "QueryResult",
    # Exceptions
    "BudgetExceededError",
    "APIRateLimitError",
    "ValidationFailedError",
    # Deprecated module shims (for backward compatibility)
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
