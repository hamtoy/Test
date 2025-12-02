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
    """외부에서 제공된 3개의 답변을 비교 평가한다 - 1~6점 척도, 동점 금지.

    Args:
        agent: GeminiAgent 인스턴스
        ocr_text: OCR 텍스트 (사실 검증 기준)
        query: 질의 내용
        answers: 평가할 답변 3개 리스트 (A, B, C 순서)

    Returns:
        각 답변의 평가 결과 리스트
    """
    if len(answers) != 3:
        raise ValueError("answers 리스트는 정확히 3개여야 합니다.")

    # 평가 기준 프롬프트 - 1~6점 척도 (7점 금지), 동점 금지
    system_prompt = """너는 텍스트-이미지 QA 시스템의 답변 품질을 평가하는 전문가다.

[핵심 원칙]
- Zero Trust: AI 생성 답변은 기본적으로 '결함이 있다'고 전제한다.
- 반드시 한국어로 응답하라.
- 점수 범위: 1~6점만 사용한다. 7점(만점)은 금지이며, 리라이팅 없이 만점을 주면 어뷰징으로 간주한다.
- **동점 금지**: A, B, C에 서로 다른 점수를 부여하라. 순위를 명확히 매겨라.
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

    user_prompt = f"""[OCR 텍스트]
{ocr_text or "(제공되지 않음)"}

[질의]
{query}

[답변 A]
{answers[0]}

[답변 B]
{answers[1]}

[답변 C]
{answers[2]}

위 3개 답변을 비교하여 1-6점 척도로 상대평가하라.
**중요: 동점 금지. 반드시 A, B, C에 서로 다른 점수를 부여하라.**

반드시 다음 형식으로만 응답하라:
A점수: [1-6 사이 정수]
A피드백: [한 줄 평가]
B점수: [1-6 사이 정수]
B피드백: [한 줄 평가]
C점수: [1-6 사이 정수]
C피드백: [한 줄 평가]"""

    try:
        model = agent._create_generative_model(system_prompt)
        response = await agent._call_api_with_retry(model, user_prompt)
        response = response.strip()

        scores: Dict[str, int] = {"A": 3, "B": 3, "C": 3}
        feedbacks: Dict[str, str] = {"A": "", "B": "", "C": ""}

        for raw_line in response.split("\n"):
            line = raw_line.strip()
            for cid in ("A", "B", "C"):
                if line.startswith(f"{cid}점수:"):
                    try:
                        score_val = int(line.split(":", 1)[1].strip())
                        scores[cid] = max(1, min(6, score_val))
                    except ValueError:
                        continue
                elif line.startswith(f"{cid}피드백:"):
                    feedbacks[cid] = line.split(":", 1)[1].strip()

        # 동점 해소: 높은 점수부터 사용, 중복이면 -1씩 조정
        adjusted_scores: Dict[str, int] = {}
        used_scores: set[int] = set()
        for cid, score in sorted(
            scores.items(), key=lambda item: item[1], reverse=True
        ):
            while score in used_scores and score > 1:
                score -= 1
            used_scores.add(score)
            adjusted_scores[cid] = score

        return [
            {
                "candidate_id": cid,
                "score": adjusted_scores[cid],
                "feedback": feedbacks[cid] or response,
            }
            for cid in ("A", "B", "C")
        ]
    except Exception as exc:  # noqa: BLE001
        logger.error("비교 평가 실패: %s", exc)
        return [
            {"candidate_id": "A", "score": 3, "feedback": f"평가 실패: {exc}"},
            {"candidate_id": "B", "score": 2, "feedback": f"평가 실패: {exc}"},
            {"candidate_id": "C", "score": 1, "feedback": f"평가 실패: {exc}"},
        ]
