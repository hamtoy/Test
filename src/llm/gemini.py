"""
Minimal Gemini client used across the QA pipeline.

This wraps google.generativeai and provides simple generate/evaluate/rewrite
helpers. Defaults to the model name from `GEMINI_MODEL_NAME` or
`gemini-3-pro-preview` if unset.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from dotenv import load_dotenv

from src.config.constants import DEFAULT_MAX_OUTPUT_TOKENS
from src.infra.logging import log_metrics

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
        genai.configure(api_key=api_key)  # type: ignore[attr-defined]
        self.model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-3-pro-preview")
        self.model = genai.GenerativeModel(self.model_name)  # type: ignore[attr-defined]
        genai_logger = getattr(genai, "_logging", None)
        if genai_logger and getattr(genai_logger, "logger", None):
            self.logger = genai_logger.logger
        else:
            import logging

            self.logger = logging.getLogger("GeminiModelClient")

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
            start = time.perf_counter()
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
                ),
            )
            latency_ms = (time.perf_counter() - start) * 1000
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = response.usage_metadata
                log_metrics(
                    self.logger,
                    latency_ms=latency_ms,
                    prompt_tokens=usage.prompt_token_count,
                    completion_tokens=usage.candidates_token_count,
                )
            return str(response.text)
        except google_exceptions.GoogleAPIError as e:
            return f"[생성 실패: {e}]"
        except (ValueError, TypeError) as e:
            return f"[생성 실패(입력 오류): {e}]"
        except Exception as e:  # noqa: BLE001
            return f"[생성 실패(알 수 없음): {e}]"

    def evaluate(self, question: str, answers: List[str]) -> Dict[str, Any]:
        """Evaluate answers; parse 점수/최고 형식, otherwise length fallback."""

        def _length_fallback(notes: str = "길이 기반 임시 평가") -> Dict[str, Any]:
            scores = [len(a) for a in answers]
            best_idx = scores.index(max(scores)) if scores else None
            return {
                "scores": scores,
                "best_index": best_idx,
                "best_answer": answers[best_idx] if best_idx is not None else None,
                "notes": notes,
            }

        if not answers:
            return _length_fallback("평가 실패: 답변이 없습니다.")

        start = time.perf_counter()
        try:
            raw = self.generate(
                f"질문: {question}\n답변 수: {len(answers)}", role="evaluator"
            )
        except google_exceptions.GoogleAPIError:
            return _length_fallback("API 오류로 길이 기반 평가 수행")
        except Exception:
            return _length_fallback("예상치 못한 오류로 길이 기반 평가 수행")
        latency_ms = (time.perf_counter() - start) * 1000

        scores: List[int] = []
        best_idx: int | None = None
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("점수"):
                try:
                    _, val = line.split(":", 1)
                    scores.append(int(val.strip()))
                except Exception:
                    continue
            elif line.startswith("최고"):
                try:
                    _, val = line.split(":", 1)
                    best_idx = int(val.strip()) - 1
                except Exception:
                    continue

        if scores:
            if best_idx is None:
                best_idx = scores.index(max(scores))
            best_idx = max(0, min(best_idx, len(answers) - 1))
            log_metrics(
                self.logger,
                latency_ms=latency_ms,
                prompt_tokens=len(question),
                completion_tokens=sum(scores),
            )
            return {
                "scores": scores,
                "best_index": best_idx,
                "best_answer": answers[best_idx],
                "notes": "점수 파싱 기반 평가",
            }

        return _length_fallback()

    def rewrite(self, answer: str) -> str:
        """Rewrite an answer with light prompting."""
        prompt = (
            "다음 답변을 더 명확하고 간결하게 한국어로 재작성하세요. "
            "사실 관계는 유지하고, 불필요한 군더더기는 제거합니다.\n\n"
            f"{answer}"
        )
        start = time.perf_counter()
        try:
            rewritten = self.generate(prompt, role="rewriter")
            log_metrics(
                self.logger,
                latency_ms=(time.perf_counter() - start) * 1000,
                prompt_tokens=len(answer),
                completion_tokens=len(rewritten),
            )
            return rewritten
        except google_exceptions.GoogleAPIError as e:
            return f"[재작성 실패: {e}]"
        except Exception as e:  # noqa: BLE001
            return f"[재작성 실패(알 수 없음): {e}]"


if __name__ == "__main__":
    client = GeminiModelClient()
    sample = client.generate("간단한 테스트 문장을 생성해 주세요.")
    print(sample)
