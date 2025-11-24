"""
Minimal Gemini client used across the QA pipeline.

This wraps google.generativeai and provides simple generate/evaluate/rewrite
helpers. Defaults to the model name from `GEMINI_MODEL_NAME` or
`gemini-3-pro-preview` if unset.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from dotenv import load_dotenv

load_dotenv()


def require_env(var: str) -> str:
    """Fetch an environment variable or raise if missing."""
    val = os.getenv(var)
    if not val:
        raise EnvironmentError(f"환경 변수 {var}가 설정되지 않았습니다 (.env 확인).")
    return val


class GeminiModelClient:
    """Real Gemini API client for generation, evaluation, and rewrite."""

    def __init__(self) -> None:
        api_key = require_env("GEMINI_API_KEY")
        genai.configure(api_key=api_key)
        self.model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-3-pro-preview")
        self.model = genai.GenerativeModel(self.model_name)

    def generate(
        self, prompt: str, temperature: float = 0.2, role: str | None = None
    ) -> str:
        """Generate text for a given prompt.

        Args:
            prompt: 입력 프롬프트.
            temperature: 생성 온도.
            role: 호출 의도(호환성용, 현재 로직에서는 사용하지 않음).
        """
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=2048,
                ),
            )
            return response.text
        except google_exceptions.GoogleAPIError as e:
            return f"[생성 실패: {e}]"
        except (ValueError, TypeError) as e:
            return f"[생성 실패(입력 오류): {e}]"
        except Exception as e:  # noqa: BLE001
            return f"[생성 실패(알 수 없음): {e}]"

    def evaluate(self, question: str, answers: List[str]) -> Dict[str, Any]:
        """Evaluate a set of answers; pick the longest as a simple fallback."""
        if not answers:
            return {
                "scores": [],
                "best_index": None,
                "best_answer": None,
                "notes": "평가 실패: 답변이 없습니다.",
            }

        # Placeholder scoring: length-based
        scores = [len(a) for a in answers]
        best_idx = scores.index(max(scores))
        return {
            "scores": scores,
            "best_index": best_idx,
            "best_answer": answers[best_idx],
            "notes": "길이 기반 임시 평가",
        }

    def rewrite(self, answer: str) -> str:
        """Rewrite an answer with light prompting."""
        prompt = (
            "다음 답변을 더 명확하고 간결하게 한국어로 재작성하세요. "
            "사실 관계는 유지하고, 불필요한 군더더기는 제거합니다.\n\n"
            f"{answer}"
        )
        return self.generate(prompt)


if __name__ == "__main__":
    client = GeminiModelClient()
    sample = client.generate("간단한 테스트 문장을 생성해 주세요.")
    print(sample)
