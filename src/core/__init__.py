"""Core package - fundamental data models and interfaces."""

from src.core.models import (
    CandidateID,
    EvaluationItem,
    EvaluationResultSchema,
    QueryResult,
    WorkflowResult,
)

__all__ = [
    "CandidateID",
    "EvaluationItem",
    "EvaluationResultSchema",
    "QueryResult",
    "WorkflowResult",
]
