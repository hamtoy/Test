# mypy: disable-error-code=misc
"""웹 API 서버 - 기존 엔진을 HTTP로 래핑"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Literal, Optional, cast
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from tenacity import retry, stop_after_attempt, wait_exponential

from checks.detect_forbidden_patterns import find_formatting_violations, find_violations
from src.agent import GeminiAgent
from src.analysis.cross_validation import CrossValidationSystem
from src.config import AppConfig
from src.config.constants import (
    DEFAULT_ANSWER_RULES,
    QA_BATCH_GENERATION_TIMEOUT,
    QA_SINGLE_GENERATION_TIMEOUT,
    QA_BATCH_TYPES,
    WORKSPACE_GENERATION_TIMEOUT,
    WORKSPACE_UNIFIED_TIMEOUT,
)
from src.features.multimodal import MultimodalUnderstanding
from src.qa.pipeline import IntegratedQAPipeline
from src.qa.rag_system import QAKnowledgeGraph
from src.web.models import (
    EvalExternalRequest,
    GenerateQARequest,
    OCRTextInput,
    UnifiedWorkspaceRequest,
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
QTYPE_MAP = {
    "global_explanation": "explanation",
    "explanation": "explanation",
    "reasoning": "reasoning",
    "target_short": "target",
    "target_long": "target",
    "target": "target",
    "summary": "summary",
    "factual": "target",
    "general": "explanation",
}

# 모듈 레벨 KG 캐시 (5분 TTL)
_kg_cache: Optional["_CachedKG"] = None
_kg_cache_timestamp: Optional[datetime] = None
_CACHE_TTL = timedelta(minutes=5)


class _CachedKG:
    """Lightweight KG wrapper with memoization."""

    def __init__(self, base: QAKnowledgeGraph) -> None:
        self._base = base
        self._constraints: dict[str, list[Dict[str, Any]]] = {}
        self._formatting: dict[str, str] = {}
        self._rules: dict[tuple[str, int], list[str]] = {}

    def get_constraints_for_query_type(self, query_type: str) -> List[Dict[str, Any]]:
        if query_type in self._constraints:
            return self._constraints[query_type]
        data = self._base.get_constraints_for_query_type(query_type)
        self._constraints[query_type] = data
        return data

    def get_formatting_rules(self, template_type: str) -> str:
        if template_type in self._formatting:
            return self._formatting[template_type]
        text = self._base.get_formatting_rules(template_type)
        self._formatting[template_type] = text
        return text

    def find_relevant_rules(self, query: str, k: int = 10) -> List[str]:
        key = (query[:500], k)
        if key in self._rules:
            return self._rules[key]
        data = self._base.find_relevant_rules(query, k=k)
        self._rules[key] = data
        return data

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)


def get_cached_kg() -> Optional["_CachedKG"]:
    """Return a cached KG wrapper valid for 5 minutes."""
    global _kg_cache, _kg_cache_timestamp
    now = datetime.now()
    if (
        _kg_cache is not None
        and _kg_cache_timestamp is not None
        and now - _kg_cache_timestamp < _CACHE_TTL
    ):
        return _kg_cache

    if kg is not None:
        _kg_cache = _CachedKG(kg)
        _kg_cache_timestamp = now
        return _kg_cache
    return None


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

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
            logger.warning(
                f"IntegratedQAPipeline 초기화 실패 (Neo4j 환경변수 필요: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD): {e}"
            )
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


def _strip_output_tags(text: str) -> str:
    """Remove <output> tags from generated text.

    Args:
        text: Text that may contain <output> tags

    Returns:
        Text with <output> tags removed and whitespace stripped
    """
    return text.replace("<output>", "").replace("</output>", "").strip()


def postprocess_answer(answer: str, qtype: str) -> str:
    """답변 후처리 - 서식 규칙 위반 자동 수정."""
    import re

    # 1. 태그 제거
    answer = answer.replace("<output>", "").replace("</output>", "").strip()

    # 2. ###/## 소제목 → **소제목** + 줄바꿈
    answer = re.sub(r"\s*###\s+([^#\n]+)", r"\n\n**\1**\n\n", answer)
    answer = re.sub(r"\s*##\s+([^#\n]+)", r"\n\n**\1**\n\n", answer)

    # 3. 별표 불릿(*) → 하이픈(-) + 줄바꿈 보장
    answer = re.sub(r"\s*\*\s+\*\*([^*]+)\*\*:", r"\n- **\1**:", answer)
    answer = re.sub(r"\s*\*\s+", r"\n- ", answer)

    # 4. 하이픈 불릿 앞에 줄바꿈 보장
    answer = re.sub(r"([^\n])\s*-\s+\*\*", r"\1\n\n- **", answer)

    # 5. 목록 항목 내 콜론 뒤 볼드체 제거
    def fix_list_bold(line: str) -> str:
        if line.strip().startswith("-") and ":**" in line:
            parts = line.split(":**", 1)
            if len(parts) == 2:
                before_colon = parts[0] + ":**"
                after_colon = re.sub(r"\*\*([^*]+)\*\*", r"\1", parts[1])
                return before_colon + after_colon
        return line

    lines = answer.split("\n")
    lines = [fix_list_bold(line) for line in lines]
    answer = "\n".join(lines)

    # 6. 줄글 내 볼드체 제거 (목록/소제목 제외)
    processed_lines: list[str] = []
    for line in answer.split("\n"):
        stripped = line.strip()
        is_list_item = stripped.startswith("-") or bool(re.match(r"^\d+\.", stripped))
        is_heading = (
            stripped.startswith("**")
            and stripped.rstrip().endswith("**")
            and stripped.count("**") == 2
        )
        if not is_list_item and not is_heading:
            line = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
        processed_lines.append(line)
    answer = "\n".join(processed_lines)

    # 7. 과도한 빈 줄 정리 (3줄 이상 → 2줄)
    while "\n\n\n" in answer:
        answer = answer.replace("\n\n\n", "\n\n")

    # 8. target_short: 불필요한 헤더 제거
    if qtype == "target_short":
        lines = answer.split("\n")
        if lines and len(lines) > 1 and ":" in lines[0] and len(lines[0]) < 20:
            answer = "\n".join(lines[1:]).strip()

    # 9. 길이 강제 조정 (target_short/long)
    if qtype == "target_short":
        sentences = [
            s.strip() for s in answer.split(". ") if s.strip() and len(s.strip()) > 5
        ]
        if len(sentences) > 2:
            sentence_with_index = [(i, s) for i, s in enumerate(sentences)]
            top_2 = sorted(sentence_with_index, key=lambda x: len(x[1]), reverse=True)[
                :2
            ]
            top_2_sorted = sorted(top_2, key=lambda x: x[0])
            answer = ". ".join([s for _, s in top_2_sorted]) + "."

    elif qtype == "target_long":
        sentences = [
            s.strip() for s in answer.split(".") if s.strip() and len(s.strip()) > 5
        ]
        if len(sentences) > 4:
            sentence_with_index = [(i, s) for i, s in enumerate(sentences)]
            top_4 = sorted(sentence_with_index, key=lambda x: len(x[1]), reverse=True)[
                :4
            ]
            top_4_sorted = sorted(top_4, key=lambda x: x[0])
            answer = ".  ".join([s for _, s in top_4_sorted]) + "."

    return answer.strip()


def detect_workflow(
    query: Optional[str], answer: Optional[str], edit_request: Optional[str]
) -> str:
    """입력 조합으로 워크플로우 자동 감지

    Args:
        query: 질의 텍스트
        answer: 답변 텍스트
        edit_request: 수정 요청 텍스트

    Returns:
        워크플로우 타입:
        - "full_generation": 질의/답변 둘 다 비어있음 → OCR에서 전체 생성
        - "query_generation": 답변만 있음 (수정요청 없음) → 질의 생성
        - "answer_generation": 질의만 있음 (수정요청 없음) → 답변 생성
        - "edit_query": 질의만 + 수정요청 → 질의 수정
        - "edit_answer": 답변만 + 수정요청 → 답변 수정
        - "edit_both": 질의+답변+수정요청 → 둘 다 수정
        - "rewrite": 질의+답변 (수정요청 없음) → 재작성/검수
    """
    has_query = bool(query and query.strip())
    has_answer = bool(answer and answer.strip())
    has_edit = bool(edit_request and edit_request.strip())

    # 1. 둘 다 비어있음
    if not has_query and not has_answer:
        return "full_generation"

    # 2. 수정요청 있는 경우
    if has_edit:
        if has_query and has_answer:
            return "edit_both"  # 둘 다 수정
        elif has_query:
            return "edit_query"  # 질의만 수정
        elif has_answer:
            return "edit_answer"  # 답변만 수정

    # 3. 수정요청 없는 경우 (일반 생성)
    if not has_query and has_answer:
        return "query_generation"  # 답변 → 질의 생성

    if has_query and not has_answer:
        return "answer_generation"  # 질의 → 답변 생성

    # 4. 둘 다 있고 수정요청 없음
    return "rewrite"  # 재작성/검수


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
    """QA 생성 (배치: 전체 설명 선행 후 병렬, 단일: 타입별 생성)"""
    if agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    ocr_text = load_ocr_text()

    try:
        if body.mode == "batch":
            results: list[Dict[str, Any]] = []

            first_type = QA_BATCH_TYPES[0]
            first_query: str = ""

            # 1단계: global_explanation 순차 생성
            try:
                first_pair = await asyncio.wait_for(
                    generate_single_qa_with_retry(agent, ocr_text, first_type),
                    timeout=QA_SINGLE_GENERATION_TIMEOUT,
                )
                results.append(first_pair)
                first_query = first_pair.get("query", "")
            except Exception as exc:  # noqa: BLE001
                logger.error("%s 생성 실패: %s", first_type, exc)
                results.append(
                    {
                        "type": first_type,
                        "query": "생성 실패",
                        "answer": f"일시적 오류: {str(exc)[:100]}",
                    }
                )

            # 2단계: 나머지 타입 병렬 생성 (중복 방지용 previous_queries 전달)
            remaining_types = QA_BATCH_TYPES[1:]
            remaining_pairs = await asyncio.wait_for(
                asyncio.gather(
                    *[
                        generate_single_qa_with_retry(
                            agent,
                            ocr_text,
                            qtype,
                            previous_queries=[first_query] if first_query else None,
                        )
                        for qtype in remaining_types
                    ],
                    return_exceptions=True,
                ),
                timeout=QA_BATCH_GENERATION_TIMEOUT,
            )

            for i, pair in enumerate(remaining_pairs):
                if isinstance(pair, Exception):
                    logger.error("%s 생성 실패: %s", remaining_types[i], pair)
                    results.append(
                        {
                            "type": remaining_types[i],
                            "query": "생성 실패",
                            "answer": f"일시적 오류: {str(pair)[:100]}",
                        }
                    )
                else:
                    results.append(cast(Dict[str, Any], pair))

            return {"mode": "batch", "pairs": results}

        else:
            if not body.qtype:
                raise HTTPException(status_code=400, detail="qtype이 필요합니다.")
            pair = await asyncio.wait_for(
                generate_single_qa(agent, ocr_text, body.qtype),
                timeout=QA_SINGLE_GENERATION_TIMEOUT,
            )
            return {"mode": "single", "pair": pair}

    except asyncio.TimeoutError:
        timeout_msg = (
            f"생성 시간 초과 ({QA_BATCH_GENERATION_TIMEOUT if body.mode == 'batch' else QA_SINGLE_GENERATION_TIMEOUT}초). "
            "다시 시도해주세요."
        )
        raise HTTPException(status_code=504, detail=timeout_msg)
    except Exception as e:
        logger.error(f"QA 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"생성 실패: {str(e)}")


async def generate_single_qa(
    agent: GeminiAgent,
    ocr_text: str,
    qtype: str,
    previous_queries: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """단일 QA 생성 - 규칙 적용 보장 + 호출 최소화"""
    from src.config.constants import QA_GENERATION_OCR_TRUNCATE_LENGTH

    normalized_qtype = QTYPE_MAP.get(qtype, "explanation")

    # 타입별 질의 스타일 가이드
    query_intent = None
    if qtype == "target_short":
        query_intent = "간단한 사실 확인 질문"
        if previous_queries:
            prev_text = "\n".join(f"- {q}" for q in previous_queries if q)
            query_intent += f"""

