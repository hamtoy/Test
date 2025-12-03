"""Web API request/response models with validation.

All string fields have explicit length limits to prevent
memory exhaustion attacks and ensure API stability.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# Constants for validation limits
MAX_QUERY_LENGTH = 10000
MAX_ANSWER_LENGTH = 50000
MAX_OCR_TEXT_LENGTH = 100000
MAX_EDIT_REQUEST_LENGTH = 5000
MAX_COMMENT_LENGTH = 2000
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MAX_TYPE_LENGTH = 100
MAX_FEEDBACK_LENGTH = 5000
MAX_PROMPT_LENGTH = 50000


class GenerateQARequest(BaseModel):
    """Request model for QA generation endpoint."""

    mode: Literal["batch", "single"] = Field(
        default="batch",
        description="Generation mode: 'batch' for all 4 types, 'single' for one type",
    )
    ocr_text: Optional[str] = Field(
        default=None,
        max_length=MAX_OCR_TEXT_LENGTH,
        description="Optional OCR text override; if absent, server loads from file",
    )
    qtype: Optional[
        Literal["global_explanation", "reasoning", "target_short", "target_long"]
    ] = Field(
        default=None,
        description="Question type for single mode",
    )


class QAPair(BaseModel):
    """QA pair model for generated question-answer pairs."""

    type: str = Field(..., max_length=MAX_TYPE_LENGTH)
    query: str = Field(..., max_length=MAX_QUERY_LENGTH)
    answer: str = Field(..., max_length=MAX_ANSWER_LENGTH)


class GenerateQAResponse(BaseModel):
    """QA generation response model."""

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

    @field_validator("answers")
    @classmethod
    def validate_answer_lengths(cls, v: List[str]) -> List[str]:
        """Validate each answer in the list does not exceed max length."""
        for i, answer in enumerate(v):
            if len(answer) > MAX_ANSWER_LENGTH:
                raise ValueError(
                    f"Answer {i + 1} exceeds maximum length of {MAX_ANSWER_LENGTH}"
                )
        return v


class EvalResult(BaseModel):
    """Evaluation result model."""

    answer_id: str = Field(..., max_length=10)
    score: int
    feedback: str = Field(..., max_length=MAX_FEEDBACK_LENGTH)


class EvalExternalResponse(BaseModel):
    """External answer evaluation response model."""

    results: List[EvalResult]
    best: str = Field(..., max_length=10)


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
    """Workspace operation response model."""

    mode: Literal["inspect", "edit"]
    result: Dict[str, Any]


class MultimodalResponse(BaseModel):
    """Image analysis response model."""

    filename: str
    metadata: Dict[str, Any]


class HealthResponse(BaseModel):
    """Response model for health check endpoints."""

    status: Literal["healthy", "degraded", "unhealthy"]
    services: Dict[str, bool] = Field(default_factory=dict)
    version: Optional[str] = None


class OCRTextInput(BaseModel):
    """Request model for saving OCR text."""

    text: str = Field(
        ...,
        max_length=MAX_OCR_TEXT_LENGTH,
        description="OCR text content to save",
    )


class UnifiedWorkspaceRequest(BaseModel):
    """Request model for unified workspace with automatic workflow detection."""

    query: Optional[str] = Field(
        default="",
        max_length=MAX_QUERY_LENGTH,
        description="Query text (optional based on workflow)",
    )
    answer: Optional[str] = Field(
        default="",
        max_length=MAX_ANSWER_LENGTH,
        description="Answer text (optional based on workflow)",
    )
    edit_request: Optional[str] = Field(
        default="",
        max_length=MAX_EDIT_REQUEST_LENGTH,
        description="Edit instructions for edit workflows",
    )
    ocr_text: Optional[str] = Field(
        default=None,
        max_length=MAX_OCR_TEXT_LENGTH,
        description="OCR text (optional, will load from file if not provided)",
    )
    query_type: Optional[
        Literal["global_explanation", "reasoning", "target_short", "target_long"]
    ] = Field(
        default=None,
        description="Query/answer type for generation style",
    )
    global_explanation_ref: Optional[str] = Field(
        default=None,
        max_length=MAX_ANSWER_LENGTH,
        description="Reference global explanation text to avoid duplication",
    )


class StreamGenerateRequest(BaseModel):
    """Streaming generation request model."""

    prompt: str = Field(
        ...,
        max_length=MAX_PROMPT_LENGTH,
        description="Raw prompt to stream-generate from",
    )
    system_instruction: Optional[str] = Field(
        default=None,
        max_length=MAX_PROMPT_LENGTH,
        description="Optional system instruction",
    )


__all__ = [
    "GenerateQARequest",
    "StreamGenerateRequest",
    "EvalExternalRequest",
    "WorkspaceRequest",
    "UnifiedWorkspaceRequest",
    "HealthResponse",
    "OCRTextInput",
    "MAX_QUERY_LENGTH",
    "MAX_ANSWER_LENGTH",
    "MAX_OCR_TEXT_LENGTH",
    "MAX_EDIT_REQUEST_LENGTH",
    "MAX_COMMENT_LENGTH",
    "MAX_UPLOAD_SIZE_BYTES",
]
