"""
Real Gemini-based model client for QA pipeline.
Replaces stub implementations with actual API calls.
"""

from __future__ import annotations

import os
from typing import List, Dict, Any

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from dotenv import load_dotenv

load_dotenv()


def require_env(var: str) -> str:
    val = os.getenv(var)
    if not val:
        raise EnvironmentError(f"환경 변수 {var}가 설정되지 않았습니다 (.env 확인).")
    return val


class GeminiModelClient:
    """
    실제 Gemini API를 사용하는 모델 클라이언트.
    eval/rewrite/fact-check를 실제 모델 호출로 구현.
    """

    def __init__(self):
        api_key = require_env("GEMINI_API_KEY")
        genai.configure(api_key=api_key)

        model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-pro-002")
        self.model = genai.GenerativeModel(model_name)
        self.temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))

    def generate(self, prompt: str, role: str = "default") -> str:
        """프롬프트 기반 답변 생성."""
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=self.temperature,
                    max_output_tokens=2048,
                ),
            )
            return response.text
        except google_exceptions.GoogleAPIError as e:
            return f"[생성 실패: {e}]"
        except Exception as e:
            return f"[생성 실패(알 수 없음): {e}]"

    def evaluate(self, question: str, answers: List[str]) -> Dict[str, Any]:
        """답변 집합 평가 및 최고 답변 선택 (3개 미만도 처리)."""

        if not answers:
            return {
                "scores": [],
                "best_index": None,
                "best_answer": None,
                "notes": "평가 실패: 답변이 없습니다.",
            }

        if len(answers) < 3:
            scores = [len(a) for a in answers]
            best_idx = scores.index(max(scores))
            return {
                "scores": scores,
                "best_index": best_idx,
                "best_answer": answers[best_idx],
                "notes": f"3개 미만 답변({len(answers)})으로 길이 기반 선택",
            }
        eval_prompt = f"""다음 질문에 대한 3개의 답변을 평가하세요.

질문: {question}

답변 1:
{answers[0]}

답변 2:
{answers[1]}

답변 3:
{answers[2]}

평가 기준:
1. 정확성 (텍스트 기반, 추론 근거 명확)
2. 완전성 (질문에 충분히 답변)
3. 형식 준수 (마크다운, 표/그래프 미참조)

각 답변에 점수(1-10)를 부여하고, 최고 답변의 번호(1/2/3)를 반환하세요.

출력 형식:
점수1: [점수]
점수2: [점수]
점수3: [점수]
최고: [번호]
"""
        try:
            response = self.generate(eval_prompt, role="evaluator")
            # 간단한 파싱 (실제로는 더 정교한 파싱 필요)
            lines = response.strip().split("\n")
            scores = []
            best_idx = 0

            for line in lines:
                if line.startswith("점수"):
                    score = int(line.split(":")[-1].strip())
                    scores.append(score)
                elif line.startswith("최고"):
                    best_idx = int(line.split(":")[-1].strip()) - 1

            if not scores:
                scores = [len(a) for a in answers]  # Fallback
                best_idx = scores.index(max(scores))

            return {
                "scores": scores,
                "best_index": best_idx,
                "best_answer": answers[best_idx],
                "notes": response,
            }
        except google_exceptions.GoogleAPIError as e:
            scores = [len(a) for a in answers]
            best_idx = scores.index(max(scores))
            return {
                "scores": scores,
                "best_index": best_idx,
                "best_answer": answers[best_idx],
                "notes": f"평가 실패, 길이 기반 선택: {e}",
            }
        except Exception as e:
            scores = [len(a) for a in answers]
            best_idx = scores.index(max(scores))
            return {
                "scores": scores,
                "best_index": best_idx,
                "best_answer": answers[best_idx],
                "notes": f"평가 실패(알 수 없음), 길이 기반 선택: {e}",
            }

    def rewrite(self, text: str) -> str:
        """답변 재작성 (문장 재구성, 마크다운 적용)."""
        rewrite_prompt = f"""다음 답변을 개선하여 재작성하세요.

원본 답변:
{text}

재작성 요구사항:
1. 문장을 자연스럽게 재구성 (원문 그대로 복사 금지)
2. 고유명사와 숫자는 정확히 보존
3. 주요 용어를 **볼드**로 강조
4. 시간 범위는 하이픈으로 (예: 2023-2024)
5. 표/그래프 참조 금지

재작성된 답변만 출력하세요:
"""
        try:
            return self.generate(rewrite_prompt, role="rewriter")
        except google_exceptions.GoogleAPIError as e:
            return f"[재작성 실패: {e}] {text}"
        except Exception as e:
            return f"[재작성 실패(알 수 없음): {e}] {text}"

    def fact_check(self, answer: str, has_table_chart: bool) -> Dict[str, Any]:
        """사실 검증 (표/그래프 참조, 외부 지식 사용 여부 등)."""
        check_prompt = f"""다음 답변을 검증하세요.

답변:
{answer}

검증 항목:
1. 표/그래프 참조 여부 ({"금지됨" if has_table_chart else "허용됨"})
2. 외부 지식 사용 여부 (이미지 텍스트만 사용해야 함)
3. 고유명사/숫자 정확성
4. 마크다운 형식 준수

출력 형식:
판정: PASS 또는 FAIL
문제점: [발견된 문제 목록, 없으면 '없음']
"""
        try:
            response = self.generate(check_prompt, role="fact_checker")
            verdict = "pass" if "PASS" in response.upper() else "fail"

            issues = []
            if "FAIL" in response.upper():
                for line in response.split("\n"):
                    if "문제점:" in line:
                        issues.append(line.split(":")[-1].strip())

            return {
                "verdict": verdict,
                "issues": issues,
                "details": response,
            }
        except google_exceptions.GoogleAPIError as e:
            return {
                "verdict": "error",
                "issues": [f"검증 실패: {e}"],
                "details": "",
            }
        except Exception as e:
            return {
                "verdict": "error",
                "issues": [f"검증 실패(알 수 없음): {e}"],
                "details": "",
            }


if __name__ == "__main__":
    client = GeminiModelClient()

    # 테스트
    test_answers = [
        "2023년 매출은 전년 대비 15% 증가했습니다.",
        "매출 증가율은 15%p를 기록했으며, 이는 신제품 출시 효과입니다.",
        "전체 이미지를 보면 매출이 늘었습니다.",  # 금지 패턴
    ]

    result = client.evaluate("매출 증가율은?", test_answers)
    if result["best_index"] is not None:
        print(f"평가 결과: 최고 답변 = {result['best_index'] + 1}번")
        print(f"재작성: {client.rewrite(test_answers[result['best_index']])[:100]}...")
    else:
        print("평가 결과 없음: 답변이 비어 있습니다.")