[중복 방지]
다음 질의에서 다룬 내용과 겹치지 않도록 구체적 팩트(날짜, 수치, 명칭 등)를 질문하세요:
{prev_text}
"""
    elif qtype == "target_long":
        query_intent = "핵심 요점을 묻는 질문"
        if previous_queries:
            prev_text = "\n".join(f"- {q}" for q in previous_queries if q)
            query_intent += f"""

[중복 방지]
다음 질의와 다른 관점/세부 항목을 묻는 질문을 생성하세요:
{prev_text}
"""
    elif qtype == "reasoning":
        query_intent = "추론/예측 질문"
    elif qtype == "global_explanation":
        query_intent = "전체 내용 설명 질문"

    rules_list: list[str] = []
    query_constraints: list[Dict[str, Any]] = []
    answer_constraints: list[Dict[str, Any]] = []
    formatting_rules: list[str] = []
    kg_wrapper: Optional[Any] = get_cached_kg()

    # 2) Neo4j 규칙/제약 조회
    if kg_wrapper is not None:
        try:
            constraints = kg_wrapper.get_constraints_for_query_type(qtype)
            for c in constraints:
                desc = c.get("description")
                if desc:
                    rules_list.append(desc)
            query_constraints = [
                c for c in constraints if c.get("category") in ["query", "both"]
            ]
            answer_constraints = [
                c for c in constraints if c.get("category") in ["answer", "both"]
            ]
            # 서식 규칙 로드
            try:
                fmt_rules = kg_wrapper.get_formatting_rules_for_query_type(
                    normalized_qtype
                )
                for fr in fmt_rules:
                    desc = fr.get("description")
                    if desc:
                        formatting_rules.append(desc)
                logger.info("서식 규칙 %s개 로드", len(formatting_rules))
            except Exception as e:  # noqa: BLE001
                logger.debug("서식 규칙 로드 실패: %s", e)

            logger.info(
                "%s 타입: 질의 제약 %s개, 답변 제약 %s개 조회",
                qtype,
                len(query_constraints),
                len(answer_constraints),
            )
        except Exception as e:
            logger.warning(f"규칙 조회 실패: {e}")

    # 3) 기본 규칙
    if not rules_list:
        rules_list = list(DEFAULT_ANSWER_RULES)
        logger.info("Neo4j 규칙 없음, 기본 규칙 사용")

    # 질의 유형별 추가 지시 및 길이 제약
    extra_instructions = "질의 유형에 맞게 작성하세요."
    length_constraint = ""
    if normalized_qtype == "reasoning":
        extra_instructions = """추론형 답변입니다.
