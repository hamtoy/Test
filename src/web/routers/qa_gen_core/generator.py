"""QA 생성 핵심 오케스트레이션 모듈."""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, cast

from src.config.constants import (
    DEFAULT_ANSWER_RULES,
    ESTIMATED_CACHE_HIT_TIME_SAVINGS,
    QA_CACHE_OCR_TRUNCATE_LENGTH,
    QA_GENERATION_OCR_TRUNCATE_LENGTH,
)
from src.config.exceptions import SafetyFilterError
from src.qa.rule_loader import RuleLoader
from src.qa.validator import UnifiedValidator
from src.web.semantic_cache import semantic_answer_cache
from src.web.utils import postprocess_answer, render_structured_answer_if_present

from ..qa_common import (
    _difficulty_hint,
    _get_kg,
    _get_pipeline,
    _get_validator_class,
    get_cached_kg,
    logger,
)
from .constraints import (
    build_constraints_text,
    load_constraints_from_kg,
    validate_constraint_conflicts,
)
from .prompts import (
    build_answer_prompt,
    build_extra_instructions,
    build_formatting_text,
    build_length_constraint,
    build_priority_hierarchy,
)
from .types import get_query_intent, normalize_qtype
from .validation import validate_and_regenerate, validate_answer_length


def _remove_parentheses_from_query(query: str) -> str:
    """질의에서 괄호와 괄호 안 내용을 제거.

    Rule: 모든 질의 유형에서 괄호() 사용 금지.

    Args:
        query: 원본 질의

    Returns:
        괄호가 제거된 질의
    """
    # Remove content within parentheses (including nested)
    # Pattern: 괄호와 그 안의 내용 제거
    cleaned = re.sub(r"\([^)]*\)", "", query)

    # Clean up extra spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Log if parentheses were removed
    if cleaned != query:
        logging.getLogger(__name__).info(
            "질의 괄호 제거: '%s' -> '%s'",
            query[:100],
            cleaned[:100],
        )

    return cleaned


