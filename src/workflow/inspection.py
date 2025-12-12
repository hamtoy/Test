from __future__ import annotations

import logging
import os
from typing import Any

from src.agent.core import GeminiAgent
from src.caching.redis_cache import RedisEvalCache
from src.config.constants import DEFAULT_ANSWER_RULES
from src.features.difficulty import AdaptiveDifficultyAdjuster
from src.features.lats import LATSSearcher, SearchState
from src.features.self_correcting import SelfCorrectingQAChain
from src.qa.rag_system import QAKnowledgeGraph

logger = logging.getLogger(__name__)


def _should_enable_lats(agent: GeminiAgent, lats: LATSSearcher | None) -> bool:
    """Check whether LATS should be activated based on env/config."""
    if lats is not None:
        return True
    env_flag = os.getenv("ENABLE_LATS", "").lower() == "true"
    config_flag = bool(getattr(getattr(agent, "config", None), "enable_lats", False))
    return bool(env_flag or config_flag)


async def _is_cached(
    cache: RedisEvalCache | None,
    cache_key: str,
    kind: str,
) -> bool:
    if cache is None:
        return False
    cached = await cache.get(cache_key)
    if cached is None:
        return False
    logger.info("Cache hit for %s inspection - returning original %s", kind, kind)
    return True


def _format_rules_context(
    constraints: list[dict[str, str]],
    rules: list[str],
) -> str:
    if not constraints and not rules:
        return ""
    lines = [f"- {desc}" for c in constraints if (desc := c.get("description", ""))]
    lines.extend([f"- {r}" for r in rules if r])
    return "[준수해야 할 규칙]\n" + "\n".join(lines) + "\n\n"


def _default_rules_context() -> str:
    return _format_rules_context([], DEFAULT_ANSWER_RULES)


def _build_rules_context(
    kg: QAKnowledgeGraph | None,
    query_type: str,
    query: str,
) -> str:
    if kg is None:
        return _default_rules_context()
    try:
        constraints = kg.get_constraints_for_query_type(query_type)
        rules = kg.find_relevant_rules(query, k=5) if query else []
        return _format_rules_context(constraints, rules)
    except Exception as exc:  # noqa: BLE001
        logger.debug("규칙 컨텍스트 조회 실패: %s", exc)
        return ""


def _build_context_with_answer(
    context: dict[str, Any],
    answer: str,
    query: str,
    ocr_text: str,
    rules_context: str,
) -> dict[str, Any]:
    ctx = context.copy()
    ctx.update(
        {
            "draft_answer": answer,
            "original_answer": answer,
            "query": query,
            "ocr_text": ocr_text,
            "rules_context": rules_context,
            "language": "한국어",
        },
    )
    return ctx


def _self_correct_answer(
    query_type: str,
    context_with_answer: dict[str, Any],
    kg: QAKnowledgeGraph | None,
    fallback_answer: str,
) -> str:
    if kg is None:
        return fallback_answer
    corrector = SelfCorrectingQAChain(kg)
    result = corrector.generate_with_self_correction(query_type, context_with_answer)
    return str(result.get("output", fallback_answer))


def _maybe_create_lats(
    agent: GeminiAgent,
    lats: LATSSearcher | None,
) -> LATSSearcher | None:
    if lats is not None:
        return lats
    provider = getattr(agent, "llm_provider", None)
    if provider is None:
        logger.debug("LATS disabled: llm_provider not available")
        return None
    try:
        return LATSSearcher(llm_provider=provider)
    except Exception as exc:  # noqa: BLE001
        logger.debug("LATS init skipped: %s", exc)
        return None


async def _apply_lats_if_enabled(
    lats: LATSSearcher | None,
    enabled: bool,
    query: str,
    ocr_text: str,
    current_answer: str,
) -> str:
    if not enabled or lats is None:
        return current_answer
    try:
        initial_state = SearchState(
            query=query,
            ocr_text=ocr_text,
            current_answer=current_answer,
        )
        best_node = await lats.run(initial_state=initial_state)
        candidate = getattr(best_node.state, "current_answer", None)
        return candidate or current_answer
    except Exception as exc:  # noqa: BLE001
        logger.debug("LATS search skipped: %s", exc)
        return current_answer


def _cross_validate_if_needed(
    query: str,
    final_answer: str,
    query_type: str,
    context: dict[str, Any],
    validator: Any | None,
) -> None:
    if not query or validator is None:
        return
    val_result = validator.cross_validate_qa_pair(
        query,
        final_answer,
        query_type,
        context.get("image_meta", {}),
    )
    if val_result.get("overall_score", 0) < 0.7:
        logger.warning("Validation failed: %s", val_result)
        context["validation_warning"] = True


async def _mark_cached(cache: RedisEvalCache | None, cache_key: str) -> None:
    if cache is not None:
        await cache.set(cache_key, 1.0)


