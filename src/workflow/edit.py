"""Edit workflow module for user-directed content revision."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.agent.core import GeminiAgent
from src.qa.rag_system import QAKnowledgeGraph

logger = logging.getLogger(__name__)


async def edit_content(
    agent: GeminiAgent,
    answer: str,
    ocr_text: str,
    query: str,
    edit_request: str,
    kg: Optional[QAKnowledgeGraph] = None,
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

    Returns:
        수정된 답변 문자열
    """
    # 1. 규칙/가이드라인 (선택적으로 Neo4j에서 가져올 수 있음)
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

    # 2. 프롬프트 구성
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

    # 3. 모델 호출
    model = agent._create_generative_model(system_prompt)
    edited = await agent._call_api_with_retry(model, user_prompt)
    edited = edited.strip()

    return edited
