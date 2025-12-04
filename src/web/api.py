# mypy: allow-untyped-decorators
"""웹 API 서버 - 기존 엔진을 HTTP로 래핑."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Literal, Optional
from uuid import uuid4

from checks.detect_forbidden_patterns import find_violations
from fastapi import File, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from fastapi.responses import HTMLResponse, RedirectResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from src.analysis.cross_validation import CrossValidationSystem
from src.agent import GeminiAgent
from src.config import AppConfig
from src.config.constants import DEFAULT_ANSWER_RULES
from src.infra.health import (
    HealthChecker,
    check_gemini_api,
    check_neo4j_with_params,
    check_redis_with_url,
)
from src.infra.structured_logging import setup_structured_logging
from src.qa.pipeline import IntegratedQAPipeline
from src.qa.rag_system import QAKnowledgeGraph
from src.web.session import SessionManager, session_middleware
from src.web.models import OCRTextInput
from src.web.dependencies import container
from src.web.routers import health_router, qa_router, stream_router, workspace_router
from src.web.routers import health as health_router_module
from src.web.routers import qa as qa_router_module
from src.web.routers import stream as stream_router_module
from src.web.routers import workspace as workspace_router_module
from src.web.utils import (
    detect_workflow,
    load_ocr_text as _load_ocr_text,
    log_review_session as _log_review_session,
    postprocess_answer,
    save_ocr_text as _save_ocr_text,
    strip_output_tags,
)
from src.workflow.edit import edit_content
from src.workflow.inspection import inspect_answer

logger = logging.getLogger(__name__)

# 전역 인스턴스 (서버 시작 시 한 번만 초기화)
_config: Optional[AppConfig] = None
agent: Optional[GeminiAgent] = None
kg: Optional[QAKnowledgeGraph] = None
pipeline: Optional[IntegratedQAPipeline] = None
session_manager = SessionManager()
REQUEST_ID_HEADER = "X-Request-Id"

# Optional structured logging
if os.getenv("ENABLE_STRUCT_LOGGING", "").lower() == "true":
    try:
        setup_structured_logging(os.getenv("LOG_LEVEL", "INFO"))
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning(
            "Structured logging init failed: %s", exc
        )


def _get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


async def _request_id_middleware(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    """Attach request_id to request.state and response headers."""
    req_id = request.headers.get(REQUEST_ID_HEADER) or uuid4().hex
    request.state.request_id = req_id
    response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = req_id
    return response


def _log_api_error(
    message: str, *, request: Request, exc: Exception, logger_obj: logging.Logger
) -> None:
    """Log structured error with request context."""
    logger_obj.error(
        message,
        extra={
            "request_id": getattr(request.state, "request_id", ""),
            "path": request.url.path,
            "method": request.method,
            "client": getattr(request.client, "host", ""),
            "user_agent": request.headers.get("user-agent", ""),
            "error_type": exc.__class__.__name__,
        },
        exc_info=True,
    )


async def _error_logging_middleware(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    """Capture unhandled exceptions with request context."""
    try:
        return await call_next(request)
    except HTTPException as http_exc:
        logger.warning(
            "HTTPException",
            extra={
                "request_id": _get_request_id(request),
                "path": request.url.path,
                "method": request.method,
                "status_code": http_exc.status_code,
                "error_type": http_exc.__class__.__name__,
            },
            exc_info=False,
        )
        raise
    except Exception as exc:  # noqa: BLE001
        _log_api_error(
            "Unhandled API error", request=request, exc=exc, logger_obj=logger
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "request_id": _get_request_id(request),
            },
        )


# 정적 파일 & 템플릿 경로
REPO_ROOT = Path(__file__).resolve().parents[2]
# Alias for backward compatibility with tests
PROJECT_ROOT = REPO_ROOT

# 헬스 체크 인스턴스
health_checker = HealthChecker(version=os.getenv("APP_VERSION", "dev"))


class _ConfigProxy:
    """Proxy object to allow patching of config in tests while using lazy initialization."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_config(), name)


# Module-level config proxy for backward compatibility with tests that patch src.web.api.config
config: Any = _ConfigProxy()


def get_config() -> AppConfig:
    """Lazy config initialization to avoid module-level validation errors during testing."""
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


# 유틸리티 래퍼 (기존 import 경로 유지)
def load_ocr_text() -> str:
    """Load OCR text from persisted storage."""
    return _load_ocr_text(config)


def save_ocr_text(text: str) -> None:
    """Persist OCR text to storage."""
    _save_ocr_text(config, text)