- '근거', '추론 과정', '결론' 등 명시적 라벨/소제목 절대 금지
- 두괄식으로 핵심 전망을 먼저 제시
- '이러한 배경에는', '이를 통해', '따라서' 등 자연스러운 연결어 사용
- '요약문', '정리하면' 등의 헤더 금지"""
        length_constraint = """
[답변 형식]
추론형 답변입니다.
- '요약문' 같은 헤더 사용 금지
- 근거 2~3개와 결론을 명확히 제시
"""
    elif normalized_qtype == "target":
        if qtype == "target_short":
            length_constraint = """
[CRITICAL - 길이 제약]
**절대 규칙**: 답변은 반드시 1-2문장 이내로 작성하세요.
- 최대 50단어 이내
- 핵심만 추출
- 불필요한 서론/결론 금지
- 예시/부연 설명 금지
"""
            rules_list = rules_list[:3]
        elif qtype == "target_long":
            length_constraint = """
[CRITICAL - 길이 제약]
**절대 규칙**: 답변은 반드시 3-4문장 이내로 작성하세요.
- 최대 100단어 이내
- 핵심 요점만 간결하게
- 불필요한 반복 금지
"""
            rules_list = rules_list[:5]

    try:
        queries = await agent.generate_query(
            ocr_text,
            user_intent=query_intent,
            query_type=qtype,
            kg=kg_wrapper or kg,
            constraints=query_constraints,
        )
        if not queries:
            raise ValueError("질의 생성 실패")

        query = queries[0]

        truncated_ocr = ocr_text[:QA_GENERATION_OCR_TRUNCATE_LENGTH]
        rules_in_answer = "\n".join(f"- {r}" for r in rules_list)
        formatting_text = ""
        if formatting_rules:
            formatting_text = "\n[서식 규칙 - 필수 준수]\n" + "\n".join(
                f"- {r}" for r in formatting_rules
            )
        constraints_text = ""
        if answer_constraints:
            answer_constraints.sort(key=lambda c: c.get("priority", 0), reverse=True)
            constraints_text = "\n".join(
                f"[우선순위 {c.get('priority', 0)}] {c.get('description', '')}"
                for c in answer_constraints
            )
        answer_prompt = f"""{length_constraint}

