"""웹 API 서버 - 기존 엔진을 HTTP로 래핑"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from src.agent import GeminiAgent
from src.config import AppConfig
from src.features.multimodal import MultimodalUnderstanding
from src.qa.rag_system import QAKnowledgeGraph
from src.web.models import EvalExternalRequest, GenerateQARequest, WorkspaceRequest
from src.workflow.edit import edit_content
from src.workflow.inspection import inspect_answer

# ============================================================================
# 설정
# ============================================================================

logger = logging.getLogger(__name__)
config = AppConfig()

# 전역 인스턴스 (서버 시작 시 한 번만 초기화)
agent: Optional[GeminiAgent] = None
kg: Optional[QAKnowledgeGraph] = None
mm: Optional[MultimodalUnderstanding] = None

# FastAPI 앱
app = FastAPI(title="Gemini QA System", version="1.0.0")

# 정적 파일 & 템플릿
REPO_ROOT = Path(__file__).resolve().parents[2]
app.mount("/static", StaticFiles(directory=str(REPO_ROOT / "static")), name="static")
templates = Jinja2Templates(directory=str(REPO_ROOT / "templates" / "web"))


# ============================================================================
# 헬퍼 함수
# ============================================================================


def load_ocr_text() -> str:
    """data/inputs/input_ocr.txt 로드"""
    ocr_path = config.input_dir / "input_ocr.txt"
    if not ocr_path.exists():
        raise HTTPException(status_code=404, detail="OCR 파일이 없습니다.")
    return ocr_path.read_text(encoding="utf-8").strip()


def save_ocr_text(text: str) -> None:
    """OCR 텍스트 저장 (이미지 분석 후)"""
    ocr_path = config.input_dir / "input_ocr.txt"
    ocr_path.parent.mkdir(parents=True, exist_ok=True)
    ocr_path.write_text(text, encoding="utf-8")


async def init_resources() -> None:
    """전역 리소스 초기화 (서버 시작 시 호출)"""
    global agent, kg, mm

    if agent is None:
        from jinja2 import Environment, FileSystemLoader

        jinja_env = Environment(
            loader=FileSystemLoader(str(REPO_ROOT / "templates")),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        agent = GeminiAgent(config=config, jinja_env=jinja_env)
        logger.info("GeminiAgent 초기화 완료")

    if kg is None:
        try:
            kg = QAKnowledgeGraph()
            logger.info("QAKnowledgeGraph 초기화 완료")
        except Exception as e:
            logger.warning(f"Neo4j 연결 실패 (RAG 비활성화): {e}")
            kg = None

    if mm is None and kg is not None:
        mm = MultimodalUnderstanding(kg=kg)
        logger.info("MultimodalUnderstanding 초기화 완료")


# ============================================================================
# API 엔드포인트
# ============================================================================


@app.on_event("startup")
async def startup_event() -> None:
    """서버 시작 시 리소스 초기화"""
    await init_resources()


@app.get("/", response_class=RedirectResponse)
async def root() -> str:
    """루트 경로 → /qa로 리다이렉트"""
    return "/qa"


@app.get("/qa", response_class=HTMLResponse)
async def page_qa(request: Request) -> HTMLResponse:
    """QA 생성 페이지"""
    return templates.TemplateResponse("qa.html", {"request": request})


@app.get("/eval", response_class=HTMLResponse)
async def page_eval(request: Request) -> HTMLResponse:
    """외부 답변 평가 페이지"""
    return templates.TemplateResponse("eval.html", {"request": request})


@app.get("/workspace", response_class=HTMLResponse)
async def page_workspace(request: Request) -> HTMLResponse:
    """워크스페이스 페이지"""
    return templates.TemplateResponse("workspace.html", {"request": request})


@app.get("/multimodal", response_class=HTMLResponse)
async def page_multimodal(request: Request) -> HTMLResponse:
    """이미지 분석 페이지"""
    return templates.TemplateResponse("multimodal.html", {"request": request})


@app.get("/api/ocr")
async def api_get_ocr() -> Dict[str, str]:
    """OCR 텍스트 조회"""
    try:
        ocr_text = load_ocr_text()
        return {"ocr": ocr_text}
    except HTTPException as e:
        return {"ocr": "", "error": e.detail}


@app.post("/api/qa/generate")
async def api_generate_qa(body: GenerateQARequest) -> Dict[str, Any]:
    """QA 생성 (4타입 일괄 또는 단일)"""
    if agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    ocr_text = load_ocr_text()

    try:
        if body.mode == "batch":
            # 4타입 일괄 생성
            types = ["global_explanation", "reasoning", "target_short", "target_long"]
            results = []
            for qtype in types:
                pair = await generate_single_qa(agent, ocr_text, qtype)
                results.append(pair)
            return {"mode": "batch", "pairs": results}

        else:
            # 단일 타입 생성
            if not body.qtype:
                raise HTTPException(status_code=400, detail="qtype이 필요합니다.")
            pair = await generate_single_qa(agent, ocr_text, body.qtype)
            return {"mode": "single", "pair": pair}

    except Exception as e:
        logger.error(f"QA 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"생성 실패: {str(e)}")


async def generate_single_qa(
    agent: GeminiAgent, ocr_text: str, qtype: str
) -> Dict[str, Any]:
    """단일 QA 생성 헬퍼"""
    from src.processing.template_generator import DynamicTemplateGenerator

    # 기본 컨텍스트 생성
    context = {
        "ocr_text": ocr_text,
        "text_density": "high",
        "has_table_chart": False,
        "language_hint": "ko",
    }

    # Neo4j 연결 시 규칙 주입
    prompt = ocr_text
    if kg is not None:
        try:
            import os

            template_gen = DynamicTemplateGenerator(
                neo4j_uri=os.getenv("NEO4J_URI", ""),
                neo4j_user=os.getenv("NEO4J_USER", ""),
                neo4j_password=os.getenv("NEO4J_PASSWORD", ""),
            )
            prompt = template_gen.generate_prompt_for_query_type(qtype, context)
            template_gen.close()
        except Exception as e:
            logger.warning(f"템플릿 생성 실패, 기본 프롬프트 사용: {e}")

    # 질의 생성
    queries = await agent.generate_query(prompt, user_intent=None)
    if not queries:
        raise ValueError("질의 생성 실패")

    query = queries[0]

    # 답변 생성 (간단한 더미 생성 - 실제론 평가+재작성 파이프라인)
    # TODO: 실제 구현 시 evaluate + rewrite 추가
    answer = f"[{qtype}] 질의에 대한 답변입니다.\n\n{ocr_text[:200]}..."

    return {
        "type": qtype,
        "query": query,
        "answer": answer,
    }


@app.post("/api/eval/external")
async def api_eval_external(body: EvalExternalRequest) -> Dict[str, Any]:
    """외부 답변 3개 평가"""
    if agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    ocr_text = load_ocr_text()

    try:
        from src.workflow.external_eval import evaluate_external_answers

        results = await evaluate_external_answers(
            agent=agent,
            ocr_text=ocr_text,
            query=body.query,
            answers=body.answers,
        )

        # 최고 답변 찾기
        best = max(results, key=lambda x: x.get("score", 0))

        return {
            "results": results,
            "best": best.get("candidate_id", "A"),
        }

    except Exception as e:
        logger.error(f"평가 실패: {e}")
        raise HTTPException(status_code=500, detail=f"평가 실패: {str(e)}")


@app.post("/api/workspace")
async def api_workspace(body: WorkspaceRequest) -> Dict[str, Any]:
    """검수 또는 자유 수정"""
    if agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    ocr_text = load_ocr_text()

    try:
        if body.mode == "inspect":
            # 검수 모드
            fixed = await inspect_answer(
                agent=agent,
                answer=body.answer,
                query=body.query or "",
                ocr_text=ocr_text,
                context={},
                kg=kg,
                validator=None,
                cache=None,
            )
            return {
                "mode": "inspect",
                "result": {
                    "original": body.answer,
                    "fixed": fixed,
                    "changes": ["자동 교정 완료"],
                },
            }

        else:
            # 자유 수정 모드
            if not body.edit_request:
                raise HTTPException(
                    status_code=400, detail="edit_request가 필요합니다."
                )

            edited = await edit_content(
                agent=agent,
                answer=body.answer,
                ocr_text=ocr_text,
                query=body.query or "",
                edit_request=body.edit_request,
                kg=kg,
                cache=None,
            )
            return {
                "mode": "edit",
                "result": {
                    "original": body.answer,
                    "edited": edited,
                    "request": body.edit_request,
                },
            }

    except Exception as e:
        logger.error(f"워크스페이스 작업 실패: {e}")
        raise HTTPException(status_code=500, detail=f"작업 실패: {str(e)}")


@app.post("/api/multimodal/analyze")
async def api_analyze_image(file: UploadFile = File(...)) -> Dict[str, Any]:
    """이미지 업로드 + OCR + 구조 분석"""
    if mm is None:
        raise HTTPException(
            status_code=500, detail="Multimodal 기능 비활성화 (Neo4j 필요)"
        )

    # 파일 검증
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")

    # 임시 저장
    temp_dir = config.input_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / (file.filename or "uploaded_image")

    try:
        # 파일 저장
        content = await file.read()
        temp_path.write_bytes(content)

        # 분석 실행
        metadata = mm.analyze_image_deep(str(temp_path))

        # OCR 텍스트 저장 (다음 QA 생성에 사용)
        extracted_text = metadata.get("extracted_text", "")
        if extracted_text:
            save_ocr_text(extracted_text)

        return {
            "filename": file.filename,
            "metadata": metadata,
        }

    except Exception as e:
        logger.error(f"이미지 분석 실패: {e}")
        raise HTTPException(status_code=500, detail=f"분석 실패: {str(e)}")

    finally:
        # 임시 파일 정리
        if temp_path.exists():
            temp_path.unlink()


# ============================================================================
# 헬스체크
# ============================================================================


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """서버 상태 확인"""
    return {
        "status": "ok",
        "agent": agent is not None,
        "neo4j": kg is not None,
        "multimodal": mm is not None,
    }
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
