# mypy: allow-untyped-decorators
"""워크스페이스 관련 엔드포인트."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
import logging
import re
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from fastapi import APIRouter, HTTPException

if TYPE_CHECKING:
    from src.features.lats import SearchNode

from checks.detect_forbidden_patterns import find_violations
from src.agent import GeminiAgent
from src.analysis.cross_validation import CrossValidationSystem
from src.config import AppConfig
from src.config.constants import DEFAULT_ANSWER_RULES
from src.qa.rule_loader import RuleLoader
from src.qa.validator import UnifiedValidator
from src.qa.pipeline import IntegratedQAPipeline
from src.qa.rag_system import QAKnowledgeGraph
from src.web.models import UnifiedWorkspaceRequest, WorkspaceRequest
from src.web.response import APIMetadata, build_response
from src.web.utils import (
    QTYPE_MAP,
    detect_workflow,
    load_ocr_text,
    log_review_session,
    postprocess_answer,
    strip_output_tags,
)
from src.workflow.edit import edit_content
from src.workflow.inspection import inspect_answer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["workspace"])

_config: Optional[AppConfig] = None
agent: Optional[GeminiAgent] = None
kg: Optional[QAKnowledgeGraph] = None
pipeline: Optional[IntegratedQAPipeline] = None
_validator: Optional[CrossValidationSystem] = None
_difficulty_levels = {
    "long": "본문이 길어 핵심 숫자·근거만 간결히 답하세요.",
    "medium": "불필요한 서론 없이 핵심을 짧게 서술하세요.",
}


def set_dependencies(
    config: AppConfig,
    gemini_agent: GeminiAgent,
    kg_ref: Optional[QAKnowledgeGraph],
    qa_pipeline: Optional[IntegratedQAPipeline] = None,
) -> None:
    """주요 의존성 주입."""
    global _config, agent, kg, pipeline
    _config = config
    agent = gemini_agent
    kg = kg_ref
    pipeline = qa_pipeline
    global _validator
    _validator = None  # reset so it uses latest kg


def _get_agent() -> Optional[GeminiAgent]:
    try:
        from src.web import api as api_module

        if getattr(api_module, "agent", None) is not None:
            return api_module.agent
    except Exception:
        pass
    try:
        from src.web import dependencies

        return dependencies.get_agent()
    except Exception:
        return agent


def _get_kg() -> Optional[QAKnowledgeGraph]:
    try:
        from src.web import api as api_module

        if getattr(api_module, "kg", None) is not None:
            return api_module.kg
    except Exception:
        pass
    try:
        from src.web import dependencies

        return dependencies.get_knowledge_graph()
    except Exception:
        return kg


def _get_pipeline() -> Optional[IntegratedQAPipeline]:
    try:
        from src.web import api as api_module

        if getattr(api_module, "pipeline", None) is not None:
            return api_module.pipeline
    except Exception:
        pass
    try:
        from src.web import dependencies

        return dependencies.get_pipeline()
    except Exception:
        return pipeline


def _get_config() -> AppConfig:
    try:
        from src.web import api as api_module

        if getattr(api_module, "config", None) is not None:
            cfg = api_module.config
        elif _config is not None:
            cfg = _config
        else:
            raise RuntimeError
        for name, default in [
            ("qa_single_timeout", QA_SINGLE_GENERATION_TIMEOUT),
            ("qa_batch_timeout", QA_BATCH_GENERATION_TIMEOUT),
            ("workspace_timeout", WORKSPACE_GENERATION_TIMEOUT),
            ("workspace_unified_timeout", WORKSPACE_UNIFIED_TIMEOUT),
        ]:
            if not hasattr(cfg, name):
                setattr(cfg, name, default)
        return cfg  # type: ignore[return-value]
    except Exception:
        try:
            from src.web import dependencies

            return dependencies.get_config()
        except Exception:
            return AppConfig()


def _get_validator_class() -> type[CrossValidationSystem]:
    """테스트 패치 호환용 CrossValidationSystem 조회."""
    try:
        from src.web import api as api_module

        return getattr(api_module, "CrossValidationSystem", CrossValidationSystem)
    except Exception:
        return CrossValidationSystem


def _get_validator() -> Optional[CrossValidationSystem]:
    """지연 초기화된 validator 반환 (kg 없으면 None)."""
    global _validator
    if _validator is not None:
        return _validator
    current_kg = _get_kg()
    if current_kg is None:
        return None
    try:
        validator_cls = _get_validator_class()
        _validator = validator_cls(current_kg)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Validator 초기화 실패: %s", exc)
        _validator = None
    return _validator


def _difficulty_hint(ocr_text: str) -> str:
    length = len(ocr_text)
    if length > 4000:
        return _difficulty_levels["long"]
    if length > 2000:
        return _difficulty_levels["long"]
    return _difficulty_levels["medium"]


@router.post("/workspace")
async def api_workspace(body: WorkspaceRequest) -> Dict[str, Any]:
    """검수 또는 자유 수정."""
    current_agent = _get_agent()
    current_kg = _get_kg()
    if current_agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    config = _get_config()
    ocr_text = load_ocr_text(config)
    meta_start = datetime.now()

    async def _run_workspace() -> Dict[str, Any]:
        if body.mode == "inspect":
            fixed = await inspect_answer(
                agent=current_agent,
                answer=body.answer,
                query=body.query or "",
                ocr_text=ocr_text,
                context={},
                kg=current_kg,
                validator=_get_validator(),
                cache=None,
            )

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

        if not body.edit_request:
            raise HTTPException(status_code=400, detail="edit_request가 필요합니다.")

        edited = await edit_content(
            agent=current_agent,
            answer=body.answer,
            ocr_text=ocr_text,
            query=body.query or "",
            edit_request=body.edit_request,
            kg=current_kg,
            cache=None,
        )

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
        result = await asyncio.wait_for(
            _run_workspace(), timeout=config.workspace_timeout
        )
        duration = (datetime.now() - meta_start).total_seconds()
        meta = APIMetadata(duration=duration)
        return cast(
            Dict[str, Any], build_response(result, metadata=meta, config=config)
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"작업 시간 초과 ({config.workspace_timeout}초). 다시 시도해주세요.",
        )
    except Exception as e:
        logger.error("워크스페이스 작업 실패: %s", e)
        raise HTTPException(status_code=500, detail=f"작업 실패: {str(e)}")


@router.post("/workspace/generate-answer")
async def api_generate_answer_from_query(body: Dict[str, Any]) -> Dict[str, Any]:
    """질문 기반 답변 생성 - Neo4j 규칙 동적 주입."""
    current_agent = _get_agent()
    current_kg = _get_kg()
    if current_agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    query = body.get("query", "")
    config = _get_config()
    ocr_text = body.get("ocr_text") or load_ocr_text(config)
    meta_start = datetime.now()
    query_type = body.get("query_type", "explanation")
    normalized_qtype = QTYPE_MAP.get(query_type, "explanation")

    rule_loader = RuleLoader(current_kg)
    rules_list = rule_loader.get_rules_for_type(normalized_qtype, DEFAULT_ANSWER_RULES)

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
            current_agent.rewrite_best_answer(
                ocr_text=ocr_text,
                best_answer=prompt,
                cached_content=None,
                query_type=normalized_qtype,
            ),
            timeout=config.workspace_timeout,
        )

        answer = strip_output_tags(answer)

        violations = find_violations(answer)
        if violations:
            violation_types = ", ".join(set(v["type"] for v in violations))
            answer = await asyncio.wait_for(
                current_agent.rewrite_best_answer(
                    ocr_text=ocr_text,
                    best_answer=answer,
                    edit_request=f"한국어로 다시 작성하고 다음 패턴 제거: {violation_types}. <output> 태그 사용 금지.",
                    cached_content=None,
                    query_type=normalized_qtype,
                ),
                timeout=config.workspace_timeout,
            )
            answer = strip_output_tags(answer)

        duration = (datetime.now() - meta_start).total_seconds()
        meta = APIMetadata(duration=duration)
        return cast(
            Dict[str, Any],
            build_response(
                {"query": query, "answer": answer}, metadata=meta, config=config
            ),
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"답변 생성 시간 초과 ({config.workspace_timeout}초). 다시 시도해주세요.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workspace/generate-query")
async def api_generate_query_from_answer(body: Dict[str, Any]) -> Dict[str, Any]:
    """답변 기반 질문 생성."""
    current_agent = _get_agent()
    if current_agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    answer = body.get("answer", "")
    config = _get_config()
    ocr_text = body.get("ocr_text") or load_ocr_text(config)
    meta_start = datetime.now()

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
            current_agent.generate_query(prompt, user_intent=None),
            timeout=config.workspace_timeout,
        )
        query = queries[0] if queries else "질문 생성 실패"

        duration = (datetime.now() - meta_start).total_seconds()
        meta = APIMetadata(duration=duration)
        return cast(
            Dict[str, Any],
            build_response(
                {"query": query, "answer": answer}, metadata=meta, config=config
            ),
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"질의 생성 시간 초과 ({config.workspace_timeout}초). 다시 시도해주세요.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _generate_lats_answer(
    query: str,
    ocr_text: str,
    query_type: str,
) -> tuple[str, dict[str, Any]]:
    """LATS를 사용하여 여러 답변 후보 생성 및 평가 후 최적 선택."""
    current_agent = _get_agent()
    if not current_agent:
        return "", {}

    # 각 전략별 프롬프트 생성
    strategies = [
        {
            "name": "숫자_중심",
            "instruction": "OCR 텍스트에 있는 모든 주요 숫자와 수치를 중심으로 답변하세요.",
        },
        {
            "name": "트렌드_중심",
            "instruction": "시간에 따른 변화, 증가/감소 추세를 중심으로 답변하세요.",
        },
        {
            "name": "비교_중심",
            "instruction": "서로 다른 항목들의 차이점과 비교를 중심으로 답변하세요.",
        },
    ]

    # 각 전략으로 답변 생성 및 평가
    candidates: list[dict[str, Any]] = []
    for strategy in strategies:
        prompt = f"""[질의]
{query}

