"""웹 API 서버 - 기존 엔진을 HTTP로 래핑"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Literal, Optional
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
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

# 전역 인스턴스 (서버 시작 시 한 번만 초기화)
_config: Optional[AppConfig] = None
agent: Optional[GeminiAgent] = None
kg: Optional[QAKnowledgeGraph] = None
mm: Optional[MultimodalUnderstanding] = None


def get_config() -> AppConfig:
    """Lazy config initialization to avoid module-level validation errors during testing."""
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


# 정적 파일 & 템플릿 경로
REPO_ROOT = Path(__file__).resolve().parents[2]
# Alias for backward compatibility with tests
PROJECT_ROOT = REPO_ROOT


class _ConfigProxy:
    """Proxy object to allow patching of config in tests while using lazy initialization."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_config(), name)


# Module-level config proxy for backward compatibility with tests that patch src.web.api.config
config = _ConfigProxy()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """서버 시작/종료 시 리소스 관리"""
    await init_resources()
    yield


# FastAPI 앱
app = FastAPI(title="Gemini QA System", version="1.0.0", lifespan=lifespan)

# 정적 파일 & 템플릿
app.mount("/static", StaticFiles(directory=str(REPO_ROOT / "static")), name="static")
templates = Jinja2Templates(directory=str(REPO_ROOT / "templates" / "web"))


# ============================================================================
# 헬퍼 함수
# ============================================================================


