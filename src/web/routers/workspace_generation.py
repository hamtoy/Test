"""워크스페이스 질의/답변 생성 엔드포인트.

웹앱 사용 여부: ❌ 웹 프론트엔드 미사용 (API 전용)

- 엔드포인트:
  - POST /api/workspace/generate-answer (질문 기반 답변 생성)
  - POST /api/workspace/generate-query (답변 기반 질문 생성)
- 용도: 직접 API 호출용 엔드포인트 (웹 UI는 /api/workspace/unified 사용)
- 상태: 테스트 코드 존재, 웹 프론트엔드에서는 호출하지 않음
- 참고: workspace_unified.py가 이 기능들을 통합하여 제공
"""
# mypy: ignore-errors

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from fastapi import APIRouter, HTTPException

from checks.detect_forbidden_patterns import find_violations
from src.config.constants import DEFAULT_ANSWER_RULES
from src.qa.rule_loader import RuleLoader
from src.web.response import APIMetadata, build_response
from src.web.utils import QTYPE_MAP, load_ocr_text, strip_output_tags

from .workspace_common import (
    DEFAULT_LATS_WEIGHTS,
    LATS_WEIGHTS_PRESETS,
    MAX_REWRITE_ATTEMPTS,
    AnswerQualityWeights,
    _get_agent,
    _get_config,
    _get_kg,
)

if TYPE_CHECKING:
    from src.features.lats import SearchNode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["workspace-generation"])

_NUMBER_REGEX = r"\d+(?:\.\d+)?"


def _score_length(
    text: str,
    weights: AnswerQualityWeights,
    failures: list[str],
) -> float:
    if weights.min_length <= len(text) <= weights.max_length:
        return weights.length_weight
    failures.append(f"length({len(text)})")
    return 0.0


def _score_numbers(
    answer: str,
    ocr_text: str,
    weights: AnswerQualityWeights,
    failures: list[str],
    *,
    score_details: dict[str, Any] | None = None,
) -> float:
    ocr_numbers = set(re.findall(_NUMBER_REGEX, ocr_text))
    answer_numbers = set(re.findall(_NUMBER_REGEX, answer))
    overlap = len(answer_numbers & ocr_numbers)

    if overlap >= weights.min_number_overlap and ocr_numbers:
        if score_details is not None:
            score_details["numbers"] = {
                "overlap": overlap,
                "total_ocr": len(ocr_numbers),
            }
        return weights.number_match_weight
    if not ocr_numbers:
        return weights.number_match_weight * 0.5

    failures.append(f"numbers({overlap}/{len(ocr_numbers)})")
    return 0.0


def _score_forbidden_patterns(
    answer: str,
    weights: AnswerQualityWeights,
    failures: list[str],
) -> float:
    forbidden_patterns = [r"^\s*[-*•]\s", r"\*\*", r"__"]
    has_forbidden = any(re.search(p, answer, re.MULTILINE) for p in forbidden_patterns)
    if has_forbidden:
        failures.append("forbidden_patterns")
        return 0.0
    return weights.no_forbidden_weight


def _score_constraints(
    weights: AnswerQualityWeights,
    failures: list[str],
) -> float:
    kg = _get_kg()
    if not kg or weights.constraint_weight <= 0:
        return 0.0
    try:
        return weights.constraint_weight * 0.8
    except Exception:
        failures.append("constraints")
        return 0.0