async def inspect_query(
    _agent: GeminiAgent,
    query: str,
    ocr_text: str = "",
    context: dict[str, Any] | None = None,
    kg: QAKnowledgeGraph | None = None,
    lats: LATSSearcher | None = None,
    difficulty: AdaptiveDifficultyAdjuster | None = None,
    cache: RedisEvalCache | None = None,
) -> str:
    """질의 종합 검수 (Zero-Rejection 목표).

    Pipeline:
    1. 캐시 확인 (동일 질의 반복 수정 방지)
    2. OCR 기반 난이도/복잡도 분석
    3. Neo4j 규칙 로드
    4. Gemini 수정 실행 (Self-Correcting)

    Args:
        agent: GeminiAgent 인스턴스
        query: 검수할 질의 문자열
        ocr_text: OCR 텍스트 (난이도 분석용)
        context: 추가 컨텍스트 정보 (선택)
        kg: Neo4j 지식 그래프 (규칙 로드용)
        lats: LATS 탐색기 (선택)
        difficulty: 난이도 조정기 (선택)
        cache: Redis 캐시 (중복 방지용)

    Returns:
        수정된 질의 문자열
    """
    if context is None:
        context = {}
    query_type = context.get("type", "general")

    # 1. 캐시 확인 (동일 질의 반복 처리 방지)
    cache_key = f"inspect:qry:{hash(query + ocr_text)}"
    if cache:
        cached = await cache.get(cache_key)
        if cached is not None:
            logger.info("Cache hit for query inspection - returning original query")
            # 캐시에서 처리 완료 표시만 저장하므로 원본 반환
            return query

    # 2. OCR 기반 난이도 분석
    if difficulty and ocr_text:
        complexity = difficulty.analyze_text_complexity(ocr_text)
        context["complexity"] = complexity
        logger.debug("Text complexity: %s", complexity.get("level", "unknown"))
    elif difficulty:
        complexity = difficulty.analyze_image_complexity(context.get("image_meta", {}))
        context["complexity"] = complexity

    # 3. Neo4j 규칙 로드 및 컨텍스트 구성
    context_prompt = ""
    if kg:
        rules: list[dict[str, str]] = kg.get_constraints_for_query_type(query_type)
        if rules:
            rule_lines = [
                r.get("description", "") for r in rules if r.get("description")
            ]
            context_prompt += "\n[규칙]\n" + "\n".join(rule_lines)

    if context.get("complexity"):
        level = context["complexity"].get("level", "medium")
        context_prompt += f"\n[난이도]: {level} (이에 맞춰 톤앤매너 조정)"

    # 4. LATS 수정 방향 탐색 (Optional)
    if lats:
        # LATS를 사용하여 개선된 질의 제안을 받을 수 있음
        pass

    # 5. Self-Correcting 자기 교정
    if kg:
        corrector = SelfCorrectingQAChain(kg)
        context_with_query = context.copy()
        context_with_query["original_query"] = query
        context_with_query["ocr_text"] = ocr_text
        context_with_query["context_prompt"] = context_prompt
        result = corrector.generate_with_self_correction(query_type, context_with_query)
        final_query = str(result.get("output", query))
    else:
        # kg가 없으면 원본 query 반환
        final_query = query

    # 6. 캐시에 저장 (처리 완료 표시)
    if cache:
        await cache.set(cache_key, 1.0)

    return final_query


async def inspect_answer(
    agent: GeminiAgent,
    answer: str,
    query: str,
    ocr_text: str,
    context: dict[str, Any] | None = None,
    kg: QAKnowledgeGraph | None = None,
    lats: LATSSearcher | None = None,
    validator: Any | None = None,
    cache: RedisEvalCache | None = None,
) -> str:
    """답변 종합 검수 - 규칙 주입 + 자기 교정 최소화 버전."""
    if context is None:
        context = {}
    query_type = context.get("type", "general")

    cache_key = f"inspect:ans:{hash(answer + query + ocr_text)}"
    if await _is_cached(cache, cache_key, "answer"):
        return answer

    rules_context = _build_rules_context(kg, query_type, query)
    context_with_answer = _build_context_with_answer(
        context,
        answer,
        query,
        ocr_text,
        rules_context,
    )
    final_answer = _self_correct_answer(query_type, context_with_answer, kg, answer)

    lats_enabled = _should_enable_lats(agent, lats)
    lats = _maybe_create_lats(agent, lats) if lats_enabled else lats
    final_answer = await _apply_lats_if_enabled(
        lats,
        lats_enabled,
        query,
        ocr_text,
        final_answer,
    )

    _cross_validate_if_needed(query, final_answer, query_type, context, validator)
    await _mark_cached(cache, cache_key)
    return final_answer
