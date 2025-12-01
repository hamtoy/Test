"""외부 답변 평가 워크플로우"""

from __future__ import annotations

import asyncio
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
    """외부에서 제공된 3개의 답변을 평가한다 - 1~6점 척도, 병렬 처리.

    Args:
        agent: GeminiAgent 인스턴스
        ocr_text: OCR 텍스트 (사실 검증 기준)
        query: 질의 내용
        answers: 평가할 답변 3개 리스트

    Returns:
        각 답변의 평가 결과 리스트
    """
    results: List[Dict[str, Any]] = []

    # 평가 기준 프롬프트 - 1~6점 척도 (7점 금지)
    system_prompt = """너는 텍스트-이미지 QA 시스템의 답변 품질을 평가하는 전문가다.

[핵심 원칙]
- Zero Trust: AI 생성 답변은 기본적으로 '결함이 있다'고 전제한다.
- 반드시 한국어로 응답하라.
- 점수 범위: 1~6점만 사용한다. 7점(만점)은 금지이며, 리라이팅 없이 만점을 주면 어뷰징으로 간주한다.
- 상대평가: 동점을 피하고, 답변이 동일할 때만 같은 점수를 준다.
- 우선순위: 유용성 > 사실성 > 안전성 > 문법성 > 규칙 준수

[점수 기준]
1점: 완전히 잘못됨 - OCR 내용과 무관하거나 심각한 사실 오류
2점: 매우 부족 - 핵심 정보 누락, 정확성 낮음
3점: 부족 - 일부 정보만 포함, 오류 있음
4점: 보통 - 기본 내용은 맞으나 불완전함
5점: 양호 - 대부분 정확하고 질의에 적절히 답변함
6점: 우수 - 정확하고 완전하나, 리라이팅 필요 (6점이 외부 답변 최고점)

[감점 요인]
- 시의성 표현 누락 (현재, 최근 등)
- 단위 오류 ($, % 등)
- 서술어 과도한 반복
- 표/그래프/차트 직접 언급
- OCR에 없는 외부 정보 추가"""

    candidate_ids = ["A", "B", "C"]

    for idx, answer in enumerate(answers):
        candidate_id = candidate_ids[idx]

        user_prompt = f"""[OCR 텍스트]
{ocr_text or "(제공되지 않음)"}

[질의]
{query}

[답변 {candidate_id}]
{answer}

위 답변을 1-6점 척도로 상대평가하라. (7점 부여 금지)
반드시 한국어로 다음 형식으로만 응답하라:
점수: [1-6 사이 정수]
피드백: [한 줄 평가 요약]"""

    async def evaluate_single(idx: int, answer: str) -> Dict[str, Any]:
        candidate_id = candidate_ids[idx]
        try:
            model = agent._create_generative_model(system_prompt)
            response = await agent._call_api_with_retry(model, user_prompt)
            response = response.strip()

            # 응답 파싱
            score = 3  # 기본값 (부족)
            feedback = response

            for line in response.split("\n"):
                line_stripped = line.strip()
                if line_stripped.startswith("점수:"):
                    try:
                        score_str = line_stripped.replace("점수:", "").strip()
                        score = int(score_str)
                        # 1-6 범위 제한 (7점 금지)
                        score = max(1, min(6, score))
                    except ValueError:
                        pass
                elif line_stripped.startswith("피드백:"):
                    feedback = line_stripped.replace("피드백:", "").strip()

            return {
                "candidate_id": candidate_id,
                "score": score,
                "feedback": feedback,
            }

        except Exception as e:
            logger.error(f"답변 {candidate_id} 평가 실패: {e}")
            return {
                "candidate_id": candidate_id,
                "score": 1,  # 실패 시 최저점
                "feedback": f"평가 실패: {str(e)}",
            }

    tasks = [evaluate_single(idx, answer) for idx, answer in enumerate(answers)]
    results = await asyncio.gather(*tasks)

    return list(results)
