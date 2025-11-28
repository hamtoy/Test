from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.agent.core import GeminiAgent
from src.analysis.cross_validation import CrossValidationSystem
from src.analysis.semantic import count_keywords
from src.features.difficulty import AdaptiveDifficultyAdjuster
from src.features.lats import LATSSearcher
from src.features.self_correcting import SelfCorrectingQAChain
from src.qa.rag_system import QAKnowledgeGraph

logger = logging.getLogger(__name__)


async def inspect_query(
    agent: GeminiAgent,
    query: str,
    context: Dict[str, Any],
    kg: Optional[QAKnowledgeGraph] = None,
    lats: Optional[LATSSearcher] = None,
    difficulty: Optional[AdaptiveDifficultyAdjuster] = None,
) -> str:
    """
    질의 종합 검수

    Pipeline:
    1. Difficulty 복잡도 분석
    2. LATS 수정 방향 탐색 (Optional)
    3. Self-Correcting 자기 교정
    """
    query_type = context.get("type", "general")

    # 1. Difficulty 복잡도 분석
    if difficulty:
        complexity = difficulty.analyze_image_complexity(context.get("image_meta", {}))
        context["complexity"] = complexity

    # 2. LATS 수정 방향 탐색 (Optional)
    if lats:
        # LATS를 사용하여 개선된 질의 제안을 받을 수 있음
        pass

    # 3. Self-Correcting 자기 교정
    if kg:
        corrector = SelfCorrectingQAChain(kg, agent.llm_provider)
        result = corrector.generate_with_self_correction(query_type, context)
        final_query = str(result.get("output", query))
    else:
        # kg가 없으면 원본 query 반환
        final_query = query

    return final_query


async def inspect_answer(
    agent: GeminiAgent,
    answer: str,
    query: str,
    ocr_text: str,
    context: Dict[str, Any],
    kg: Optional[QAKnowledgeGraph] = None,
    lats: Optional[LATSSearcher] = None,
    validator: Optional[CrossValidationSystem] = None,
) -> str:
    """
    답변 종합 검수

    Pipeline:
    1. Semantic 키워드 검증
    2. Self-Correcting 자기 교정
    3. Cross-Validation 교차 검증
    """
    query_type = context.get("type", "general")

    # 1. Semantic 키워드 검증
    ocr_keywords = count_keywords([ocr_text])
    answer_keywords = count_keywords([answer])

    total_ocr_keywords = sum(ocr_keywords.values())
    matched_keywords = 0
    for k, v in answer_keywords.items():
        if k in ocr_keywords:
            matched_keywords += v

    coverage = matched_keywords / total_ocr_keywords if total_ocr_keywords > 0 else 1.0
    if coverage < 0.6:
        logger.warning(f"Low keyword coverage: {coverage:.2f}")

    # 2. Self-Correcting 자기 교정
    context_with_answer = context.copy()
    context_with_answer["draft_answer"] = answer
    context_with_answer["query"] = query

    if kg:
        corrector = SelfCorrectingQAChain(kg, agent.llm_provider)
        result = corrector.generate_with_self_correction(
            query_type, context_with_answer
        )
        final_answer = str(result.get("output", answer))
    else:
        # kg가 없으면 원본 answer 반환
        final_answer = answer

    # 3. Cross-Validation 교차 검증
    if validator:
        val_result = validator.cross_validate_qa_pair(
            query, final_answer, query_type, context.get("image_meta", {})
        )
        if val_result.get("overall_score", 0) < 0.7:
            logger.warning(f"Validation failed: {val_result}")

    return final_answer