def log_review_session(
    mode: Literal["inspect", "edit"],
    question: str,
    answer_before: str,
    answer_after: str,
    edit_request_used: str,
    inspector_comment: str,
    *,
    base_dir: Optional[Path] = None,
) -> None:
    """Append a log review session entry to storage."""
    _log_review_session(
        mode=mode,
        question=question,
        answer_before=answer_before,
        answer_after=answer_after,
        edit_request_used=edit_request_used,
        inspector_comment=inspector_comment,
        base_dir=base_dir,
    )


# QA 헬퍼 함수 재노출 (테스트 호환성)
generate_single_qa = qa_router_module.generate_single_qa
generate_single_qa_with_retry = qa_router_module.generate_single_qa_with_retry


async def _init_health_checks() -> None:
    """Register health checks based on environment."""
    if os.getenv("NEO4J_URI"):
        health_checker.register_check(
            "neo4j",
            lambda: check_neo4j_with_params(
                os.getenv("NEO4J_URI", ""),
                os.getenv("NEO4J_USER", "neo4j"),
                os.getenv("NEO4J_PASSWORD", ""),
            ),
        )
    if os.getenv("REDIS_URL"):
        health_checker.register_check(
            "redis",
            lambda: check_redis_with_url(os.getenv("REDIS_URL", "")),
        )
    if os.getenv("GEMINI_API_KEY"):
        health_checker.register_check("gemini", check_gemini_api)


