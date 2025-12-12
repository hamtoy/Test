"""shining-quasar v3.0 - Pure Package Architecture.

This module provides the public API for shining-quasar v3.0.

Public API:
    - Agent: GeminiAgent
    - Config: AppConfig
    - Models: WorkflowResult, EvaluationResultSchema, QueryResult
    - Exceptions: BudgetExceededError, APIRateLimitError, ValidationFailedError

Legacy module shims are deprecated and will be removed in v4.0.

Example::

    # Preferred imports (v3.0+)
    from src.core.models import EvaluationItem, WorkflowResult
    from src.config.settings import AppConfig
    from src.config.constants import PRICING_TIERS

    # Module-level aliases (deprecated, will be removed in v4.0)
    from src import gemini_model_client
    from src import list_models
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
        "  pip install shining-quasar~=2.5.0",
    )

if TYPE_CHECKING:
    # Type-only imports for static analysis - no runtime cost
    from src.agent import GeminiAgent
    from src.analysis import cross_validation
    from src.analysis import document_compare as compare_documents
    from src.analysis import semantic as semantic_analysis
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
    from src.features import autocomplete as smart_autocomplete
    from src.infra import budget as budget_tracker
    from src.infra import callbacks as custom_callback
    from src.infra import health as health_check
    from src.llm import gemini as gemini_model_client
    from src.llm import lcel_chain as lcel_optimized_chain
    from src.llm import list_models
    from src.processing import example_selector as dynamic_example_selector


# Lazy loading mapping for public API
# Maps attribute name to (module_path, attribute_name, is_deprecated)
_EXC_MODULE = "src.config.exceptions"
_CORE_MODELS_MODULE = "src.core.models"
_LAZY_IMPORTS: dict[str, tuple[str, str | None, bool]] = {
    # Core public API (not deprecated)
    "GeminiAgent": ("src.agent", "GeminiAgent", False),
    "AppConfig": ("src.config", "AppConfig", False),
    "BudgetExceededError": (_EXC_MODULE, "BudgetExceededError", False),
    "APIRateLimitError": (_EXC_MODULE, "APIRateLimitError", False),
    "ValidationFailedError": (_EXC_MODULE, "ValidationFailedError", False),
    "WorkflowResult": (_CORE_MODELS_MODULE, "WorkflowResult", False),
    "EvaluationResultSchema": (_CORE_MODELS_MODULE, "EvaluationResultSchema", False),
    "QueryResult": (_CORE_MODELS_MODULE, "QueryResult", False),
    # Deprecated module shims (will be removed in v4.0)
    "gemini_model_client": ("src.llm.gemini", None, True),
    "lcel_optimized_chain": ("src.llm.lcel_chain", None, True),
    "list_models": ("src.llm.list_models", None, True),
    "compare_documents": ("src.analysis.document_compare", None, True),
    "cross_validation": ("src.analysis.cross_validation", None, True),
    "semantic_analysis": ("src.analysis.semantic", None, True),
    "custom_callback": ("src.infra.callbacks", None, True),
    "budget_tracker": ("src.infra.budget", None, True),
    "health_check": ("src.infra.health", None, True),
    "smart_autocomplete": ("src.features.autocomplete", None, True),
    "dynamic_example_selector": ("src.processing.example_selector", None, True),
}


def _emit_deprecation_warning(name: str, new_path: str) -> None:
    """Emit a deprecation warning for legacy module shims."""
    warnings.warn(
        f"Importing '{name}' from 'src' is deprecated and will be removed in v4.0. "
        f"Use 'from {new_path} import ...' instead.",
        DeprecationWarning,
        stacklevel=4,
    )


def __getattr__(name: str) -> Any:
    """Lazy-load public API and deprecated module shims.

    This uses lazy loading for all exports to:
    1. Reduce circular import risks by deferring imports
    2. Improve startup time by loading modules on-demand
    3. Maintain backward compatibility with deprecated imports

    DEPRECATED shims will be removed in v4.0.
    """
    if name in _LAZY_IMPORTS:
        module_path, attr_name, is_deprecated = _LAZY_IMPORTS[name]

        if is_deprecated:
            _emit_deprecation_warning(name, module_path)

        # Import the module
        import importlib

        module = importlib.import_module(module_path)

        # Return either a specific attribute or the whole module
        if attr_name is not None:
            return getattr(module, attr_name)
        return module

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