def load_ocr_text() -> str:
    """data/inputs/input_ocr.txt 로드"""
    ocr_path: Path = config.input_dir / "input_ocr.txt"
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
    app_config = get_config()

    if agent is None:
        from jinja2 import Environment, FileSystemLoader

        jinja_env = Environment(
            loader=FileSystemLoader(str(REPO_ROOT / "templates")),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        agent = GeminiAgent(config=app_config, jinja_env=jinja_env)
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


def log_review_session(
    mode: Literal["inspect", "edit"],
    question: str,
    answer_before: str,
    answer_after: str,
    edit_request_used: str,
    inspector_comment: str,
) -> None:
    """검수/수정 세션 로그를 JSONL 파일에 기록.

    로그 파일 경로: data/outputs/review_logs/review_YYYY-MM-DD.jsonl

    Args:
        mode: 작업 모드 ("inspect" 또는 "edit")
        question: 질의 내용 (빈 문자열 허용)
        answer_before: 수정 전 답변
        answer_after: 수정 후 답변
        edit_request_used: 수정 요청 내용 (inspect 모드에서는 빈 문자열)
        inspector_comment: 검수자 코멘트 (빈 문자열 허용)

    Note:
        이 함수는 메인 기능에 영향을 주지 않도록 모든 예외를 내부에서 처리하고,
        실패 시 콘솔에 경고만 남깁니다.
    """
    try:
        # 로그 디렉터리 경로 설정 및 자동 생성
        log_dir = REPO_ROOT / "data" / "outputs" / "review_logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # 현재 날짜 기반 로그 파일명
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = log_dir / f"review_{today}.jsonl"

        # 로그 엔트리 생성
        timestamp = datetime.now(timezone.utc).isoformat()
        log_entry = {
            "timestamp": timestamp,
            "mode": mode,
            "question": question,
            "answer_before": answer_before,
            "answer_after": answer_after,
            "edit_request_used": edit_request_used,
            "inspector_comment": inspector_comment,
        }

        # JSONL 형식으로 append
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    except Exception as e:
        # 로그 기록 실패 시 경고만 출력, 메인 기능에 영향 없음
        logger.warning(f"검수 로그 기록 실패: {e}")


# ============================================================================
# API 엔드포인트
# ============================================================================


@app.get("/", response_class=RedirectResponse)
async def root() -> str:
    """루트 경로 → /qa로 리다이렉트"""
    return "/qa"


@app.get("/qa", response_class=HTMLResponse)
async def page_qa(request: Request) -> HTMLResponse:
    """QA 생성 페이지"""
    return templates.TemplateResponse(request, "qa.html")


@app.get("/eval", response_class=HTMLResponse)
async def page_eval(request: Request) -> HTMLResponse:
    """외부 답변 평가 페이지"""
    return templates.TemplateResponse(request, "eval.html")


@app.get("/workspace", response_class=HTMLResponse)
async def page_workspace(request: Request) -> HTMLResponse:
    """워크스페이스 페이지"""
    return templates.TemplateResponse(request, "workspace.html")


@app.get("/multimodal", response_class=HTMLResponse)
async def page_multimodal(request: Request) -> HTMLResponse:
    """이미지 분석 페이지"""
    return templates.TemplateResponse(request, "multimodal.html")


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
    """단일 QA 생성 헬퍼 - 검수 파이프라인 포함"""
    from src.config.constants import QA_GENERATION_OCR_TRUNCATE_LENGTH
    from src.processing.template_generator import DynamicTemplateGenerator

    # 기본 컨텍스트 생성
    context = {
        "ocr_text": ocr_text,
        "text_density": "high",
        "has_table_chart": False,
        "language_hint": "ko",
        "type": qtype,
    }

    # Neo4j 연결 시 규칙 주입
    prompt = ocr_text
    template_gen = None
    if kg is not None:
        try:
            import os

            template_gen = DynamicTemplateGenerator(
                neo4j_uri=os.getenv("NEO4J_URI", ""),
                neo4j_user=os.getenv("NEO4J_USER", ""),
                neo4j_password=os.getenv("NEO4J_PASSWORD", ""),
            )
            prompt = template_gen.generate_prompt_for_query_type(qtype, context)
        except Exception as e:
            logger.warning(f"템플릿 생성 실패, 기본 프롬프트 사용: {e}")

    try:
        # 질의 생성
        queries = await agent.generate_query(prompt, user_intent=None)
        if not queries:
            raise ValueError("질의 생성 실패")

        query = queries[0]

        # 초기 답변 생성 (rewrite_best_answer 사용)
        truncated_ocr = ocr_text[:QA_GENERATION_OCR_TRUNCATE_LENGTH]
        draft_answer = await agent.rewrite_best_answer(
            ocr_text=ocr_text,
            best_answer=f"[{qtype}] 질의: {query}\n\n{truncated_ocr}",
            cached_content=None,
        )

        # 검수 파이프라인 적용
        final_answer = await inspect_answer(
            agent=agent,
            answer=draft_answer,
            query=query,
            ocr_text=ocr_text,
            context=context,
            kg=kg,
            lats=None,
            validator=None,
            cache=None,
        )

        return {
            "type": qtype,
            "query": query,
            "answer": final_answer,
        }
    finally:
        if template_gen is not None:
            template_gen.close()


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

            # 검수 로그 기록 (실패해도 메인 응답에 영향 없음)
            log_review_session(
                mode="inspect",
                question=body.query or "",
                answer_before=body.answer,
                answer_after=fixed,
                edit_request_used="",
                inspector_comment=body.inspector_comment or "",
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

            # 수정 로그 기록 (실패해도 메인 응답에 영향 없음)
            log_review_session(
                mode="edit",
                question=body.query or "",
                answer_before=body.answer,
                answer_after=edited,
                edit_request_used=body.edit_request,
                inspector_comment=body.inspector_comment or "",
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

    # 임시 저장 - 보안을 위해 uuid로 파일명 생성
    temp_dir = config.input_dir / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    # 업로드된 파일명에서 디렉터리 정보 제거 및 허용된 확장자만 유지
    original_filename = file.filename or "uploaded_image"
    safe_name = Path(original_filename).name
    ext = Path(safe_name).suffix
    secure_filename = f"{uuid4().hex}{ext}"
    temp_path = temp_dir / secure_filename

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
async def health_endpoint() -> Dict[str, Any]:
    """전체 시스템 상태 확인"""
    from src.infra.health import health_check_async

    result = await health_check_async()
    # 추가 정보
    result["services"] = {
        "agent": agent is not None,
        "neo4j": kg is not None,
        "multimodal": mm is not None,
    }
    return result


@app.get("/health/ready")
async def readiness_endpoint() -> Dict[str, Any]:
    """Kubernetes readiness probe"""
    from src.infra.health import readiness_check

    return await readiness_check()


@app.get("/health/live")
async def liveness_endpoint() -> Dict[str, Any]:
    """Kubernetes liveness probe"""
    from src.infra.health import liveness_check

    return await liveness_check()


# ============================================================================
# 메트릭
# ============================================================================


@app.get("/metrics")
async def metrics_endpoint() -> Response:
    """Prometheus metrics endpoint"""
    from src.monitoring.metrics import get_metrics

    return Response(content=get_metrics(), media_type="text/plain")


# ============================================================================
# 분석 엔드포인트 (Analytics)
# ============================================================================


@app.get("/api/analytics/current")
async def current_metrics() -> Dict[str, Any]:
    """실시간 메트릭 조회

    Returns current usage metrics including today's stats and weekly totals.
    """
    from src.analytics.dashboard import UsageDashboard

    dashboard = UsageDashboard()

    # 오늘 데이터
    today_stats = dashboard.get_today_stats()

    return {
        "today": {
            "sessions": today_stats["sessions"],
            "cost": today_stats["cost"],
            "cache_hit_rate": today_stats["cache_hit_rate"],
        },
        "this_week": {
            "total_cost": dashboard.get_week_total_cost(),
            "avg_quality": dashboard.get_week_avg_quality(),
        },
    }


# ============================================================================
# 관리자 엔드포인트
# ============================================================================


@app.post("/admin/log-level")
async def set_log_level_endpoint(level: str) -> Dict[str, str]:
    """런타임에 로그 레벨 변경 (관리자용)

    Args:
        level: 새 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        결과 메시지
    """
    from src.infra.logging import set_log_level

    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if level.upper() not in valid_levels:
        raise HTTPException(400, f"Invalid level. Use: {valid_levels}")

    if set_log_level(level):
        return {"message": f"Log level set to {level.upper()}"}
    else:
        raise HTTPException(500, "Failed to set log level")