[OCR 텍스트]
{ocr_text[:2000]}

[답변 전략: {strategy["name"]}]
{strategy["instruction"]}

위 OCR 텍스트를 기반으로 답변을 작성하세요. 마크다운이나 불릿은 사용하지 마세요."""

        try:
            system_prompt = (
                "당신은 한국어로 정확하고 간결한 답변을 작성하는 어시스턴트입니다."
            )
            model = current_agent._create_generative_model(system_prompt)  # noqa: SLF001
            answer = await current_agent._call_api_with_retry(model, prompt)  # noqa: SLF001
            answer = strip_output_tags(answer.strip())

            if answer and len(answer) > 10:
                # 답변 평가
                score = await _evaluate_answer_quality(answer, ocr_text, query_type)
                candidates.append(
                    {
                        "strategy": strategy["name"],
                        "answer": answer,
                        "score": score,
                    }
                )
                logger.info("LATS 후보 생성: %s (점수: %.2f)", strategy["name"], score)
        except Exception as e:
            logger.debug("LATS 답변 생성 실패 (%s): %s", strategy["name"], e)
            continue

    # 최고 점수 답변 선택
    if candidates:
        best = max(candidates, key=lambda x: float(x["score"]))
        meta = {
            "candidates": len(candidates),
            "best_strategy": best["strategy"],
            "best_score": best["score"],
            "all_scores": [c["score"] for c in candidates],
        }
        best_answer = str(best["answer"])
        return best_answer, meta

    return "", {}


async def _evaluate_answer_quality(
    answer: str,
    ocr_text: str,
    query_type: str,
) -> float:
    """답변 품질을 0.0-1.0로 점수화."""
    if not answer:
        return 0.0

    score = 0.5

    # 1. 길이 검증
    if 10 < len(answer) < 5000:
        score += 0.1

    # 2. OCR 숫자 포함 검증
    import re

    ocr_numbers = set(re.findall(r"\d+(?:\.\d+)?", ocr_text))
    answer_numbers = set(re.findall(r"\d+(?:\.\d+)?", answer))
    if ocr_numbers and answer_numbers & ocr_numbers:
        score += 0.2

    # 3. 금지 패턴 검증
    forbidden_patterns = [r"^\s*[-*•]\s", r"\*\*", r"__"]
    has_forbidden = any(re.search(p, answer, re.MULTILINE) for p in forbidden_patterns)
    if not has_forbidden:
        score += 0.1

    return min(1.0, max(0.0, score))


async def _lats_evaluate_answer(node: "SearchNode") -> float:
    """LATS 평가: 생성된 답변의 품질을 0.0-1.0로 점수화."""
    # SearchState에서 필요한 정보 추출
    state = node.state
    current_answer = state.current_answer or ""
    ocr_text = state.ocr_text or ""

    if not current_answer:
        return 0.0

    score = 0.5  # 기본 점수

    # 1. 길이 검증 (너무 짧거나 길면 감점)
    if 10 < len(current_answer) < 5000:
        score += 0.1

    # 2. OCR 텍스트에서 주요 숫자가 포함되었는지 검증
    import re

    ocr_numbers = set(re.findall(r"\d+(?:\.\d+)?", ocr_text))
    answer_numbers = set(re.findall(r"\d+(?:\.\d+)?", current_answer))
    if ocr_numbers and answer_numbers & ocr_numbers:
        # 교집합이 있으면 OCR의 숫자를 사용했다는 증거
        score += 0.2

    # 3. 금지 패턴 검증 (마크다운 불릿 등)
    forbidden_patterns = [r"^\s*[-*•]\s", r"\*\*", r"__"]
    has_forbidden = any(
        re.search(p, current_answer, re.MULTILINE) for p in forbidden_patterns
    )
    if not has_forbidden:
        score += 0.1

    # 4. Neo4j 제약사항 검증 (선택)
    current_kg = _get_kg()
    if current_kg:
        # 간단한 제약사항 체크 (예: 최소 길이, 형식 등)
        # 실제로는 각 제약사항을 순회하며 검증해야 함
        with contextlib.suppress(Exception):
            score += 0.1

    return min(1.0, max(0.0, score))


@router.post("/workspace/unified")
async def api_unified_workspace(body: UnifiedWorkspaceRequest) -> Dict[str, Any]:
    """통합 워크스페이스 - 모든 조합 지원."""
    current_agent = _get_agent()
    current_kg = _get_kg()
    current_pipeline = _get_pipeline()
    config = _get_config()
    unified_validator = UnifiedValidator(current_kg, current_pipeline)
    meta_start = datetime.now()
    if current_agent is None:
        raise HTTPException(status_code=500, detail="Agent 초기화 실패")

    ocr_text = body.ocr_text or load_ocr_text(_get_config())
    query_type = body.query_type or "global_explanation"
    normalized_qtype = QTYPE_MAP.get(query_type, "explanation")
    global_explanation_ref = body.global_explanation_ref or ""

    query_intent = None
    rule_loader = RuleLoader(current_kg)
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

    workflow = detect_workflow(body.query or "", body.answer or "", body.edit_request)
    logger.info("워크플로우 감지: %s, 질문 유형: %s", workflow, query_type)

    query = body.query or ""
    answer = body.answer or ""
    changes: list[str] = []
    reference_text = global_explanation_ref or ""

    def _shorten_target_query(text: str) -> str:
        """타겟 단답용 질의가 장문/설명문으로 생성될 때 한 문장으로 압축."""
        clean = re.sub(r"\s+", " ", text or "").strip()
        # 문장 단위로 자르되, 없으면 단어 수로 제한
        parts = re.split(r"[?.!]\s*", clean)
        candidate = parts[0] if parts and parts[0] else clean
        words = candidate.split()
        if len(words) > 20:
            candidate = " ".join(words[:20])
        return candidate.strip()

    def _sanitize_output(text: str) -> str:
        """불릿/마크다운/여분 공백을 제거해 일관된 문장만 남긴다."""
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
        text = re.sub(r"\*(.*?)\*", r"\1", text)
        text = re.sub(r"[_]{1,2}(.*?)[_]{1,2}", r"\1", text)
        text = text.replace("*", "")
        text = re.sub(r"^[\-\u2022]\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _dedup_with_reference(text: str, reference: str, qtype: str) -> str:
        """참조 문단과 중복되는 문장을 제거 (간단 정규화 기반)."""

        def normalize(chunk: str) -> str:
            chunk = chunk.lower()
            chunk = re.sub(r"[\s\*\-_`~#]+", "", chunk)
            chunk = re.sub(r"[.,:;\"'’”“‘!?()/\\]", "", chunk)
            chunk = chunk.replace(",", "")
            return chunk

        ref_norm = normalize(reference)
        sentences = [
            s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()
        ]
        kept: list[str] = []
        for s in sentences:
            norm = normalize(s.strip(" -•\t"))
            if not norm or len(norm) < 10:
                continue
            if norm in ref_norm:
                continue
            kept.append(s.strip())
        if not kept:
            # 타겟 단답일 때는 숫자/퍼센트를 우선 추출해 중복 최소화
            if qtype == "target_short":
                num_match = re.search(
                    r"[0-9][0-9,\.]*\s*억\s*달러|[0-9]+(?:\.[0-9]+)?\s*%|[0-9][0-9,\.]*",
                    text,
                )
                if num_match:
                    return num_match.group(0).strip()
            if qtype in {"target_short", "target_long"}:
                return "참조 내용과 중복되지 않는 추가 정보가 없습니다."
            return sentences[0].strip() if sentences else text.strip()
        return ". ".join(kept[:4])

    async def _execute_workflow() -> Dict[str, Any]:
        nonlocal query, answer
        length_constraint: str = ""
        answer_constraints: list[Dict[str, Any]] = []
        if workflow == "full_generation":
            changes.append("OCR에서 전체 생성")

            queries = await current_agent.generate_query(
                ocr_text,
                user_intent=query_intent,
                query_type=query_type,
                kg=current_kg,
            )
            if queries:
                query = queries[0]
                if query_type == "target_short":
                    query = _shorten_target_query(query)
                changes.append("질의 생성 완료")

            rules_list: list[str] = rule_loader.get_rules_for_type(
                normalized_qtype, DEFAULT_ANSWER_RULES
            )
            rule_texts: list[str] = []
            if current_kg is not None:
                try:
                    kg_rules = current_kg.get_rules_for_query_type(normalized_qtype)
                    for r in kg_rules:
                        txt = r.get("text")
                        if txt:
                            rule_texts.append(txt)
                except Exception as exc:
                    logger.debug("Rule 로드 실패: %s", exc)

            if query_type == "target_short":
                length_constraint = "답변은 불릿·마크다운(볼드/기울임) 없이 한 문장으로, 최대 50단어 이내로 작성하세요."
                rules_list = rules_list[:3]
            elif query_type == "target_long":
                length_constraint = "답변은 불릿·마크다운(볼드/기울임) 없이 3-4문장, 최대 100단어 이내로 작성하세요."
            elif query_type == "reasoning":
                length_constraint = "불릿·마크다운(볼드/기울임) 없이 한 단락으로 간결하게 추론을 제시하세요."

            dedup_section = ""
            if reference_text:
                dedup_section = f"""
