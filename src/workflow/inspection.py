from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.agent.core import GeminiAgent
from src.analysis.cross_validation import CrossValidationSystem
from src.analysis.semantic import count_keywords
from src.caching.redis_cache import RedisEvalCache
from src.config.constants import DEFAULT_ANSWER_RULES
from src.features.difficulty import AdaptiveDifficultyAdjuster
from src.features.lats import LATSSearcher
from src.features.self_correcting import SelfCorrectingQAChain
from src.qa.rag_system import QAKnowledgeGraph

logger = logging.getLogger(__name__)


async def inspect_query(
    agent: GeminiAgent,
    query: str,
    ocr_text: str = "",
    context: Optional[Dict[str, Any]] = None,
    kg: Optional[QAKnowledgeGraph] = None,
    lats: Optional[LATSSearcher] = None,
    difficulty: Optional[AdaptiveDifficultyAdjuster] = None,
    cache: Optional[RedisEvalCache] = None,
) -> str:
    """질의 종합 검수 (Zero-Rejection 목표)

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
        rules: List[Dict[str, str]] = kg.get_constraints_for_query_type(query_type)
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
    context: Optional[Dict[str, Any]] = None,
    kg: Optional[QAKnowledgeGraph] = None,
    lats: Optional[LATSSearcher] = None,
    validator: Optional[CrossValidationSystem] = None,
    cache: Optional[RedisEvalCache] = None,
) -> str:
    """답변 종합 검수 (Zero-Rejection 목표)

    Pipeline:
    1. 캐시 확인 (긴 답변 처리 비용 절감)
    2. Semantic 키워드 검증 (OCR 이탈 방지)
    3. Self-Correcting 자기 교정 (LATS 탐색)
    4. Cross-Validation 교차 검증

    Args:
        agent: GeminiAgent 인스턴스
        answer: 검수할 답변 문자열
        query: 관련 질의 (선택적이지만 교차검증에 사용)
        ocr_text: OCR 텍스트 (사실 검증용)
        context: 추가 컨텍스트 정보 (선택)
        kg: Neo4j 지식 그래프 (규칙 로드용)
        lats: LATS 탐색기 (최적 표현 탐색용)
        validator: 교차 검증 시스템 (신뢰도 강화용)
        cache: Redis 캐시 (비용 절감용)

    Returns:
        수정된 답변 문자열
    """
    if context is None:
        context = {}
    query_type = context.get("type", "general")

    # 1. 캐시 확인 (긴 답변 처리 비용 절감)
    cache_key = f"inspect:ans:{hash(answer + query + ocr_text)}"
    if cache:
        cached = await cache.get(cache_key)
        if cached is not None:
            logger.info("Cache hit for answer inspection - returning original answer")
            # 캐시에서 처리 완료 표시만 저장하므로 원본 반환
            return answer

    # 2. Semantic 키워드 검증 (OCR 이탈 방지)
    if ocr_text:
        ocr_keywords = count_keywords([ocr_text])
        answer_keywords = count_keywords([answer])

        total_ocr_keywords = sum(ocr_keywords.values())
        matched_keywords = 0
        for k, v in answer_keywords.items():
            if k in ocr_keywords:
                matched_keywords += v

        coverage = (
            matched_keywords / total_ocr_keywords if total_ocr_keywords > 0 else 1.0
        )
        if coverage < 0.6:
            logger.warning(f"Low keyword coverage: {coverage:.2f}")
            context["low_coverage"] = True
            context["coverage_score"] = coverage

    # [추가] 규칙 컨텍스트 조회 및 주입
    rules_context = ""
    if kg is not None:
        try:
            # 관련 규칙 조회
            rules = kg.find_relevant_rules(query, limit=5) if query else []
            constraints = kg.get_constraints_for_query_type(query_type)
            
            if rules or constraints:
                rules_context = "[준수해야 할 규칙]\n"
                if constraints:
                    rules_context += "\n".join(
                        f"- {c.get('description', '')}" 
                        for c in constraints 
                        if c.get('description')
                    )
                if rules:
                    rules_context += "\n" + "\n".join(
                        f"- {r.get('content', '')}" 
                        for r in rules 
                        if r.get('content')
                    )
                rules_context += "\n\n"
        except Exception as e:
            logger.debug(f"규칙 컨텍스트 조회 실패: {e}")
    else:
        # Neo4j 없을 때 기본 규칙 사용
        rules_context = "[준수해야 할 규칙]\n"
        rules_context += "\n".join(f"- {r}" for r in DEFAULT_ANSWER_RULES)
        rules_context += "\n\n"

    # 3. Self-Correcting 자기 교정 (LATS 내부 최적 경로 탐색)
    context_with_answer = context.copy()
    context_with_answer["draft_answer"] = answer
    context_with_answer["original_answer"] = answer
    context_with_answer["query"] = query
    context_with_answer["ocr_text"] = ocr_text
    context_with_answer["rules_context"] = rules_context

    if kg:
        corrector = SelfCorrectingQAChain(kg)
        result = corrector.generate_with_self_correction(
            query_type, context_with_answer
        )
        final_answer = str(result.get("output", answer))
    else:
        # kg가 없으면 원본 answer 반환
        final_answer = answer

    # 4. Cross-Validation 교차 검증 (질의 있을 시 신뢰도 강화)
    if query and validator:
        val_result = validator.cross_validate_qa_pair(
            query, final_answer, query_type, context.get("image_meta", {})
        )
        if val_result.get("overall_score", 0) < 0.7:
            logger.warning(f"Validation failed: {val_result}")
            context["validation_warning"] = True

    # 5. 캐시에 저장 (처리 완료 표시)
    if cache:
        await cache.set(cache_key, 1.0)

    return final_answer
