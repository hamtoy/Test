"""API 요청/응답 모델"""

from typing import Any, Dict, List, Literal, Optional
"""Request and Response models for the Gemini QA System Web API."""

from pydantic import BaseModel, Field


class GenerateQARequest(BaseModel):
    """QA 생성 요청"""

    mode: Literal["batch", "single"] = Field(
        ..., description="batch: 4타입 일괄, single: 단일 타입"
    )
    qtype: Optional[
        Literal["global_explanation", "reasoning", "target_short", "target_long"]
    ] = Field(None, description="mode=single일 때 필수")


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
    """외부 답변 평가 요청"""

    query: str = Field(..., description="질의 내용")
    answers: List[str] = Field(..., min_length=3, max_length=3, description="답변 3개")


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
    """워크스페이스 요청"""

    mode: Literal["inspect", "edit"] = Field(
        ..., description="inspect: 검수, edit: 자유 수정"
    )
    query: Optional[str] = Field("", description="질의 (선택)")
    answer: str = Field(..., description="검수/수정할 답변")
    edit_request: Optional[str] = Field("", description="edit 모드일 때 수정 요청")


class WorkspaceResponse(BaseModel):
    """워크스페이스 응답"""

    mode: Literal["inspect", "edit"]
    result: Dict[str, Any]


class MultimodalResponse(BaseModel):
    """이미지 분석 응답"""

    filename: str
    metadata: Dict[str, Any]
class QAGenerateRequest(BaseModel):
    """Request model for QA generation."""

    mode: str = Field(..., description="Generation mode: 'batch' or 'single'")
    qtype: str | None = Field(
        None, description="Question type (required when mode is 'single')"
    )


class QAPair(BaseModel):
    """A single QA pair."""

    type: str = Field(..., description="Question type")
    query: str = Field(..., description="Generated query")
    answer: str = Field(..., description="Generated answer")


class QABatchResponse(BaseModel):
    """Response for batch QA generation."""

    mode: str = "batch"
    pairs: list[QAPair] = Field(..., description="List of generated QA pairs")


class QASingleResponse(BaseModel):
    """Response for single QA generation."""

    mode: str = "single"
    pair: QAPair = Field(..., description="Generated QA pair")


class OCRResponse(BaseModel):
    """Response for OCR text."""

    ocr: str | None = Field(None, description="OCR text content")


class EvalRequest(BaseModel):
    """Request model for answer evaluation."""

    query: str = Field(..., description="The query/question")
    answers: list[str] = Field(..., description="List of answers to evaluate")


class EvalResult(BaseModel):
    """Evaluation result for a single answer."""

    answer_id: str = Field(..., description="Answer identifier (A, B, C, etc.)")
    score: float = Field(..., description="Evaluation score")
    feedback: str = Field(..., description="Evaluation feedback")


class EvalResponse(BaseModel):
    """Response for answer evaluation."""

    results: list[EvalResult] = Field(..., description="Evaluation results")
    best: str = Field(..., description="ID of the best answer")


class WorkspaceRequest(BaseModel):
    """Request model for workspace operations."""

    mode: str = Field(..., description="Operation mode: 'inspect' or 'edit'")
    query: str = Field("", description="Optional query")
    answer: str = Field(..., description="Answer/text to process")
    edit_request: str = Field("", description="Edit request (required for 'edit' mode)")


class WorkspaceResult(BaseModel):
    """Result of workspace operation."""

    fixed: str | None = Field(None, description="Fixed text (for inspect mode)")
    edited: str | None = Field(None, description="Edited text (for edit mode)")


class WorkspaceResponse(BaseModel):
    """Response for workspace operations."""

    result: WorkspaceResult = Field(..., description="Operation result")


class ImageMetadata(BaseModel):
    """Metadata extracted from an image."""

    has_table_chart: bool = Field(
        ..., description="Whether the image contains tables or charts"
    )
    text_density: float = Field(..., description="Text density score")
    topics: list[str] = Field(..., description="Extracted topics")
    extracted_text: str = Field(..., description="Extracted text from image")


class ImageAnalysisResponse(BaseModel):
    """Response for image analysis."""

    filename: str = Field(..., description="Uploaded filename")
    metadata: ImageMetadata = Field(..., description="Image metadata")