{formatting_text}

[제약사항]
{constraints_text or rules_in_answer}

[질의]: {query}

[OCR 텍스트]
{truncated_ocr}

위 길이/형식 제약과 규칙을 엄격히 준수하여 한국어로 답변하세요.
{extra_instructions}"""

        draft_answer = await agent.rewrite_best_answer(
            ocr_text=ocr_text,
            best_answer=answer_prompt,
            cached_content=None,
            query_type=normalized_qtype,
            kg=kg_wrapper or kg,
            constraints=answer_constraints,
            length_constraint=length_constraint,
        )

        # 통합 검증: 길이 + 규칙 위반을 한 번에 수집하여 재작성 호출 최소화
        all_issues: list[str] = []

        # 길이 검증: 타겟 단답/장답형에서 문장 수 초과 시
        sentences = [
            s
            for s in draft_answer.replace("?", ".").replace("!", ".").split(".")
            if s.strip()
        ]
        sentence_count = len(sentences)
        if normalized_qtype == "target":
            if qtype == "target_short" and sentence_count > 2:
                all_issues.append(f"1-2문장으로 축소 필요 (현재 {sentence_count}문장)")
            elif qtype == "target_long" and sentence_count > 4:
                all_issues.append(f"3-4문장으로 축소 필요 (현재 {sentence_count}문장)")

        # 규칙 위반 검증
        all_violations: list[str] = []
        if normalized_qtype == "reasoning" and (
            "요약문" in draft_answer or "요약" in draft_answer.splitlines()[0]
        ):
            all_violations.append("summary_header_not_allowed")

        # 금지 패턴 검사
        violations = find_violations(draft_answer)
        if violations:
            for v in violations:
                v_type = v["type"]
                # 시의성 표현 관련 위반은 재작성 트리거에서 제외 (사후 수동 수정 허용)
                if v_type.startswith("error_pattern:시의성"):
                    continue
                all_violations.append(v_type)

        # 서식 규칙 위반 검사 (줄글 볼드 등)
        formatting_violations = find_formatting_violations(draft_answer)
        for fv in formatting_violations:
            if fv.get("severity") == "error":
                all_violations.append(fv["type"])
                logger.warning(
                    "서식 위반 감지: %s - '%s'", fv.get("description", ""), fv["match"]
                )

        # IntegratedQAPipeline.validate_output() 사용
        if pipeline is not None:
            validation = pipeline.validate_output(normalized_qtype, draft_answer)
            if not validation.get("valid", True):
                all_violations.extend(validation.get("violations", []))
            missing_rules = validation.get("missing_rules_hint", [])
            if missing_rules:
                logger.info(f"누락 가능성 있는 규칙: {missing_rules}")

        # 규칙 준수 검증 (CrossValidationSystem)
        if kg_wrapper is not None:
            validator = CrossValidationSystem(kg_wrapper)
            rule_check = validator._check_rule_compliance(
                draft_answer, normalized_qtype
            )
            if rule_check.get("violations") and rule_check.get("score", 1.0) < 0.3:
                all_violations.extend(rule_check.get("violations", []))

        # 위반 사항을 all_issues에 추가 (최대 3개)
        if all_violations:
            all_issues.extend(all_violations[:3])

        # 길이 또는 규칙 위반이 있을 때만 한 번에 재작성
        if all_issues:
            combined_request = "; ".join(all_issues)
            logger.warning("검증 실패, 재생성: %s", combined_request)
            draft_answer = await agent.rewrite_best_answer(
                ocr_text=ocr_text,
                best_answer=draft_answer,
                edit_request=f"다음 사항 수정: {combined_request}",
                cached_content=None,
                constraints=answer_constraints,
                length_constraint=length_constraint,
            )

        final_answer = postprocess_answer(draft_answer, qtype)

        return {
            "type": qtype,
            "query": query,
            "answer": final_answer,
        }
    except Exception as e:
        logger.error(f"QA 생성 실패: {e}")
        raise


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def generate_single_qa_with_retry(
    agent: GeminiAgent,
    ocr_text: str,
    qtype: str,
    previous_queries: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """재시도 로직이 있는 QA 생성 래퍼."""
    return await generate_single_qa(agent, ocr_text, qtype, previous_queries)


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

    async def _run_workspace() -> Dict[str, Any]:
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

        # 자유 수정 모드
        if not body.edit_request:
            raise HTTPException(status_code=400, detail="edit_request가 필요합니다.")

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

    try:
        return await asyncio.wait_for(
            _run_workspace(), timeout=WORKSPACE_GENERATION_TIMEOUT
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"작업 시간 초과 ({WORKSPACE_GENERATION_TIMEOUT}초). 다시 시도해주세요.",
        )
    except Exception as e:
        logger.error(f"워크스페이스 작업 실패: {e}")
        raise HTTPException(status_code=500, detail=f"작업 실패: {str(e)}")


@app.post("/api/workspace/generate-answer")
async def api_generate_answer_from_query(body: Dict[str, Any]) -> Dict[str, Any]:
    """질문 기반 답변 생성 - Neo4j 규칙 동적 주입"""
    if agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    query = body.get("query", "")
    ocr_text = body.get("ocr_text") or load_ocr_text()
    query_type = body.get("query_type", "explanation")
    normalized_qtype = QTYPE_MAP.get(query_type, "explanation")

    # 규칙 로드 (한 번만)
    rules_list: list[str] = []
    if kg is not None:
        try:
            constraints = kg.get_constraints_for_query_type(normalized_qtype)
            for c in constraints:
                desc = c.get("description")
                if desc:
                    rules_list.append(desc)
        except Exception as e:
            logger.debug(f"규칙 로드 실패: {e}")

    if not rules_list:
        rules_list = list(DEFAULT_ANSWER_RULES)

    try:
        rules_text = "\n".join(f"- {r}" for r in rules_list)
        prompt = f"""[지시사항]
