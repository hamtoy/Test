"""Web API package for HTTP server."""

from src.web.api import app
from src.web.models import (
    EvalExternalRequest,
    EvalExternalResponse,
    EvalResult,
    GenerateQARequest,
    GenerateQAResponse,
    MultimodalResponse,
    QAPair,
    WorkspaceRequest,
    WorkspaceResponse,
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
    "GenerateQARequest",
    "GenerateQAResponse",
    "QAPair",
    "EvalExternalRequest",
    "EvalExternalResponse",
    "EvalResult",
    "WorkspaceRequest",
    "WorkspaceResponse",
    "MultimodalResponse",
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
