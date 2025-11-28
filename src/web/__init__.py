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
]
