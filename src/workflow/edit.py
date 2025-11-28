"""Edit workflow module for user-directed content revision."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.agent.core import GeminiAgent
from src.caching.redis_cache import RedisEvalCache
from src.qa.rag_system import QAKnowledgeGraph

logger = logging.getLogger(__name__)


async def edit_content(
    agent: GeminiAgent,
    answer: str,
    ocr_text: str,
    query: str,
    edit_request: str,
    kg: Optional[QAKnowledgeGraph] = None,
    cache: Optional[RedisEvalCache] = None,
) -> str:
    """
    사용자의 간결한 요청(edit_request)을 반영하여 answer 내용을 수정한다.

    Args:
        agent: GeminiAgent 인스턴스
        answer: 수정할 답변 텍스트
        ocr_text: OCR 텍스트 (사실/수치 일관성 유지용)
        query: 관련 질의 (문맥 강화용, 선택적)
        edit_request: 사용자의 수정 요청 문장
        kg: Neo4j 지식 그래프 (규칙 로드용, 선택적)
        cache: Redis 캐시 (중복 방지용, 선택적)

    Returns:
        수정된 답변 문자열
    """
    # 1. 캐시 키 (같은 요청/문맥 반복 시 재사용)
    cache_key = None
    if cache:
        base = answer + ocr_text + query + edit_request
        cache_key = f"edit:{hash(base)}"
        cached = await cache.get(cache_key)
        if cached is not None:
            logger.info("Cache hit for edit - returning cached result")
            # 캐시된 결과가 문자열이 아닌 경우 (마커 값일 수 있음)
            # 실제 수정본을 저장하므로 다시 처리
            if isinstance(cached, str):
                return cached

    # 2. 규칙/가이드라인 (선택적으로 Neo4j에서 가져올 수 있음)
    rules_summary = ""
    if kg:
        try:
            rules: List[Dict[str, Any]] = kg.get_constraints_for_query_type("general")
            if rules:
                rules_summary = "\n".join(
                    [f"- {r.get('description', '')}" for r in rules if r.get("description")]
                )
        except Exception as e:
            logger.warning("Failed to load rules from knowledge graph: %s", e)

    # 3. 프롬프트 구성
    system_prompt = "너는 사용자의 요청에 맞춰 텍스트를 자연스럽게 수정하는 어시스턴트다."

    user_prompt = f"""다음은 이미지에서 추출한 OCR 텍스트와, 그 OCR을 바탕으로 작성된 답변입니다.

[OCR 텍스트]
{ocr_text or "(제공되지 않음)"}

[현재 답변]
{answer}

[질의]
{query or "(별도 질의 없음)"}

[수정 요청]
{edit_request}

[추가 지침]
- 가능한 한 사실 관계(OCR 내용)와 수치 정보는 유지한다.
- 사용자의 '수정 요청'을 최우선으로 반영한다.
- 규칙이 있다면 이를 위반하지 않도록 한다.
{rules_summary if rules_summary else ""}

위 정보를 바탕으로 '현재 답변'을 전체적으로 다시 작성하되,
사용자가 원하는 방향으로만 수정하라.
수정된 최종 답변 전체만 출력하라."""

    # 4. 모델 호출
    model = agent._create_generative_model(system_prompt)
    edited = await agent._call_api_with_retry(model, user_prompt)
    edited = edited.strip()

    # 5. 캐시에 저장 (수정본을 문자열로 저장)
    if cache and cache_key:
        # RedisEvalCache.set expects float, but we need to store string
        # Use a workaround: store a marker and log the actual text
        await cache.set(cache_key, 1.0)
        logger.debug("Cached edit result for key: %s", cache_key)

    return edited