[중복 금지]
다음 전체 설명문에 이미 나온 표현/숫자를 그대로 복사하지 말고, 필요한 경우 다른 문장으로 요약하세요:
---
{reference_text[:500]}
---"""

        rules_text = "\n".join(f"- {r}" for r in rules_list)
        extra_rules_text = "\n".join(f"- {t}" for t in rule_texts[:5])
        difficulty_text = _difficulty_hint(ocr_text)
        evidence_clause = (
            "숫자·고유명사는 OCR에 나온 값 그대로 사용하고, 근거 문장을 1개 포함하세요."
        )
        prompt = f"""[지시사항]
반드시 한국어로 답변하세요.
OCR에 없는 정보는 추가하지 마세요.
{length_constraint}
{dedup_section}
{difficulty_text}
{evidence_clause}

[준수 규칙]
{rules_text}
{extra_rules_text}

[OCR 텍스트]
{ocr_text[:3000]}

[질의]
{query}

위 OCR 텍스트를 기반으로 답변을 작성하세요."""

        # LATS 다중 후보 생성 활성화
        if (
            workflow == "full_generation"
            and body.use_lats
            and _get_config().enable_lats
        ):
            try:
                logger.info("LATS 다중 후보 생성 시작 (full_generation)")
                answer, lats_meta = await _generate_lats_answer(
                    query=query,
                    ocr_text=ocr_text,
                    query_type=normalized_qtype,
                )
                if answer:
                    answer = strip_output_tags(answer)
                    changes.append(
                        f"LATS: {lats_meta.get('candidates', 0)}개 후보, "
                        f"최적={lats_meta.get('best_strategy', 'N/A')}, "
                        f"점수={lats_meta.get('best_score', 0):.2f}"
                    )
                else:
                    raise ValueError("LATS 답변 후보 없음")
            except Exception as e:
                logger.warning("LATS 실패, 기본 생성: %s", e)
                answer = await current_agent.rewrite_best_answer(
                    ocr_text=ocr_text,
                    best_answer=prompt,
                    cached_content=None,
                    query_type=normalized_qtype,
                )
                answer = strip_output_tags(answer)
                changes.append("답변 생성 완료 (기본)")
        elif workflow == "full_generation":
            answer = await current_agent.rewrite_best_answer(
                ocr_text=ocr_text,
                best_answer=prompt,
                cached_content=None,
                query_type=normalized_qtype,
            )
            answer = strip_output_tags(answer)
            changes.append("답변 생성 완료")

        elif workflow == "query_generation":
            changes.append("질문 생성 요청")
            queries = await current_agent.generate_query(
                ocr_text,
                user_intent=query_intent,
                query_type=query_type,
                kg=current_kg,
            )
            query = queries[0] if queries else "질문 생성 실패"
            if query_type == "target_short":
                query = _shorten_target_query(query)
            changes.append("질문 생성 완료")

        elif workflow == "answer_generation":
            changes.append("답변 생성 요청")
            rules_list = rule_loader.get_rules_for_type(
                normalized_qtype, DEFAULT_ANSWER_RULES
            )
            answer_rule_texts: list[str] = []
            if current_kg is not None:
                try:
                    constraints = current_kg.get_constraints_for_query_type(
                        normalized_qtype
                    )
                    for c in constraints:
                        desc = c.get("description")
                        if desc:
                            rules_list.append(desc)
                except Exception as exc:
                    logger.debug("규칙 로드 실패: %s", exc)
                try:
                    kg_rules = current_kg.get_rules_for_query_type(normalized_qtype)
                    for r in kg_rules:
                        txt = r.get("text")
                        if txt:
                            answer_rule_texts.append(txt)
                except Exception as exc:
                    logger.debug("Rule 로드 실패: %s", exc)

            rules_text = "\n".join(f"- {r}" for r in rules_list)
            extra_rules_text = "\n".join(f"- {t}" for t in answer_rule_texts[:5])
            length_constraint = ""
            if query_type == "target_short":
                length_constraint = "답변은 불릿·마크다운(볼드/기울임) 없이 한 문장으로, 최대 50단어 이내로 작성하세요."
            elif query_type == "target_long":
                length_constraint = "답변은 불릿·마크다운(볼드/기울임) 없이 3-4문장, 최대 100단어 이내로 작성하세요."
            elif query_type == "reasoning":
                length_constraint = (
                    "불릿·마크다운(볼드/기울임) 없이 한 단락으로 간결하게 추론을 제시하세요. "
                    "근거/추론/결론 같은 섹션 제목은 사용하지 마세요."
                )

            dedup_section = ""
            if reference_text:
                dedup_section = f"""
