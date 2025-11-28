"""Backend API for the Gemini QA System Web Interface."""

from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Initialize FastAPI app
app = FastAPI(title="Gemini QA System", version="1.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "static"), name="static")

# Set up templates
templates = Jinja2Templates(directory=PROJECT_ROOT / "templates" / "web")

# Create API router
api_router = APIRouter(prefix="/api")


# =============================================================================
# Page Routes
# =============================================================================


@app.get("/", response_class=HTMLResponse)
@app.get("/qa", response_class=HTMLResponse)
async def qa_page(request: Request) -> HTMLResponse:
    """Render QA generation page."""
    return templates.TemplateResponse(request=request, name="qa.html")


@app.get("/eval", response_class=HTMLResponse)
async def eval_page(request: Request) -> HTMLResponse:
    """Render evaluation page."""
    return templates.TemplateResponse(request=request, name="eval.html")


@app.get("/workspace", response_class=HTMLResponse)
async def workspace_page(request: Request) -> HTMLResponse:
    """Render workspace page."""
    return templates.TemplateResponse(request=request, name="workspace.html")


@app.get("/multimodal", response_class=HTMLResponse)
async def multimodal_page(request: Request) -> HTMLResponse:
    """Render multimodal/image analysis page."""
    return templates.TemplateResponse(request=request, name="multimodal.html")


# =============================================================================
# API Routes
# =============================================================================


@api_router.get("/ocr", response_model=OCRResponse)
async def get_ocr() -> OCRResponse:
    """Get OCR text from file."""
    ocr_path = PROJECT_ROOT / "data" / "ocr.txt"

    if ocr_path.exists():
        return OCRResponse(ocr=ocr_path.read_text(encoding="utf-8"))

    return OCRResponse(ocr=None)


@api_router.post("/qa/generate")
async def generate_qa(
    request: QAGenerateRequest,
) -> QABatchResponse | QASingleResponse:
    """Generate QA pairs."""
    # Define question types
    question_types = {
        "global_explanation": "전반 설명",
        "reasoning": "추론",
        "target_short": "타겟 짧은 답변",
        "target_long": "타겟 긴 답변",
    }

    if request.mode == "single":
        if not request.qtype or request.qtype not in question_types:
            raise HTTPException(status_code=400, detail="Invalid question type")

        # Generate single QA pair (mock implementation)
        pair = QAPair(
            type=question_types[request.qtype],
            query=f"[{question_types[request.qtype]}] 샘플 질의입니다.",
            answer=f"이것은 {question_types[request.qtype]} 타입에 대한 샘플 답변입니다.",
        )
        return QASingleResponse(pair=pair)

    # Generate batch QA pairs (mock implementation)
    pairs = [
        QAPair(
            type=type_name,
            query=f"[{type_name}] 샘플 질의입니다.",
            answer=f"이것은 {type_name} 타입에 대한 샘플 답변입니다.",
        )
        for type_name in question_types.values()
    ]
    return QABatchResponse(pairs=pairs)


@api_router.post("/eval/external", response_model=EvalResponse)
async def evaluate_external(request: EvalRequest) -> EvalResponse:
    """Evaluate external answers."""
    if len(request.answers) == 0:
        raise HTTPException(status_code=400, detail="No answers provided")

    # Mock evaluation (replace with actual LLM evaluation)
    answer_labels = ["A", "B", "C", "D", "E", "F"]
    results = []
    best_score = 0.0
    best_id = "A"

    for i, answer in enumerate(request.answers):
        if i >= len(answer_labels):
            break

        label = answer_labels[i]
        # Mock scoring based on answer length
        score = min(100, len(answer) * 2)

        if score > best_score:
            best_score = score
            best_id = label

        results.append(
            EvalResult(
                answer_id=label,
                score=score,
                feedback=f"답변 {label}에 대한 평가 피드백입니다.",
            )
        )

    return EvalResponse(results=results, best=best_id)


@api_router.post("/workspace", response_model=WorkspaceResponse)
async def workspace_operation(request: WorkspaceRequest) -> WorkspaceResponse:
    """Process workspace operations."""
    if request.mode == "inspect":
        # Mock inspection (auto-correction)
        fixed_text = f"[검수됨] {request.answer}"
        return WorkspaceResponse(result=WorkspaceResult(fixed=fixed_text, edited=None))

    if request.mode == "edit":
        if not request.edit_request.strip():
            raise HTTPException(status_code=400, detail="Edit request is required")

        # Mock edit operation
        edited_text = f"[{request.edit_request}에 따라 수정됨] {request.answer}"
        return WorkspaceResponse(result=WorkspaceResult(fixed=None, edited=edited_text))

    raise HTTPException(status_code=400, detail="Invalid mode")


@api_router.post("/multimodal/analyze", response_model=ImageAnalysisResponse)
async def analyze_image(file: UploadFile) -> ImageAnalysisResponse:
    """Analyze an uploaded image."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")

    filename = file.filename or "unknown"

    # Mock image analysis (replace with actual analysis)
    metadata = ImageMetadata(
        has_table_chart=True,
        text_density=0.75,
        topics=["문서", "텍스트", "이미지"],
        extracted_text=f"이것은 {filename} 파일에서 추출된 샘플 텍스트입니다.",
    )

    return ImageAnalysisResponse(filename=filename, metadata=metadata)


# Include API router
app.include_router(api_router)
