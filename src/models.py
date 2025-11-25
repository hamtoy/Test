"""Backward compatibility - use src.core.models instead."""
import warnings

warnings.warn(
    "Importing from 'src.models' is deprecated. "
    "Use 'from src.core.models import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from src.core.models import *

__all__ = [
    "CandidateID",
    "EvaluationItem",
    "EvaluationResultSchema",
    "QueryResult",
    "WorkflowResult",
]