async def generate_single_qa(
    agent: Any,
    ocr_text: str,
    qtype: str,
    previous_queries: list[str] | None = None,
    explanation_answer: str | None = None,
) -> dict[str, Any]:
    """단일 QA 생성 - 규칙 적용 보장 + 호출 최소화.

    Args:
        agent: GeminiAgent 인스턴스
        ocr_text: OCR 텍스트
        qtype: Query type
        previous_queries: 이전 질의 목록 (중복 방지용)
        explanation_answer: 설명문 답변 (target 타입에서 제외할 내용)

    Returns:
        생성된 QA pair dict (type, query, answer)
    """
    current_kg = _get_kg()
    current_pipeline = _get_pipeline()
    kg_wrapper = get_cached_kg()

    # Phase 1: Normalize query type
    normalized_qtype = normalize_qtype(qtype)
    logger.info(
        "Query type '%s' normalized to '%s' for rule loading",
        qtype,
        normalized_qtype,
    )

    # Phase 2: Get query intent (설명문 답변 전달하여 중복 방지)
    query_intent = get_query_intent(qtype, previous_queries, explanation_answer)

    # Phase 3: Load constraints from KG
    constraint_set = load_constraints_from_kg(kg_wrapper, normalized_qtype)

    # Load rules list
    rule_loader = RuleLoader(current_kg)
    rules_list = rule_loader.get_rules_for_type(normalized_qtype, DEFAULT_ANSWER_RULES)
    if not rules_list:
        rules_list = list(DEFAULT_ANSWER_RULES)
        logger.info("Neo4j 규칙 없음, 기본 규칙 사용")

    # Limit rules for target types
    if qtype == "target_short":
        rules_list = rules_list[:3]
    elif qtype == "target_long":
        rules_list = rules_list[:5]

    # Phase 4: Build prompts
    length_constraint, max_chars = build_length_constraint(
        qtype, len(ocr_text), ocr_text
    )
    extra_instructions = build_extra_instructions(qtype, normalized_qtype, current_kg)
    formatting_text = build_formatting_text(
        constraint_set.formatting_rules,
        normalized_qtype,
    )

    # Validate constraint conflicts
    validate_constraint_conflicts(
        constraint_set.answer_constraints,
        length_constraint,
        normalized_qtype,
    )

    # Phase 5: Create unified validator
    unified_validator = UnifiedValidator(current_kg, current_pipeline)

    # PHASE 2B: Check cache before expensive operations
    cache_ocr_key = ocr_text[:QA_CACHE_OCR_TRUNCATE_LENGTH]

    try:
        # Generate query
        queries = await agent.generate_query(
            ocr_text,
            user_intent=query_intent,
            query_type=qtype,
            kg=kg_wrapper or current_kg,
            constraints=constraint_set.query_constraints,
        )
        if not queries:
            raise ValueError("질의 생성 실패")

        query = queries[0]

        # Postprocess query: Remove parentheses and their content
        # Rule: 모든 질의에서 괄호() 사용 금지
        query = _remove_parentheses_from_query(query)

        # PHASE 2B: Cache key logging (normalized for hit rate improvement)
        normalized_query = query.lower()
        normalized_query = " ".join(normalized_query.split())
        normalized_query = normalized_query.rstrip("?.!。？！")
        ocr_hash = hashlib.sha256(cache_ocr_key.encode()).hexdigest()[:16]
        cache_key_hash = hashlib.sha256(
            f"{normalized_query}|{ocr_hash}|{qtype}".encode(),
        ).hexdigest()[:16]
        logger.info(
            "Cache Key Generated - Query: %s... | OCR hash: %s | Type: %s | Key: %s",
            normalized_query[:30],
            ocr_hash,
            qtype,
            cache_key_hash,
        )

        # Check cache after query generation
        cached_result = await semantic_answer_cache.get(query, cache_ocr_key, qtype)
        if cached_result is not None:
            cache_stats = semantic_answer_cache.get_stats()
            logger.info(
                "✅ CACHE HIT! Saved ~%d seconds. Query: %s... | Cache size: %d | Hit rate: %.1f%%",
                ESTIMATED_CACHE_HIT_TIME_SAVINGS,
                query[:50],
                cache_stats["cache_size"],
                cache_stats["hit_rate_percent"],
            )
            return cast("dict[str, Any]", cached_result)

        cache_stats = semantic_answer_cache.get_stats()
        logger.info(
            "❌ CACHE MISS - Will generate new answer. Cache size: %d | Hit rate: %.1f%%",
            cache_stats["cache_size"],
            cache_stats["hit_rate_percent"],
        )

        # Phase 6: Build answer prompt
        truncated_ocr = ocr_text[:QA_GENERATION_OCR_TRUNCATE_LENGTH]
        rules_in_answer = "\n".join(f"- {r}" for r in rules_list)
        constraints_text = build_constraints_text(constraint_set.answer_constraints)
        difficulty_text = _difficulty_hint(ocr_text)

        priority_hierarchy = build_priority_hierarchy(
            normalized_qtype,
            length_constraint,
            formatting_text,
        )

        answer_prompt = build_answer_prompt(
            query=query,
            truncated_ocr=truncated_ocr,
            constraints_text=constraints_text,
            rules_in_answer=rules_in_answer,
            priority_hierarchy=priority_hierarchy,
            length_constraint=length_constraint,
            formatting_text=formatting_text,
            difficulty_text=difficulty_text,
            extra_instructions=extra_instructions,
        )

        # Phase 7: Generate answer
        draft_answer = await agent.rewrite_best_answer(
            ocr_text=ocr_text,
            best_answer=answer_prompt,
            cached_content=None,
            query_type=normalized_qtype,
            kg=kg_wrapper or current_kg,
            constraints=constraint_set.answer_constraints,
            length_constraint=length_constraint,
        )
        if not draft_answer:
            raise SafetyFilterError("No text content in response.")

        # Structured(JSON) output is rendered to markdown before validation to avoid
        # validators interpreting JSON punctuation/quotes as sentence/format issues.
        draft_answer = render_structured_answer_if_present(draft_answer, qtype)

        # Enhanced logging for answer length debugging
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Answer length tracking - qtype=%s, OCR=%d chars, draft=%d chars",
                qtype,
                len(ocr_text),
                len(draft_answer),
            )

        # Phase 8: Validate and regenerate if needed
        validated_answer = await validate_and_regenerate(
            agent=agent,
            draft_answer=draft_answer,
            qtype=qtype,
            normalized_qtype=normalized_qtype,
            query=query,
            unified_validator=unified_validator,
            answer_constraints=constraint_set.answer_constraints,
            length_constraint=length_constraint,
            ocr_text=ocr_text,
            kg_wrapper=kg_wrapper,
            pipeline=current_pipeline,
            validator_class=_get_validator_class(),
        )

        # Phase 9: Post-process answer
        final_answer = postprocess_answer(validated_answer, qtype, max_length=max_chars)

        # Log length changes through post-processing
        if normalized_qtype == "explanation":
            logger.info(
                "Answer length - OCR: %d chars | Draft: %d chars | Final: %d chars | Query: %s",
                len(ocr_text),
                len(draft_answer),
                len(final_answer),
                query[:50],
            )

        # Validate answer length
        validate_answer_length(final_answer, normalized_qtype, ocr_text, query)

        # Phase 10: Cache result
        result = {"type": qtype, "query": query, "answer": final_answer}
        await semantic_answer_cache.set(query, cache_ocr_key, qtype, result)
        logger.debug("Cached answer for query_type=%s", qtype)

        return result
    except Exception as e:
        logger.error("QA 생성 실패: %s", e)
        raise
