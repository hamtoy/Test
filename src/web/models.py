"""Request and Response models for the Gemini QA System Web API."""


from pydantic import BaseModel, Field


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
