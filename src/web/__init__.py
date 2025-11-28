"""Web module for the Gemini QA System."""

from .api import app
from .models import (
    EvalRequest,
    EvalResponse,
    EvalResult,
    ImageAnalysisResponse,
    ImageMetadata,
    OCRResponse,
    QABatchResponse,
    QAGenerateRequest,
    QAPair,
    QASingleResponse,
    WorkspaceRequest,
    WorkspaceResponse,
    WorkspaceResult,
)

__all__ = [
    "app",
    "EvalRequest",
    "EvalResponse",
    "EvalResult",
    "ImageAnalysisResponse",
    "ImageMetadata",
    "OCRResponse",
    "QABatchResponse",
    "QAGenerateRequest",
    "QAPair",
    "QASingleResponse",
    "WorkspaceRequest",
    "WorkspaceResponse",
    "WorkspaceResult",
]