[중복 금지]
다음 전체 설명문에 이미 나온 표현/숫자를 그대로 복사하지 말고, 필요한 경우 다른 문장으로 요약하세요:
---
{reference_text[:500]}
---"""
            prompt = f"""[지시사항]
반드시 한국어로 답변하세요.
OCR에 없는 정보는 추가하지 마세요.
{length_constraint}
{dedup_section}

[준수 규칙]
{rules_text}
{extra_rules_text}

[OCR 텍스트]
{ocr_text[:3000]}

[질의]
{query}

[추가 지침]
{body.edit_request or "(없음)"}

위 OCR 텍스트를 기반으로 답변을 작성하세요."""

            # LATS 다중 후보 생성 활성화
            if body.use_lats and _get_config().enable_lats:
                try:
                    logger.info("LATS 다중 후보 생성 시작 (answer_generation)")
                    answer, lats_meta = await _generate_lats_answer(
                        query=query,
                        ocr_text=ocr_text,
                        query_type=normalized_qtype,
                    )
                    if answer:
                        answer = strip_output_tags(answer)
                        changes.append(
                            f"LATS: {lats_meta.get('candidates', 0)}개 후보, "
                            f"최적={lats_meta.get('best_strategy', 'N/A')}, "
                            f"점수={lats_meta.get('best_score', 0):.2f}"
                        )
                    else:
                        raise ValueError("LATS 답변 후보 없음")
                except Exception as e:
                    logger.warning("LATS 실패, 기본 생성: %s", e)
                    answer = await current_agent.rewrite_best_answer(
                        ocr_text=ocr_text,
                        best_answer=prompt,
                        cached_content=None,
                        query_type=normalized_qtype,
                    )
                    answer = strip_output_tags(answer)
                    changes.append("답변 생성 완료 (기본)")
            else:
                answer = await current_agent.rewrite_best_answer(
                    ocr_text=ocr_text,
                    best_answer=prompt,
                    cached_content=None,
                    query_type=normalized_qtype,
                )
                answer = strip_output_tags(answer)
                changes.append("답변 생성 완료")

        elif workflow == "rewrite":
            changes.append("답변 재작성 요청")
            answer = await edit_content(
                agent=current_agent,
                answer=answer,
                ocr_text=ocr_text,
                query=query,
                edit_request="형식/길이 위반을 자동 교정",
                kg=current_kg,
                cache=None,
            )
            answer = strip_output_tags(answer)
            changes.append("재작성 완료")

        elif workflow == "edit_query":
            changes.append("질의 수정 요청")
            edited_query = await edit_content(
                agent=current_agent,
                answer=query,
                ocr_text=ocr_text,
                query="",
                edit_request=body.edit_request or "",
                kg=current_kg,
                cache=None,
            )
            query = edited_query
            changes.append("질의 수정 완료")

        elif workflow == "edit_answer":
            changes.append(f"답변 수정 요청: {body.edit_request}")
            edited_answer = await edit_content(
                agent=current_agent,
                answer=answer,
                ocr_text=ocr_text,
                query=query,
                edit_request=body.edit_request or "",
                kg=current_kg,
                cache=None,
            )
            answer = edited_answer
            changes.append("답변 수정 완료")

        elif workflow == "edit_both":
            changes.append(f"질의+답변 수정 요청: {body.edit_request}")
            edited_answer = await edit_content(
                agent=current_agent,
                answer=answer,
                ocr_text=ocr_text,
                query=query,
                edit_request=body.edit_request or "",
                kg=current_kg,
                cache=None,
            )
            answer = edited_answer
            changes.append("답변 수정 완료")

            edited_query = await edit_content(
                agent=current_agent,
                answer=query,
                ocr_text=ocr_text,
                query="",
                edit_request=f"다음 답변에 맞게 질의 조정: {answer[:200]}...",
                kg=current_kg,
                cache=None,
            )
            query = edited_query
            changes.append("질의 조정 완료")

        else:
            raise HTTPException(status_code=400, detail="알 수 없는 워크플로우")

        if answer:
            if current_pipeline is not None:
                try:
                    validation = current_pipeline.validate_output(
                        normalized_qtype, answer
                    )
                    if not validation.get("valid", True):
                        violations = validation.get("violations", [])
                        if violations:
                            changes.append(
                                f"규칙 위반 감지: {', '.join(violations[:3])}"
                            )
                    missing_rules = validation.get("missing_rules_hint", [])
                    if missing_rules:
                        changes.append(
                            f"추가 검증 필요 규칙: {', '.join(missing_rules[:3])}"
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Pipeline validation skipped: %s", exc)
            answer = postprocess_answer(answer, query_type)
            if reference_text and query_type in {
                "target_short",
                "target_long",
                "reasoning",
            }:
                answer = _dedup_with_reference(answer, reference_text, query_type)

            answer = _sanitize_output(answer)
            # 통합 검증: 위반 시 재작성 시도
            val_result = unified_validator.validate_all(answer, normalized_qtype)
            if val_result.has_errors() or val_result.warnings:
                edit_request_parts: list[str] = []
                if val_result.has_errors():
                    edit_request_parts.append(val_result.get_error_summary())
                if val_result.warnings:
                    edit_request_parts.extend(val_result.warnings[:2])
                edit_request = "; ".join(
                    [p for p in edit_request_parts if p] or ["형식/규칙 위반 수정"]
                )
                try:
                    answer = await current_agent.rewrite_best_answer(
                        ocr_text=ocr_text,
                        best_answer=answer,
                        edit_request=edit_request,
                        cached_content=None,
                        constraints=answer_constraints,
                        length_constraint=length_constraint,
                    )
                    answer = strip_output_tags(answer)
                    answer = postprocess_answer(answer, query_type)
                    if reference_text and query_type in {
                        "target_short",
                        "target_long",
                        "reasoning",
                    }:
                        answer = _dedup_with_reference(
                            answer, reference_text, query_type
                        )
                    answer = _sanitize_output(answer)
                    changes.append("검증 기반 재작성 완료")
                except Exception as exc:  # noqa: BLE001
                    logger.debug("재작성 실패, 기존 답변 유지: %s", exc)
            if val_result.has_errors():
                changes.append(val_result.get_error_summary())
            if val_result.warnings:
                changes.extend(val_result.warnings)

        return {
            "workflow": workflow,
            "query": query,
            "answer": answer,
            "changes": changes,
            "query_type": query_type,
        }

    try:
        result = await asyncio.wait_for(
            _execute_workflow(), timeout=config.workspace_unified_timeout
        )
        duration = (datetime.now() - meta_start).total_seconds()
        meta = APIMetadata(duration=duration)
        return cast(
            Dict[str, Any], build_response(result, metadata=meta, config=config)
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"워크플로우 시간 초과 ({config.workspace_unified_timeout}초). 다시 시도해주세요.",
        )
    except Exception as e:
        logger.error("워크플로우 실행 실패: %s", e)
        raise HTTPException(status_code=500, detail=f"실행 실패: {str(e)}")


__all__ = [
    "api_generate_answer_from_query",
    "api_generate_query_from_answer",
    "api_unified_workspace",
    "api_workspace",
    "router",
    "set_dependencies",
]