async def init_resources() -> None:
    """전역 리소스 초기화 (서버 시작 시 호출)."""
    global agent, kg, pipeline
    app_config = get_config()
    container.set_config(app_config)

    if agent is None:
        from jinja2 import Environment, FileSystemLoader

        jinja_env = Environment(
            loader=FileSystemLoader(str(REPO_ROOT / "templates")),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        agent = GeminiAgent(config=app_config, jinja_env=jinja_env)
        logger.info("GeminiAgent 초기화 완료")
        container.set_agent(agent)

    if kg is None:
        try:
            kg = QAKnowledgeGraph()
            logger.info("QAKnowledgeGraph 초기화 완료")
            container.set_kg(kg)
        except Exception as e:
            logger.warning("Neo4j 연결 실패 (RAG 비활성화): %s", e)
            kg = None

    if pipeline is None:
        try:
            pipeline = IntegratedQAPipeline()
            logger.info("IntegratedQAPipeline 초기화 완료")
            container.set_pipeline(pipeline)
        except Exception as e:
            logger.warning(
                "IntegratedQAPipeline 초기화 실패 (Neo4j 환경변수 필요: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD): %s",
                e,
            )
            pipeline = None

    # 라우터 의존성 주입
    qa_router_module.set_dependencies(app_config, agent, pipeline, kg)
    workspace_router_module.set_dependencies(app_config, agent, kg, pipeline)
    stream_router_module.set_dependencies(app_config, agent)
    health_router_module.set_dependencies(
        health_checker, agent=agent, kg=kg, pipeline=pipeline
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """서버 시작/종료 시 리소스 관리."""
    await init_resources()
    await _init_health_checks()
    yield


# FastAPI 앱
app = FastAPI(title="Gemini QA System", version="1.0.0", lifespan=lifespan)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(BaseHTTPMiddleware, dispatch=session_middleware(session_manager))
app.add_middleware(BaseHTTPMiddleware, dispatch=_request_id_middleware)
app.add_middleware(BaseHTTPMiddleware, dispatch=_error_logging_middleware)

# 정적 파일 & 템플릿
app.mount("/static", StaticFiles(directory=str(REPO_ROOT / "static")), name="static")
templates = Jinja2Templates(directory=str(REPO_ROOT / "templates" / "web"))

# 라우터 등록
app.include_router(health_router)
app.include_router(qa_router)
app.include_router(workspace_router)
app.include_router(stream_router)


# ============================================================================
# 페이지 엔드포인트
# ============================================================================


@app.get("/", response_class=RedirectResponse)
async def root() -> str:
    """루트 경로 → /qa로 리다이렉트."""
    return "/qa"


@app.get("/qa", response_class=HTMLResponse)
async def page_qa(request: Request) -> HTMLResponse:
    """QA 생성 페이지."""
    return templates.TemplateResponse(request, "qa.html")


@app.get("/eval", response_class=HTMLResponse)
async def page_eval(request: Request) -> HTMLResponse:
    """외부 답변 평가 페이지."""
    return templates.TemplateResponse(request, "eval.html")


@app.get("/workspace", response_class=HTMLResponse)
async def page_workspace(request: Request) -> HTMLResponse:
    """워크스페이스 페이지."""
    return templates.TemplateResponse(request, "workspace.html")


@app.get("/multimodal", response_class=HTMLResponse)
async def page_multimodal() -> HTMLResponse:
    """멀티모달 페이지 (현재 비활성화)."""
    html = "<html><body><h1>Multimodal feature is disabled.</h1></body></html>"
    return HTMLResponse(content=html)


@app.get("/api/session")
async def get_session(request: Request) -> Dict[str, Any]:
    """현재 세션 정보를 조회합니다."""
    session = getattr(request.state, "session", None)
    if session is None:
        raise HTTPException(status_code=500, detail="세션을 초기화할 수 없습니다.")
    return session_manager.serialize(session)


@app.delete("/api/session")
async def delete_session(request: Request) -> Dict[str, Any]:
    """현재 세션을 종료합니다."""
    session = getattr(request.state, "session", None)
    if session is None:
        raise HTTPException(status_code=500, detail="세션을 초기화할 수 없습니다.")
    session_manager.destroy(session.session_id)
    return {"cleared": True}


# ============================================================================
# OCR 엔드포인트
# ============================================================================


@app.get("/api/ocr")
async def api_get_ocr(request: Request) -> Dict[str, str]:
    """OCR 텍스트 조회."""
    try:
        ocr_text = load_ocr_text()
        return {"ocr": ocr_text}
    except HTTPException as e:
        return {"ocr": "", "error": e.detail}
    except Exception as exc:  # noqa: BLE001
        _log_api_error(
            "Failed to load OCR text", request=request, exc=exc, logger_obj=logger
        )
        raise HTTPException(
            status_code=500, detail="OCR 텍스트 조회 중 오류가 발생했습니다."
        ) from exc


@app.post("/api/ocr")
async def api_save_ocr(request: Request, payload: OCRTextInput) -> Dict[str, str]:
    """OCR 텍스트 저장 (사용자 직접 입력)."""
    try:
        save_ocr_text(payload.text)
        return {"status": "success", "message": "OCR 텍스트가 저장되었습니다."}
    except Exception as exc:  # noqa: BLE001
        _log_api_error(
            "Failed to save OCR text", request=request, exc=exc, logger_obj=logger
        )
        raise HTTPException(status_code=500, detail="OCR 텍스트 저장 실패") from exc


# ============================================================================
# 멀티모달 엔드포인트 (기능 비활성)
# ============================================================================


@app.post("/api/multimodal/analyze")
async def api_analyze_image_disabled(file: UploadFile = File(...)) -> Dict[str, str]:
    """이미지 분석 엔드포인트 (멀티모달 기능 미사용 시 500 반환)."""
    _ = file  # FastAPI 형태를 유지하면서 사용하지 않음
    raise HTTPException(
        status_code=500, detail="Multimodal analysis is disabled in this deployment."
    )


# ============================================================================
# 메트릭 / 분석 / 관리자 엔드포인트
# ============================================================================


@app.get("/metrics")
async def metrics_endpoint() -> Response:
    """Prometheus metrics endpoint."""
    from src.monitoring.metrics import get_metrics

    return Response(content=get_metrics(), media_type="text/plain")


@app.get("/api/analytics/current")
async def current_metrics() -> Dict[str, Any]:
    """실시간 메트릭 조회."""
    from src.analytics.dashboard import UsageDashboard

    dashboard = UsageDashboard()
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


@app.post("/admin/log-level")
async def set_log_level_endpoint(level: str) -> Dict[str, str]:
    """런타임에 로그 레벨 변경 (관리자용)."""
    from src.infra.logging import set_log_level

    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if level.upper() not in valid_levels:
        raise HTTPException(400, f"Invalid level. Use: {valid_levels}")

    if set_log_level(level):
        return {"message": f"Log level set to {level.upper()}"}
    raise HTTPException(500, "Failed to set log level")


__all__ = [
    "app",
    "config",
    "detect_workflow",
    "edit_content",
    "generate_single_qa",
    "generate_single_qa_with_retry",
    "init_resources",
    "inspect_answer",
    "load_ocr_text",
    "log_review_session",
    "postprocess_answer",
    "save_ocr_text",
    "strip_output_tags",
    "CrossValidationSystem",
    "DEFAULT_ANSWER_RULES",
    "find_violations",
]