반드시 한국어로 답변하세요.
OCR에 없는 정보는 추가하지 마세요.
표/그래프/차트를 직접 언급하지 말고 텍스트 근거만 사용하세요.
<output> 태그를 사용하지 마세요.

[준수 규칙]
{rules_text}

[OCR 텍스트]
{ocr_text[:3000]}

[질의]
{query}

위 OCR 텍스트를 기반으로 질의에 대한 답변을 작성하세요."""

        answer = await asyncio.wait_for(
            agent.rewrite_best_answer(
                ocr_text=ocr_text,
                best_answer=prompt,
                cached_content=None,
                query_type=normalized_qtype,
            ),
            timeout=WORKSPACE_GENERATION_TIMEOUT,
        )

        answer = _strip_output_tags(answer)

        violations = find_violations(answer)
        if violations:
            violation_types = ", ".join(set(v["type"] for v in violations))
            answer = await asyncio.wait_for(
                agent.rewrite_best_answer(
                    ocr_text=ocr_text,
                    best_answer=answer,
                    edit_request=f"한국어로 다시 작성하고 다음 패턴 제거: {violation_types}. <output> 태그 사용 금지.",
                    cached_content=None,
                    query_type=normalized_qtype,
                ),
                timeout=WORKSPACE_GENERATION_TIMEOUT,
            )
            answer = _strip_output_tags(answer)

        return {"query": query, "answer": answer}
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"답변 생성 시간 초과 ({WORKSPACE_GENERATION_TIMEOUT}초). 다시 시도해주세요.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/workspace/generate-query")
async def api_generate_query_from_answer(body: Dict[str, Any]) -> Dict[str, Any]:
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
        queries = await asyncio.wait_for(
            agent.generate_query(prompt, user_intent=None),
            timeout=WORKSPACE_GENERATION_TIMEOUT,
        )
        query = queries[0] if queries else "질문 생성 실패"

        return {"query": query, "answer": answer}
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"질의 생성 시간 초과 ({WORKSPACE_GENERATION_TIMEOUT}초). 다시 시도해주세요.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/workspace/unified")
async def api_unified_workspace(body: UnifiedWorkspaceRequest) -> Dict[str, Any]:
    """통합 워크스페이스 - 모든 조합 지원"""
    if agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    ocr_text = body.ocr_text or load_ocr_text()
    query_type = body.query_type or "global_explanation"
    normalized_qtype = QTYPE_MAP.get(query_type, "explanation")
    global_explanation_ref = body.global_explanation_ref or ""

    # 타입별 질의 의도 힌트
    query_intent = None
    if query_type == "target_short":
        query_intent = "간단한 사실 확인 질문"
        if global_explanation_ref:
            query_intent += f"""

