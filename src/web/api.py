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

from checks.detect_forbidden_patterns import find_violations
from src.agent import GeminiAgent
from src.analysis.cross_validation import CrossValidationSystem
from src.config import AppConfig
from src.config.constants import DEFAULT_ANSWER_RULES
from src.features.multimodal import MultimodalUnderstanding
from src.qa.pipeline import IntegratedQAPipeline
from src.qa.rag_system import QAKnowledgeGraph
from src.web.models import (
    EvalExternalRequest,
    GenerateQARequest,
    OCRTextInput,
    WorkspaceRequest,
)
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
pipeline: Optional[IntegratedQAPipeline] = None


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
        """Proxy attribute access to the underlying config."""
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
    global agent, kg, mm, pipeline
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
        try:
            mm = MultimodalUnderstanding(kg=kg)
            logger.info("MultimodalUnderstanding 초기화 완료")
        except Exception as e:
            logger.warning(f"Multimodal 초기화 실패: {e}")
            mm = None

    # IntegratedQAPipeline 초기화 추가
    if pipeline is None:
        try:
            pipeline = IntegratedQAPipeline()
            logger.info("IntegratedQAPipeline 초기화 완료")
        except Exception as e:
            logger.warning(f"IntegratedQAPipeline 초기화 실패: {e}")
            pipeline = None


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


@app.post("/api/ocr")
async def api_save_ocr(payload: OCRTextInput) -> Dict[str, str]:
    """OCR 텍스트 저장 (사용자 직접 입력)"""
    try:
        save_ocr_text(payload.text)
        return {"status": "success", "message": "OCR 텍스트가 저장되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    """단일 QA 생성 - IntegratedQAPipeline 완전 통합"""
    from src.config.constants import QA_GENERATION_OCR_TRUNCATE_LENGTH

    # 기본 컨텍스트 생성
    context = {
        "ocr_text": ocr_text,
        "text_density": "high",
        "has_table_chart": False,
        "language_hint": "ko",
        "type": qtype,
    }

    # IntegratedQAPipeline 사용 (Neo4j 연결 시)
    prompt = ocr_text
    if pipeline is not None:
        try:
            prompt = pipeline.template_gen.generate_prompt_for_query_type(qtype, context)
        except Exception as e:
            logger.warning(f"파이프라인 템플릿 생성 실패: {e}")
    elif kg is None:
        # Neo4j 없을 때 기본 규칙 사용
        rules_text = "\n".join(f"- {r}" for r in DEFAULT_ANSWER_RULES)
        prompt = f"[기본 규칙]\n{rules_text}\n\n[텍스트]\n{ocr_text}"

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

        # 금지 패턴 검사
        violations = find_violations(draft_answer)
        if violations:
            logger.warning(f"금지 패턴 발견: {violations}")
            # 위반 시 재생성 요청
            violation_types = ", ".join(set(v["type"] for v in violations))
            draft_answer = await agent.rewrite_best_answer(
                ocr_text=ocr_text,
                best_answer=draft_answer,
                edit_request=f"다음 패턴을 제거해주세요: {violation_types}",
                cached_content=None,
            )

        # IntegratedQAPipeline.validate_output() 사용
        if pipeline is not None:
            validation = pipeline.validate_output(qtype, draft_answer)
            if not validation.get("valid", True):
                logger.warning(f"파이프라인 검증 실패: {validation.get('violations')}")
                violation_desc = "; ".join(validation.get("violations", []))
                draft_answer = await agent.rewrite_best_answer(
                    ocr_text=ocr_text,
                    best_answer=draft_answer,
                    edit_request=f"다음 위반 사항을 수정해주세요: {violation_desc}",
                    cached_content=None,
                )
            missing_rules = validation.get("missing_rules_hint", [])
            if missing_rules:
                logger.info(f"누락 가능성 있는 규칙: {missing_rules}")

        # 규칙 준수 검증 (CrossValidationSystem)
        if kg is not None:
            validator = CrossValidationSystem(kg)
            rule_check = validator._check_rule_compliance(draft_answer, qtype)
            # Check violations list and score
            if rule_check.get("violations") and rule_check.get("score", 1.0) < 0.5:
                logger.warning(f"규칙 위반: {rule_check.get('violations')}")
                # 규칙 위반이 심각하면 재생성
                violation_desc = "; ".join(rule_check.get("violations", []))
                draft_answer = await agent.rewrite_best_answer(
                    ocr_text=ocr_text,
                    best_answer=draft_answer,
                    edit_request=f"다음 규칙 위반을 수정해주세요: {violation_desc}",
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
    except Exception as e:
        logger.error(f"QA 생성 실패: {e}")
        raise


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


@app.post("/api/workspace/generate-answer")
async def api_generate_answer_from_query(body: dict) -> Dict[str, Any]:
    """질문 기반 답변 생성 - 파이프라인 검증 포함"""
    if agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    query = body.get("query", "")
    ocr_text = body.get("ocr_text") or load_ocr_text()

    try:
        answer = await agent.rewrite_best_answer(
            ocr_text=ocr_text,
            best_answer=f"질의: {query}\n\nOCR 텍스트를 기반으로 위 질의에 답변하세요.",
            cached_content=None,
        )

        # 파이프라인 검증
        if pipeline is not None:
            validation = pipeline.validate_output("general", answer)
            if not validation.get("valid", True):
                violation_desc = "; ".join(validation.get("violations", []))
                answer = await agent.rewrite_best_answer(
                    ocr_text=ocr_text,
                    best_answer=answer,
                    edit_request=f"위반 사항 수정: {violation_desc}",
                    cached_content=None,
                )

        # 검수 적용
        final_answer = await inspect_answer(
            agent=agent,
            answer=answer,
            query=query,
            ocr_text=ocr_text,
            context={"type": "general"},
            kg=kg,
            lats=None,
            validator=None,
            cache=None,
        )

        return {"query": query, "answer": final_answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/workspace/generate-query")
async def api_generate_query_from_answer(body: dict) -> Dict[str, Any]:
    """답변 기반 질문 생성"""
    if agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    answer = body.get("answer", "")
    ocr_text = body.get("ocr_text") or load_ocr_text()

    try:
        prompt = f"""
다음 답변에 가장 적합한 질문을 생성하세요.

[OCR 텍스트]
{ocr_text[:1000]}

[답변]
{answer}

위 답변에 대한 자연스러운 질문 1개를 생성하세요. 질문만 출력하세요.
"""
        queries = await agent.generate_query(prompt, user_intent=None)
        query = queries[0] if queries else "질문 생성 실패"

        return {"query": query, "answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/multimodal/analyze")
async def api_analyze_image(file: UploadFile = File(...)) -> Dict[str, Any]:
    """이미지 업로드 + 구조 분석 (OCR은 사용자가 직접 입력)."""
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
    original_filename = file.filename or "uploaded_image"
    safe_name = Path(original_filename).name
    ext = Path(safe_name).suffix.lower()
    allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}
    if ext not in allowed_extensions:
        ext = ""
    secure_filename = f"{uuid4().hex}{ext}"
    temp_path = temp_dir / secure_filename

    try:
        content = await file.read()
        temp_path.write_bytes(content)

        metadata = mm.analyze_image_deep(str(temp_path))

        return {
            "filename": file.filename,
            "metadata": metadata,
        }

    except Exception as e:
        logger.error(f"이미지 분석 실패: {e}")
        raise HTTPException(status_code=500, detail=f"분석 실패: {str(e)}")

    finally:
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
        "pipeline": pipeline is not None,
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
