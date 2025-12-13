# mypy: allow-untyped-decorators
"""웹 API 서버 - 기존 엔진을 HTTP로 래핑."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request

from checks.detect_forbidden_patterns import find_violations
from src.agent import GeminiAgent
from src.analysis.cross_validation import CrossValidationSystem
from src.config import AppConfig
from src.config.constants import DEFAULT_ANSWER_RULES
from src.infra.health import (
    HealthChecker,
    check_gemini_api,
    check_neo4j_with_params,
    check_redis_with_url,
)
from src.infra.logging import setup_logging
from src.infra.structured_logging import setup_structured_logging
from src.qa.pipeline import IntegratedQAPipeline
from src.qa.rag_system import QAKnowledgeGraph
from src.qa.rule_loader import set_global_kg
from src.web.routers import (
    cache_stats_router,
    health_router,
    metrics_router,
    ocr_router,
    pages_router,
    qa_router,
    session_router,
    stream_router,
    workspace_router,
)
from src.web.routers import health as health_router_module
from src.web.routers import ocr as ocr_router_module
from src.web.routers import qa as qa_router_module
from src.web.routers import session as session_router_module
from src.web.routers import stream as stream_router_module
from src.web.routers import workspace as workspace_router_module
from src.web.service_registry import get_registry
from src.web.session import SessionManager, session_middleware
from src.web.utils import (
    detect_workflow,
    postprocess_answer,
    strip_output_tags,
)
from src.web.utils import (
    load_ocr_text as _load_ocr_text,
)
from src.web.utils import (
    log_review_session as _log_review_session,
)
from src.web.utils import (
    save_ocr_text as _save_ocr_text,
)
from src.workflow.edit import edit_content
from src.workflow.inspection import inspect_answer

logger = logging.getLogger(__name__)

# 전역 인스턴스 (서버 시작 시 한 번만 초기화)
# Note: Kept for backward compatibility with existing code
_config: AppConfig | None = None
agent: GeminiAgent | None = None
kg: QAKnowledgeGraph | None = None
pipeline: IntegratedQAPipeline | None = None
session_manager = SessionManager()
_log_listener: Any | None = None  # QueueListener for file logging
REQUEST_ID_HEADER = "X-Request-Id"
ENABLE_MULTIMODAL = os.getenv("ENABLE_MULTIMODAL", "true").lower() == "true"
ENABLE_METRICS = os.getenv("ENABLE_METRICS", "true").lower() == "true"

# Optional structured logging
if os.getenv("ENABLE_STRUCT_LOGGING", "").lower() == "true":
    try:
        setup_structured_logging(os.getenv("LOG_LEVEL", "INFO"))
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("Structured logging init failed: %s", exc)


def _get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


async def _request_id_middleware(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    """Attach request_id to request.state and response headers."""
    req_id = request.headers.get(REQUEST_ID_HEADER) or uuid4().hex
    request.state.request_id = req_id
    response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = req_id
    return response


def _log_api_error(
    message: str,
    *,
    request: Request,
    exc: Exception,
    logger_obj: logging.Logger,
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
    request: Request,
    call_next: RequestResponseEndpoint,
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
            "Unhandled API error",
            request=request,
            exc=exc,
            logger_obj=logger,
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "request_id": _get_request_id(request),
            },
        )


async def _performance_logging_middleware(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    """요청 처리 시간 로깅 (디버깅용)."""
    from time import perf_counter

    start = perf_counter()
    response = await call_next(request)
    duration_ms = (perf_counter() - start) * 1000

    # 느린 요청만 로깅 (>100ms)
    if duration_ms > 100:
        logger.warning(
            "Slow request",
            extra={
                "path": request.url.path,
                "method": request.method,
                "duration_ms": duration_ms,
                "request_id": _get_request_id(request),
            },
        )

    response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
    return response


# 정적 파일 & 템플릿 경로
REPO_ROOT = Path(__file__).resolve().parents[2]
# Alias for backward compatibility with tests
PROJECT_ROOT = REPO_ROOT


def get_config() -> AppConfig:
    """Lazy config initialization to avoid module-level validation errors during testing."""
    global _config
    if _config is None:
        if not os.getenv("GEMINI_API_KEY"):
            # 프로덕션에서는 반드시 키가 필요
            if os.getenv("ENVIRONMENT", "").lower() == "production":
                raise ValueError("GEMINI_API_KEY required in production")
            # 개인/테스트 용도: 더미값으로 설정해 검증 실패를 방지
            os.environ["GEMINI_API_KEY"] = "AIza" + ("A" * 35)  # 총 39자 더미 키
        _config = AppConfig()
    return _config


# 헬스 체크 인스턴스
health_checker = HealthChecker(version=os.getenv("APP_VERSION", "dev"))
# Module-level config object (backward compatible name)
config: AppConfig = get_config()


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
    base_dir: Path | None = None,
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
    await asyncio.sleep(0)
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
    await asyncio.sleep(0)
    global agent, kg, pipeline
    registry = get_registry()

    # ServiceRegistry를 통한 초기화
    if registry.is_initialized():
        logger.info("Resources already initialized via ServiceRegistry")
        # 기존 전역 변수 동기화 (backward compatibility)
        agent = registry.agent
        kg = registry.kg
        pipeline = registry.pipeline
        app_config = registry.config
    else:
        # 처음 초기화하는 경우
        app_config = get_config()
        registry.register_config(app_config)
        logger.info("Config registered to ServiceRegistry")

        from jinja2 import Environment, FileSystemLoader, select_autoescape

        jinja_env = Environment(
            loader=FileSystemLoader(str(REPO_ROOT / "templates")),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        gemini_agent = GeminiAgent(config=app_config, jinja_env=jinja_env)
        registry.register_agent(gemini_agent)
        agent = gemini_agent
        logger.info("GeminiAgent 초기화 완료")

        try:
            knowledge_graph = QAKnowledgeGraph()
            registry.register_kg(knowledge_graph)
            kg = knowledge_graph
            logger.info("QAKnowledgeGraph 초기화 완료")
        except Exception as e:
            logger.warning("Neo4j 연결 실패 (RAG 비활성화): %s", e)
            registry.register_kg(None)
            kg = None
        # RuleLoader 전역 캐시를 위한 KG 설정
        set_global_kg(kg)

        try:
            qa_pipeline = IntegratedQAPipeline()
            registry.register_pipeline(qa_pipeline)
            pipeline = qa_pipeline
            logger.info("IntegratedQAPipeline 초기화 완료")
        except Exception as e:
            logger.warning(
                "IntegratedQAPipeline 초기화 실패 (Neo4j 환경변수 필요: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD): %s",
                e,
            )
            registry.register_pipeline(None)
            pipeline = None

    # 라우터 의존성 주입
    qa_router_module.set_dependencies(app_config, agent, pipeline, kg)
    workspace_router_module.set_dependencies(app_config, agent, kg, pipeline)
    stream_router_module.set_dependencies(app_config, agent)
    health_router_module.set_dependencies(
        health_checker,
        agent=agent,
        kg=kg,
        pipeline=pipeline,
    )
    ocr_router_module.set_dependencies(app_config)
    session_router_module.set_dependencies(session_manager)
    # 전역 KG 설정 (이미 초기화된 경우에도 동기화)
    set_global_kg(kg)

    # Redis 캐시 연결 (QA 답변 캐싱용)
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            import redis.asyncio as aioredis

            from src.web.cache import answer_cache

            redis_client = aioredis.from_url(redis_url)  # type: ignore[no-untyped-call]
            answer_cache.redis = redis_client
            answer_cache.use_redis = True
            logger.info("Redis connected to AnswerCache (TTL: %ds)", answer_cache.ttl)
        except ImportError:
            logger.warning("redis.asyncio not installed, using memory-only cache")
        except Exception as e:
            logger.warning("Redis connection failed: %s, using memory-only cache", e)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """서버 시작/종료 시 리소스 관리."""
    global _log_listener

    # Initialize OpenTelemetry if OTLP endpoint is configured
    from src.infra.telemetry import init_telemetry

    init_telemetry(service_name="gemini-qa-web")

    # Setup file-based logging (app.log, error.log)
    # Only if not using structured logging to stdout
    if os.getenv("ENABLE_STRUCT_LOGGING", "").lower() != "true":
        try:
            _, _log_listener = setup_logging(log_level=os.getenv("LOG_LEVEL"))
            logger.info("File-based logging initialized (app.log, error.log)")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to setup file logging: %s", exc)

    await init_resources()
    await _init_health_checks()
    yield

    # Cleanup: Stop log listener on shutdown
    if _log_listener is not None:
        _log_listener.stop()
        logger.info("Log listener stopped")


# FastAPI 앱
app = FastAPI(title="Gemini QA System", version="1.0.0", lifespan=lifespan)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(BaseHTTPMiddleware, dispatch=session_middleware(session_manager))
app.add_middleware(BaseHTTPMiddleware, dispatch=_request_id_middleware)
app.add_middleware(BaseHTTPMiddleware, dispatch=_error_logging_middleware)
app.add_middleware(BaseHTTPMiddleware, dispatch=_performance_logging_middleware)

# 정적 파일 & 템플릿
app.mount("/static", StaticFiles(directory=str(REPO_ROOT / "static")), name="static")
templates = Jinja2Templates(directory=str(REPO_ROOT / "templates" / "web"))

# 라우터 등록
app.include_router(pages_router)
app.include_router(health_router)
app.include_router(qa_router)
app.include_router(workspace_router)
app.include_router(stream_router)
app.include_router(ocr_router)
app.include_router(session_router)
app.include_router(metrics_router)
app.include_router(cache_stats_router)

__all__ = [
    "DEFAULT_ANSWER_RULES",
    "CrossValidationSystem",
    "app",
    "config",
    "detect_workflow",
    "edit_content",
    "find_violations",
    "generate_single_qa",
    "generate_single_qa_with_retry",
    "init_resources",
    "inspect_answer",
    "load_ocr_text",
    "log_review_session",
    "postprocess_answer",
    "save_ocr_text",
    "strip_output_tags",
]