[중복 방지 필수]
다음 전체 설명문에서 이미 다룬 내용과 중복되지 않는 새로운 세부 사실/수치를 질문하세요:
---
{global_explanation_ref[:500]}
---
전체 설명에서 다루지 않은 구체적 정보(날짜, 수치, 특정 명칭 등)에 집중하세요."""
    elif query_type == "target_long":
        query_intent = "핵심 요점을 묻는 질문"
        if global_explanation_ref:
            query_intent += f"""

[중복 방지 필수]
다음 전체 설명문과 다른 관점의 핵심 요점을 질문하세요:
---
{global_explanation_ref[:500]}
---"""
    elif query_type == "reasoning":
        query_intent = "추론/예측 질문"
    elif query_type == "global_explanation":
        query_intent = "전체 내용 설명 질문"

    # 워크플로우 감지
    workflow = detect_workflow(body.query, body.answer, body.edit_request)
    logger.info(f"워크플로우 감지: {workflow}, 질문 유형: {query_type}")

    query = body.query or ""
    answer = body.answer or ""
    changes: list[str] = []

    async def _execute_workflow() -> Dict[str, Any]:
        nonlocal query, answer
        if workflow == "full_generation":
            # 질의와 답변 모두 생성
            changes.append("OCR에서 전체 생성")

            # 질의 생성
            queries = await agent.generate_query(
                ocr_text, user_intent=query_intent, query_type=query_type, kg=kg
            )
            if queries:
                query = queries[0]
                changes.append("질의 생성 완료")

            # 답변 생성
            rules_list: list[str] = []
            if kg is not None:
                try:
                    constraints = kg.get_constraints_for_query_type(normalized_qtype)
                    for c in constraints:
                        desc = c.get("description")
                        if desc:
                            rules_list.append(desc)
                except Exception as e:
                    logger.debug(f"규칙 로드 실패: {e}")

            if not rules_list:
                rules_list = list(DEFAULT_ANSWER_RULES)

            length_constraint = ""
            if query_type == "target_short":
                length_constraint = "답변은 1-2문장, 최대 50단어 이내로 작성하세요."
                rules_list = rules_list[:3]
            elif query_type == "target_long":
                length_constraint = "답변은 3-4문장, 최대 100단어 이내로 작성하세요."
            elif query_type == "reasoning":
                length_constraint = "근거 2~3개와 결론을 명확히 제시하세요."

            rules_text = "\n".join(f"- {r}" for r in rules_list)
            prompt = f"""[지시사항]
