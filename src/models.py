"""
⚠️ DEPRECATED: This module is deprecated since v2.0.
Use 'src.core.models' instead. Will be removed in v3.0.
"""

from src._deprecation import warn_deprecated
from src.core.models import (
    CandidateID,
    EvaluationItem,
    EvaluationResultSchema,
    QueryResult,
    WorkflowResult,
)

warn_deprecated(
    old_path="src.models",
    new_path="src.core.models",
    removal_version="v3.0",
)

__all__ = [
    "CandidateID",
    "EvaluationItem",
    "EvaluationResultSchema",
    "QueryResult",
    "WorkflowResult",
]
