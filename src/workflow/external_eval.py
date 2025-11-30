"""외부 답변 평가 워크플로우"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.agent.core import GeminiAgent

logger = logging.getLogger(__name__)


async def evaluate_external_answers(
    agent: GeminiAgent,
    ocr_text: str,
    query: str,
    answers: List[str],
) -> List[Dict[str, Any]]:
    """외부에서 제공된 3개의 답변을 평가한다.

    Args:
        agent: GeminiAgent 인스턴스
        ocr_text: OCR 텍스트 (사실 검증 기준)
        query: 질의 내용
        answers: 평가할 답변 3개 리스트

    Returns:
        각 답변의 평가 결과 리스트
    """
    results: List[Dict[str, Any]] = []

    # 평가 기준 프롬프트
    system_prompt = (
        "너는 텍스트-이미지 QA 시스템의 답변 품질을 평가하는 전문가다. "
        "OCR 텍스트와 질의를 기준으로 각 답변의 정확성, 완전성, 표현력을 평가한다."
    )

    candidate_ids = ["A", "B", "C"]

    for idx, answer in enumerate(answers):
        candidate_id = candidate_ids[idx]

        user_prompt = f"""[OCR 텍스트]
{ocr_text or "(제공되지 않음)"}

[질의]
{query}

[답변 {candidate_id}]
{answer}

위 답변을 다음 기준으로 평가하고 1-100점으로 점수를 매겨라:
1. 정확성: OCR 내용과 일치하는가?
2. 완전성: 질의에 충분히 답변했는가?
3. 표현력: 자연스럽고 읽기 쉬운가?

다음 형식으로만 응답하라:
점수: [숫자]
피드백: [한 줄 요약]"""

        try:
            model = agent._create_generative_model(system_prompt)
            response = await agent._call_api_with_retry(model, user_prompt)
            response = response.strip()

            # 응답 파싱
            score = 50  # 기본값
            feedback = response

            for line in response.split("\n"):
                line_stripped = line.strip()
                if line_stripped.startswith("점수:"):
                    try:
                        score_str = line_stripped.replace("점수:", "").strip()
                        score = int(score_str)
                        score = max(0, min(100, score))  # 0-100 범위 제한
                    except ValueError:
                        pass
                elif line_stripped.startswith("피드백:"):
                    feedback = line_stripped.replace("피드백:", "").strip()

            results.append(
                {
                    "candidate_id": candidate_id,
                    "score": score,
                    "feedback": feedback,
                }
            )

        except Exception as e:
            logger.error(f"답변 {candidate_id} 평가 실패: {e}")
            results.append(
                {
                    "candidate_id": candidate_id,
                    "score": 0,
                    "feedback": f"평가 실패: {str(e)}",
                }
            )

    return results