반드시 한국어로 답변하세요.
OCR에 없는 정보는 추가하지 마세요.
{length_constraint}

[준수 규칙]
{rules_text}

[OCR 텍스트]
{ocr_text[:3000]}

[질의]
{query}

위 OCR 텍스트를 기반으로 질의에 대한 답변을 작성하세요."""

            answer = await agent.rewrite_best_answer(
                ocr_text=ocr_text,
                best_answer=prompt,
                cached_content=None,
                query_type=normalized_qtype,
            )
            changes.append("답변 생성 완료")

        elif workflow == "query_generation":
            # 답변 → 질의 생성
            changes.append("답변 기반 질의 생성")

            prompt = f"""
다음 답변에 가장 적합한 질문을 생성하세요.

[OCR 텍스트]
{ocr_text[:1000]}

[답변]
{answer}

위 답변에 대한 자연스러운 질문 1개를 생성하세요. 질문만 출력하세요.
"""
            queries = await agent.generate_query(prompt, user_intent=query_intent)
            if not queries:
                logger.warning(
                    "질의 생성 실패: agent.generate_query returned empty list"
                )
                query = ""
                changes.append("질의 생성 실패 - 빈 답변으로 질의 생성 불가")
            else:
                query = queries[0]
                changes.append("질의 생성 완료")

        elif workflow == "answer_generation":
            # 질의 → 답변 생성
            changes.append("질의 기반 답변 생성")

            answer_rules_list: list[str] = []
            if kg is not None:
                try:
                    constraints = kg.get_constraints_for_query_type(normalized_qtype)
                    for c in constraints:
                        desc = c.get("description")
                        if desc:
                            answer_rules_list.append(desc)
                except Exception as e:
                    logger.debug(f"규칙 로드 실패: {e}")

            if not answer_rules_list:
                answer_rules_list = list(DEFAULT_ANSWER_RULES)

            length_constraint = ""
            if query_type == "target_short":
                length_constraint = "답변은 1-2문장, 최대 50단어 이내로 작성하세요."
                answer_rules_list = answer_rules_list[:3]
            elif query_type == "target_long":
                length_constraint = "답변은 3-4문장, 최대 100단어 이내로 작성하세요."
            elif query_type == "reasoning":
                length_constraint = "근거 2~3개와 결론을 명확히 제시하세요."

            rules_text = "\n".join(f"- {r}" for r in answer_rules_list)
            prompt = f"""[지시사항]