@router.post("/workspace/generate-answer")
async def api_generate_answer_from_query(body: dict[str, Any]) -> dict[str, Any]:
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

        # 검증 및 재시도 (최대 MAX_REWRITE_ATTEMPTS회)
        for attempt in range(MAX_REWRITE_ATTEMPTS):
            violations = find_violations(answer)
            if not violations:
                break

            if attempt < MAX_REWRITE_ATTEMPTS - 1:
                violation_types = ", ".join({v["type"] for v in violations})
                logger.warning(
                    "답변에 금지 패턴 발견 (시도 %d/%d): %s",
                    attempt + 1,
                    MAX_REWRITE_ATTEMPTS,
                    violation_types,
                )
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
            else:
                logger.error(
                    "최대 재시도 횟수 초과. 마지막 답변 반환 (violations: %d)",
                    len(violations),
                )

        duration = (datetime.now() - meta_start).total_seconds()
        meta = APIMetadata(duration=duration)
        return cast(
            "dict[str, Any]",
            build_response(
                {"query": query, "answer": answer},
                metadata=meta,
                config=config,
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
async def api_generate_query_from_answer(body: dict[str, Any]) -> dict[str, Any]:
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
            "dict[str, Any]",
            build_response(
                {"query": query, "answer": answer},
                metadata=meta,
                config=config,
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

    # 자동 가중치 선택 (실전 최적화)
    weights = LATS_WEIGHTS_PRESETS.get(query_type, DEFAULT_LATS_WEIGHTS)
    logger.info("LATS 실행: %s (weights: %s)", query_type, weights.__class__.__name__)

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

            if answer and len(answer) > weights.min_length:
                # 답변 평가
                score = await _evaluate_answer_quality(
                    answer,
                    ocr_text,
                    query_type,
                    weights,
                )

                if score >= 0.6:  # 품질 임계값 (실전 기준)
                    candidates.append(
                        {
                            "strategy": strategy["name"],
                            "answer": answer,
                            "score": score,
                        },
                    )
                    logger.info("✅ LATS 후보: %s (%.2f)", strategy["name"], score)
        except Exception as e:
            logger.debug("LATS 답변 생성 실패 (%s): %s", strategy["name"], e)
            continue

    if not candidates:
        logger.warning("LATS 모든 후보 저품질, 기본 답변 반환")
        return "", {"reason": "all_low_quality"}

    # 최고 점수 답변 선택
    best = max(candidates, key=lambda x: float(x["score"]))
    meta = {
        "query_type": query_type,
        "weights_used": vars(weights),
        "best_strategy": best["strategy"],
        "best_score": best["score"],
        "candidates": len(candidates),
        "avg_score": sum(c["score"] for c in candidates) / len(candidates),
    }

    return str(best["answer"]), meta


async def _evaluate_answer_quality(
    answer: str,
    ocr_text: str,
    query_type: str = "explanation",
    weights: AnswerQualityWeights | None = None,
) -> float:
    """실전용 고품질 답변 평가 (0.0-1.0)."""
    await asyncio.sleep(0)
    if not answer or len(answer) < 5:
        logger.debug("답변 너무 짧음: %d자", len(answer))
        return 0.0

    weights = weights or LATS_WEIGHTS_PRESETS.get(query_type, DEFAULT_LATS_WEIGHTS)

    failures: list[str] = []
    score_details = {"weights": vars(weights), "failures": failures}
    score = weights.base_score

    score += _score_length(answer, weights, failures)
    score += _score_numbers(
        answer,
        ocr_text,
        weights,
        failures,
        score_details=score_details,
    )
    score += _score_forbidden_patterns(answer, weights, failures)
    score += _score_constraints(weights, failures)

    final_score = min(1.0, max(0.0, score))

    # 로깅 (실전 디버깅용)
    if final_score < 0.7:  # 저품질 답변만 로깅
        logger.warning(
            "저품질 LATS 답변 (%.2f): %s, 실패: %s",
            final_score,
            query_type,
            ", ".join(failures),
        )

    logger.debug("LATS 점수: %.2f (%s)", final_score, score_details)
    return final_score


async def _lats_evaluate_answer(node: SearchNode) -> float:
    """LATS 평가: 생성된 답변의 품질을 0.0-1.0로 점수화."""
    await asyncio.sleep(0)
    # SearchState에서 필요한 정보 추출
    state = node.state
    current_answer = state.current_answer or ""
    ocr_text = state.ocr_text or ""

    # query_type 추출 (metadata나 query_type 필드 확인)
    query_type = "explanation"
    if hasattr(state, "metadata") and state.metadata:
        query_type = state.metadata.get("query_type", "explanation")
    elif hasattr(state, "query_type") and state.query_type:
        query_type = state.query_type

    if not current_answer:
        return 0.0

    # 가중치 적용
    weights = LATS_WEIGHTS_PRESETS.get(query_type, DEFAULT_LATS_WEIGHTS)

    score = weights.base_score
    failures: list[str] = []
    score += _score_length(current_answer, weights, failures)
    score += _score_numbers(current_answer, ocr_text, weights, failures)
    score += _score_forbidden_patterns(current_answer, weights, failures)
    score += _score_constraints(weights, failures)

    final_score = min(1.0, max(0.0, score))

    # 로깅 (10% 확률 또는 저품질일 때만)
    if final_score < 0.6:
        logger.debug("LATS Node 평가 (%.2f): %s", final_score, query_type)

    return final_score
