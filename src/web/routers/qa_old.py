# mypy: allow-untyped-decorators
"""QA 생성 및 평가 엔드포인트.

This module provides FastAPI endpoints for QA pair generation and evaluation:
- QA pair generation with Neo4j rule integration
- External answer evaluation
- Batch and single QA generation
- Quality validation and cross-validation

## Endpoints
- POST /qa/generate - Generate QA pairs from OCR text
- POST /eval/external - Evaluate external answers

## Structure
**Imports and Setup** (lines 1-40): Module imports and router initialization
**Dependency Management** (lines 41-214): Dependency injection and helper functions
**QA Generation** (lines 215-659): `/qa/generate` endpoint (batch and single)
**Answer Evaluation** (lines 660-end): `/eval/external` endpoint

Note: This is a large file. Consider future refactoring into:
  - qa_generation.py (QA pair generation logic)
  - qa_evaluation.py (Answer evaluation logic)
  - qa_batch.py (Batch processing logic)
  - qa_helpers.py (Shared utilities)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, HTTPException
from tenacity import retry, stop_after_attempt, wait_exponential

from checks.detect_forbidden_patterns import find_formatting_violations, find_violations
from src.agent import GeminiAgent
from src.analysis.cross_validation import CrossValidationSystem
from src.config import AppConfig
from src.config.constants import (
    DEFAULT_ANSWER_RULES,
    QA_BATCH_GENERATION_TIMEOUT,
    QA_BATCH_TYPES,
    QA_BATCH_TYPES_THREE,
    QA_GENERATION_OCR_TRUNCATE_LENGTH,
    QA_SINGLE_GENERATION_TIMEOUT,
    WORKSPACE_GENERATION_TIMEOUT,
    WORKSPACE_UNIFIED_TIMEOUT,
)
from src.config.exceptions import SafetyFilterError
from src.qa.pipeline import IntegratedQAPipeline
from src.qa.rag_system import QAKnowledgeGraph
from src.qa.rule_loader import RuleLoader
from src.qa.validator import UnifiedValidator
from src.web.models import EvalExternalRequest, GenerateQARequest
from src.web.response import APIMetadata, build_response
from src.web.utils import QTYPE_MAP, load_ocr_text, postprocess_answer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["qa"])

_config: Optional[AppConfig] = None
agent: Optional[GeminiAgent] = None
kg: Optional[QAKnowledgeGraph] = None
pipeline: Optional[IntegratedQAPipeline] = None

_kg_cache: Optional["_CachedKG"] = None
_kg_cache_timestamp: Optional[datetime] = None
_CACHE_TTL = timedelta(minutes=5)


class _CachedKG:
    """Lightweight KG wrapper with memoization."""

    def __init__(self, base: QAKnowledgeGraph) -> None:
        self._base = base
        self._constraints: dict[str, list[Dict[str, Any]]] = {}
        self._formatting_text: dict[str, str] = {}
        self._formatting_rules: dict[str, List[Dict[str, Any]]] = {}
        self._rules: dict[tuple[str, int], list[str]] = {}

    def get_constraints_for_query_type(self, query_type: str) -> List[Dict[str, Any]]:
        if query_type in self._constraints:
            return self._constraints[query_type]
        data = self._base.get_constraints_for_query_type(query_type)
        self._constraints[query_type] = data
        return data

    def get_formatting_rules(self, template_type: str) -> str:
        if template_type in self._formatting_text:
            return self._formatting_text[template_type]
        text = self._base.get_formatting_rules(template_type)
        self._formatting_text[template_type] = text
        return text

    def get_formatting_rules_for_query_type(
        self, query_type: str
    ) -> List[Dict[str, Any]]:
        if query_type in self._formatting_rules:
            return self._formatting_rules[query_type]
        rules = self._base.get_formatting_rules_for_query_type(query_type)
        self._formatting_rules[query_type] = rules
        return rules

    def find_relevant_rules(self, query: str, k: int = 10) -> List[str]:
        key = (query[:500], k)
        if key in self._rules:
            return self._rules[key]
        data = self._base.find_relevant_rules(query, k=k)
        self._rules[key] = data
        return data

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)


def set_dependencies(
    config: AppConfig,
    gemini_agent: GeminiAgent,
    qa_pipeline: Optional[IntegratedQAPipeline],
    kg_ref: Optional[QAKnowledgeGraph],
) -> None:
    """주요 의존성 주입."""
    global _config, agent, pipeline, kg
    _config = config
    agent = gemini_agent
    pipeline = qa_pipeline
    kg = kg_ref


def _get_agent() -> Optional[GeminiAgent]:
    try:
        from src.web import api as api_module

        if getattr(api_module, "agent", None) is not None:
            return api_module.agent
    except Exception:
        pass
    return agent


def _get_pipeline() -> Optional[IntegratedQAPipeline]:
    try:
        from src.web import api as api_module

        if getattr(api_module, "pipeline", None) is not None:
            return api_module.pipeline
    except Exception:
        pass
    return pipeline


def _get_kg() -> Optional[QAKnowledgeGraph]:
    try:
        from src.web import api as api_module

        if getattr(api_module, "kg", None) is not None:
            return api_module.kg
    except Exception:
        pass
    return kg


def _get_config() -> AppConfig:
    try:
        from src.web import api as api_module

        cfg_raw = getattr(api_module, "config", None) or _config
        if cfg_raw is not None:
            cfg = cast(AppConfig, cfg_raw)
            # Ensure numeric timeouts even when patched with MagicMock
            for name, default in [
                ("qa_single_timeout", QA_SINGLE_GENERATION_TIMEOUT),
                ("qa_batch_timeout", QA_BATCH_GENERATION_TIMEOUT),
                ("workspace_timeout", WORKSPACE_GENERATION_TIMEOUT),
                ("workspace_unified_timeout", WORKSPACE_UNIFIED_TIMEOUT),
            ]:
                try:
                    value = int(getattr(cfg, name, default))
                except Exception:
                    value = default
                setattr(cfg, name, value)
            try:
                cfg.enable_standard_response = bool(
                    getattr(cfg, "enable_standard_response", False)
                )
                cfg.enable_lats = bool(getattr(cfg, "enable_lats", False))
            except Exception:
                cfg.enable_standard_response = False
                cfg.enable_lats = False
            return cfg
    except Exception:
        if _config is not None:
            return _config
    try:
        from src.web import dependencies

        return dependencies.get_config()
    except Exception:
        return AppConfig()


def _get_validator_class() -> type[CrossValidationSystem] | Any:
    """테스트에서 패치한 CrossValidationSystem을 우선 사용."""
    try:
        from src.web import api as api_module

        return getattr(api_module, "CrossValidationSystem", CrossValidationSystem)
    except Exception:
        return CrossValidationSystem


def _difficulty_hint(ocr_text: str) -> str:
    length = len(ocr_text)
    if length > 4000:
        return "본문이 매우 길어요. 숫자·고유명사 중심으로 2-3문장 이내로 답하세요."
    if length > 2000:
        return "본문이 길어 핵심만 압축해 답하세요. 숫자·고유명사만 그대로 사용하세요."
    return "필요 이상의 부연 없이 핵심 숫자·근거 1문장을 포함해 간결히 답하세요."


def get_cached_kg() -> Optional["_CachedKG"]:
    """Return a cached KG wrapper valid for 5 minutes."""
    global _kg_cache, _kg_cache_timestamp
    current_kg = _get_kg()
    if current_kg is None:
        return None
    now = datetime.now()
    if _kg_cache and _kg_cache_timestamp and now - _kg_cache_timestamp < _CACHE_TTL:
        return _kg_cache
    _kg_cache = _CachedKG(current_kg)
    _kg_cache_timestamp = now
    return _kg_cache


@router.post("/qa/generate")
async def api_generate_qa(body: GenerateQARequest) -> Dict[str, Any]:
    """QA 생성 (배치: 전체 설명 선행 후 병렬, 단일: 타입별 생성)."""
    current_agent = _get_agent()
    if current_agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    ocr_text = body.ocr_text or load_ocr_text(_get_config())

    try:
        start = datetime.now()
        if body.mode in {"batch", "batch_three"}:
            results: list[Dict[str, Any]] = []

            batch_types = body.batch_types or QA_BATCH_TYPES
            if body.mode == "batch_three" and body.batch_types is None:
                batch_types = QA_BATCH_TYPES_THREE
            if not batch_types:
                raise HTTPException(
                    status_code=400, detail="batch_types이 비어 있습니다."
                )

            first_type = batch_types[0]
            first_query: str = ""

            # 1단계: global_explanation 순차 생성
            try:
                first_pair = await asyncio.wait_for(
                    generate_single_qa_with_retry(current_agent, ocr_text, first_type),
                    timeout=_get_config().qa_single_timeout,
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
            remaining_types = batch_types[1:]
            remaining_pairs = await asyncio.wait_for(
                asyncio.gather(
                    *[
                        generate_single_qa_with_retry(
                            current_agent,
                            ocr_text,
                            qtype,
                            previous_queries=[first_query] if first_query else None,
                        )
                        for qtype in remaining_types
                    ],
                    return_exceptions=True,
                ),
                timeout=_get_config().qa_batch_timeout,
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

            duration = (datetime.now() - start).total_seconds()
            meta = APIMetadata(duration=duration)
            return cast(
                Dict[str, Any],
                build_response(
                    {"mode": "batch", "pairs": results},
                    metadata=meta,
                    config=_get_config(),
                ),
            )

        if not body.qtype:
            raise HTTPException(status_code=400, detail="qtype이 필요합니다.")
        pair = await asyncio.wait_for(
            generate_single_qa(current_agent, ocr_text, body.qtype),
            timeout=_get_config().qa_single_timeout,
        )
        duration = (datetime.now() - start).total_seconds()
        meta = APIMetadata(duration=duration)
        return cast(
            Dict[str, Any],
            build_response(
                {"mode": "single", "pair": pair},
                metadata=meta,
                config=_get_config(),
            ),
        )

    except asyncio.TimeoutError:
        timeout_msg = (
            f"생성 시간 초과 ({_get_config().qa_batch_timeout if body.mode == 'batch' else _get_config().qa_single_timeout}초). "
            "다시 시도해주세요."
        )
        raise HTTPException(status_code=504, detail=timeout_msg)
    except Exception as e:
        logger.error("QA 생성 실패: %s", e)
        raise HTTPException(status_code=500, detail=f"생성 실패: {str(e)}")


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


async def generate_single_qa(
    agent: GeminiAgent,
    ocr_text: str,
    qtype: str,
    previous_queries: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """단일 QA 생성 - 규칙 적용 보장 + 호출 최소화."""
    current_kg = _get_kg()
    current_pipeline = _get_pipeline()
    normalized_qtype = QTYPE_MAP.get(qtype, "explanation")
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

    # 중복/병렬 질문 방지 공통 지시
    single_focus_clause = """
