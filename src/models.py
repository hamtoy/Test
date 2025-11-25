"""Backward compatibility - use src.core.models instead."""

import warnings

from src.core.models import (
    CandidateID,
    EvaluationItem,
    EvaluationResultSchema,
    QueryResult,
    WorkflowResult,
)

warnings.warn(
    "Importing from 'src.models' is deprecated. "
    "Use 'from src.core.models import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "CandidateID",
    "EvaluationItem",
    "EvaluationResultSchema",
    "QueryResult",
    "WorkflowResult",
]