반드시 한국어로 답변하세요.
OCR에 없는 정보는 추가하지 마세요.
{length_constraint}

[준수 규칙]
{rules_text}

[OCR 텍스트]
{ocr_text[:3000]}

[질의]
{query}

위 OCR 텍스트를 기반으로 질의에 대한 답변을 작성하세요."""

            answer = await agent.rewrite_best_answer(
                ocr_text=ocr_text,
                best_answer=prompt,
                cached_content=None,
                query_type=normalized_qtype,
            )

            answer = _strip_output_tags(answer)

            violations = find_violations(answer)
            if violations:
                violation_types = ", ".join(set(v["type"] for v in violations))
                answer = await agent.rewrite_best_answer(
                    ocr_text=ocr_text,
                    best_answer=answer,
                    edit_request=f"한국어로 다시 작성하고 다음 패턴 제거: {violation_types}",
                    cached_content=None,
                    query_type=normalized_qtype,
                )
                answer = _strip_output_tags(answer)

            changes.append("답변 생성 완료")

        elif workflow == "rewrite":
            # 재작성/검수
            changes.append("재작성/검수 수행")

            fixed = await inspect_answer(
                agent=agent,
                answer=answer,
                query=query,
                ocr_text=ocr_text,
                context={},
                kg=kg,
                validator=None,
                cache=None,
            )
            answer = fixed
            changes.append("검수 완료")

        elif workflow == "edit_query":
            # 질의만 수정
            changes.append(f"질의 수정 요청: {body.edit_request}")

            # 질의를 "답변"처럼 취급하여 edit_content 호출
            edited_query = await edit_content(
                agent=agent,
                answer=query,  # 질의를 수정 대상으로
                ocr_text=ocr_text,
                query="",  # 빈 문자열
                edit_request=body.edit_request or "",
                kg=kg,
                cache=None,
            )
            query = edited_query
            changes.append("질의 수정 완료")

        elif workflow == "edit_answer":
            # 답변만 수정
            changes.append(f"답변 수정 요청: {body.edit_request}")

            edited_answer = await edit_content(
                agent=agent,
                answer=answer,
                ocr_text=ocr_text,
                query="",  # 질의 없음
                edit_request=body.edit_request or "",
                kg=kg,
                cache=None,
            )
            answer = edited_answer
            changes.append("답변 수정 완료")

        elif workflow == "edit_both":
            # 둘 다 수정
            changes.append(f"질의+답변 수정 요청: {body.edit_request}")

            # 먼저 답변 수정
            edited_answer = await edit_content(
                agent=agent,
                answer=answer,
                ocr_text=ocr_text,
                query=query,
                edit_request=body.edit_request or "",
                kg=kg,
                cache=None,
            )
            answer = edited_answer
            changes.append("답변 수정 완료")

            # 수정된 답변 기반으로 질의도 조정
            edited_query = await edit_content(
                agent=agent,
                answer=query,
                ocr_text=ocr_text,
                query="",
                edit_request=f"다음 답변에 맞게 질의 조정: {answer[:200]}...",
                kg=kg,
                cache=None,
            )
            query = edited_query
            changes.append("질의 조정 완료")

        else:
            raise HTTPException(status_code=400, detail="알 수 없는 워크플로우")

        return {
            "workflow": workflow,
            "query": query,
            "answer": answer,
            "changes": changes,
            "query_type": query_type,
        }

    try:
        return await asyncio.wait_for(
            _execute_workflow(), timeout=WORKSPACE_UNIFIED_TIMEOUT
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"워크플로우 시간 초과 ({WORKSPACE_UNIFIED_TIMEOUT}초). 다시 시도해주세요.",
        )
    except Exception as e:
        logger.error(f"워크플로우 실행 실패: {e}")
        raise HTTPException(status_code=500, detail=f"실행 실패: {str(e)}")


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