[단일 포커스 필수]
- 한 가지 과업만 질문 (근거+전망처럼 두 항목을 동시에 묻지 말 것)
- '와/과/및/또는'으로 서로 다른 질문을 병렬 연결 금지
- 필요하면 한 항목만 묻도록 재작성
"""
    if query_intent:
        query_intent += single_focus_clause
    else:
        query_intent = single_focus_clause

    rule_loader = RuleLoader(current_kg)
    rules_list = rule_loader.get_rules_for_type(normalized_qtype, DEFAULT_ANSWER_RULES)
    query_constraints: list[Dict[str, Any]] = []
    answer_constraints: list[Dict[str, Any]] = []
    formatting_rules: list[str] = []
    unified_validator = UnifiedValidator(current_kg, current_pipeline)
    kg_wrapper: Optional[Any] = get_cached_kg()

    if kg_wrapper is not None:
        try:
            constraints = kg_wrapper.get_constraints_for_query_type(qtype)
            # [Fix] Ensure validation: filter out non-dict items
            valid_constraints = [c for c in constraints if isinstance(c, dict)]
            if len(valid_constraints) < len(constraints):
                logger.warning(
                    "Dropdown invalid constraints: %d/%d (expected dict, got types: %s)",
                    len(constraints) - len(valid_constraints),
                    len(constraints),
                    {type(c).__name__ for c in constraints if not isinstance(c, dict)},
                )

            query_constraints = [
                c for c in valid_constraints if c.get("category") in ["query", "both"]
            ]
            answer_constraints = [
                c for c in valid_constraints if c.get("category") in ["answer", "both"]
            ]
            try:
                fmt_rules = kg_wrapper.get_formatting_rules_for_query_type(
                    normalized_qtype
                )
                # [Fix] Sanitize formatting rules
                valid_fmt_rules = [fr for fr in fmt_rules if isinstance(fr, dict)]
                if len(valid_fmt_rules) < len(fmt_rules):
                    logger.warning(
                        "Invalid formatting rules dropped: %d/%d",
                        len(fmt_rules) - len(valid_fmt_rules),
                        len(fmt_rules),
                    )

                for fr in valid_fmt_rules:
                    desc = fr.get("description") or fr.get("text")
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
            logger.warning("규칙 조회 실패: %s", e)

    # 질의 중복/복합 방지용 공통 제약 추가
    query_constraints.append(
        {
            "description": "단일 과업만 묻기: '와/과/및/또는'으로 병렬 질문(두 가지 이상 요구) 금지",
            "priority": 100,
            "category": "query",
        }
    )

    if not rules_list:
        rules_list = list(DEFAULT_ANSWER_RULES)
        logger.info("Neo4j 규칙 없음, 기본 규칙 사용")

    extra_instructions = "질의 유형에 맞게 작성하세요."
    length_constraint = ""
    if normalized_qtype == "reasoning":
        extra_instructions = """추론형 답변입니다.
