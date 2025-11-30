"""Web API request/response models with validation.

All string fields have explicit length limits to prevent
memory exhaustion attacks and ensure API stability.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# Constants for validation limits
MAX_QUERY_LENGTH = 10000
MAX_ANSWER_LENGTH = 50000
MAX_OCR_TEXT_LENGTH = 100000
MAX_EDIT_REQUEST_LENGTH = 5000
MAX_COMMENT_LENGTH = 2000
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10MB


class GenerateQARequest(BaseModel):
    """Request model for QA generation endpoint."""

    mode: Literal["batch", "single"] = Field(
        default="batch",
        description="Generation mode: 'batch' for all 4 types, 'single' for one type",
    )
    qtype: Optional[
        Literal["global_explanation", "reasoning", "target_short", "target_long"]
    ] = Field(
        default=None,
        max_length=50,
        description="Question type for single mode",
    )


class QAPair(BaseModel):
    """QA 쌍"""

    type: str
    query: str
    answer: str


class GenerateQAResponse(BaseModel):
    """QA 생성 응답"""

    mode: Literal["batch", "single"]
    pairs: Optional[List[QAPair]] = None  # batch
    pair: Optional[QAPair] = None  # single


class EvalExternalRequest(BaseModel):
    """Request model for external answer evaluation."""

    query: str = Field(
        ...,
        max_length=MAX_QUERY_LENGTH,
        description="The question to evaluate answers for",
    )
    answers: List[str] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="List of 3 candidate answers",
    )


class EvalResult(BaseModel):
    """평가 결과"""

    answer_id: str
    score: int
    feedback: str


class EvalExternalResponse(BaseModel):
    """외부 답변 평가 응답"""

    results: List[EvalResult]
    best: str


class WorkspaceRequest(BaseModel):
    """Request model for workspace operations (inspect/edit)."""

    mode: Literal["inspect", "edit"] = Field(
        default="inspect",
        description="Operation mode",
    )
    query: Optional[str] = Field(
        default="",
        max_length=MAX_QUERY_LENGTH,
        description="Associated query (optional)",
    )
    answer: str = Field(
        ...,
        max_length=MAX_ANSWER_LENGTH,
        description="Answer content to process",
    )
    edit_request: Optional[str] = Field(
        default="",
        max_length=MAX_EDIT_REQUEST_LENGTH,
        description="Edit instructions for 'edit' mode",
    )
    inspector_comment: Optional[str] = Field(
        default="",
        max_length=MAX_COMMENT_LENGTH,
        description="Inspector's comment for logging",
    )


class WorkspaceResponse(BaseModel):
    """워크스페이스 응답"""

    mode: Literal["inspect", "edit"]
    result: Dict[str, Any]


class MultimodalResponse(BaseModel):
    """이미지 분석 응답"""

    filename: str
    metadata: Dict[str, Any]


class HealthResponse(BaseModel):
    """Response model for health check endpoints."""

    status: Literal["healthy", "degraded", "unhealthy"]
    services: Dict[str, bool] = Field(default_factory=dict)
    version: Optional[str] = None


__all__ = [
    "GenerateQARequest",
    "EvalExternalRequest",
    "WorkspaceRequest",
    "HealthResponse",
    "MAX_QUERY_LENGTH",
    "MAX_ANSWER_LENGTH",
    "MAX_OCR_TEXT_LENGTH",
    "MAX_EDIT_REQUEST_LENGTH",
    "MAX_COMMENT_LENGTH",
    "MAX_UPLOAD_SIZE_BYTES",
]