- '근거', '추론 과정', '결론' 등 명시적 라벨/소제목 절대 금지
- 소제목을 쓰면 자연스러운 서론-본론-결론 흐름만 유지(헤더로 '서론/본론/결론' 금지)
- 두괄식으로 핵심 전망을 먼저 제시
- '이러한 배경에는', '이를 통해', '따라서' 등 자연스러운 연결어 사용
- '요약문', '정리하면' 등의 헤더 금지"""
        length_constraint = """
[답변 형식]
추론형 답변입니다.
- '요약문' 같은 헤더 사용 금지
- 근거 2~3개와 결론을 명확히 제시
"""
    elif normalized_qtype == "explanation":
        extra_instructions = """설명형 답변입니다.
- 소제목을 쓸 때는 자연스러운 서론-본론-결론 흐름 유지 (헤더에 '서론/본론/결론' 직접 표기 금지)
- 불필요한 반복, 장황한 수식어 금지"""
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
- 소제목 사용 시 자연스러운 흐름만 유지(헤더에 '서론/본론/결론' 표기 금지)
"""
            rules_list = rules_list[:5]

    try:
        queries = await agent.generate_query(
            ocr_text,
            user_intent=query_intent,
            query_type=qtype,
            kg=kg_wrapper or current_kg,
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

            def _priority_value(item: Dict[str, Any]) -> float:
                val = item.get("priority")
                return float(val) if isinstance(val, (int, float)) else 0.0

            answer_constraints.sort(key=_priority_value, reverse=True)
            constraints_text = "\n".join(
                f"[우선순위 {c.get('priority', 0)}] {c.get('description', '')}"
                for c in answer_constraints
            )
        difficulty_text = _difficulty_hint(ocr_text)
        evidence_clause = "숫자·고유명사는 OCR에 나온 값 그대로 사용하고, 근거가 되는 문장을 1개 포함하세요."
        answer_prompt = f"""{length_constraint}

{formatting_text}

[제약사항]
{constraints_text or rules_in_answer}

[질의]: {query}

[OCR 텍스트]
{truncated_ocr}

위 길이/형식 제약과 규칙을 엄격히 준수하여 한국어로 답변하세요.
{difficulty_text}
{evidence_clause}
{extra_instructions}"""

        draft_answer = await agent.rewrite_best_answer(
            ocr_text=ocr_text,
            best_answer=answer_prompt,
            cached_content=None,
            query_type=normalized_qtype,
            kg=kg_wrapper or current_kg,
            constraints=answer_constraints,
            length_constraint=length_constraint,
        )
        if not draft_answer:
            raise SafetyFilterError("No text content in response.")

        # 통합 검증으로 수집할 위반/경고
        val_result = unified_validator.validate_all(draft_answer, normalized_qtype)
        all_issues: list[str] = []

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

        all_violations: list[str] = []
        if normalized_qtype == "reasoning" and (
            "요약문" in draft_answer or "요약" in draft_answer.splitlines()[0]
        ):
            all_violations.append("summary_header_not_allowed")

        # Explicit rule compliance check when KG is available (for tests/validation)
        if kg_wrapper is not None:
            try:
                validator_cls = _get_validator_class()
                validator = validator_cls(kg_wrapper)
                rule_check = validator._check_rule_compliance(
                    draft_answer, normalized_qtype
                )
                score = rule_check.get("score")
                score_val = score if isinstance(score, (int, float)) else 1.0
                if rule_check.get("violations") and score_val < 0.3:
                    all_violations.extend(rule_check.get("violations", []))
            except Exception:
                pass

        # 기존 탐지 + 통합 검증 병합
        violations = find_violations(draft_answer)
        if violations:
            for v in violations:
                v_type = v["type"]
                if v_type.startswith("error_pattern:시의성"):
                    continue
                all_violations.append(v_type)

        formatting_violations = find_formatting_violations(draft_answer)
        for fv in formatting_violations:
            if fv.get("severity") == "error":
                all_violations.append(fv["type"])
                logger.warning(
                    "서식 위반 감지: %s - '%s'", fv.get("description", ""), fv["match"]
                )

        if current_pipeline is not None:
            validation = current_pipeline.validate_output(
                normalized_qtype, draft_answer
            )
            if not validation.get("valid", True):
                all_violations.extend(validation.get("violations", []))
            missing_rules = validation.get("missing_rules_hint", [])
            if missing_rules:
                logger.info("누락 가능성 있는 규칙: %s", missing_rules)

        if val_result.has_errors():
            all_violations.extend(
                [v.get("type", "rule") for v in val_result.violations]
            )
        if val_result.warnings:
            all_issues.extend(val_result.warnings)

        if all_violations:
            all_issues.extend(all_violations[:3])

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

        return {"type": qtype, "query": query, "answer": final_answer}
    except Exception as e:
        logger.error("QA 생성 실패: %s", e)
        raise


@router.post("/eval/external")
async def api_eval_external(body: EvalExternalRequest) -> Dict[str, Any]:
    """외부 답변 3개 평가."""
    current_agent = _get_agent()
    if current_agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    cfg = _get_config()
    ocr_text = load_ocr_text(cfg)

    try:
        from src.workflow.external_eval import evaluate_external_answers

        results = await evaluate_external_answers(
            agent=current_agent,
            ocr_text=ocr_text,
            query=body.query,
            answers=body.answers,
        )

        best = max(results, key=lambda x: x.get("score", 0))
        meta = APIMetadata(duration=0.0)
        return cast(
            Dict[str, Any],
            build_response(
                {"results": results, "best": best.get("candidate_id", "A")},
                metadata=meta,
                config=cfg,
            ),
        )

    except Exception as e:
        logger.error("평가 실패: %s", e)
        raise HTTPException(status_code=500, detail=f"평가 실패: {str(e)}")


__all__ = [
    "api_generate_qa",
    "api_eval_external",
    "generate_single_qa",
    "generate_single_qa_with_retry",
    "router",
    "set_dependencies",
]
