# mypy: disable-error-code=attr-defined
"""Minimal Gemini client used across the QA pipeline.

This wraps google-generativeai SDK and provides simple generate/evaluate/rewrite
helpers. Defaults to the model name from `GEMINI_MODEL_NAME` or
`gemini-flash-latest` if unset.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from dotenv import load_dotenv
from google.api_core import exceptions as google_exceptions
import google.generativeai as genai

from src.config.constants import DEFAULT_MAX_OUTPUT_TOKENS
from src.config.utils import require_env
from src.infra.logging import log_metrics
from src.llm.init_genai import configure_genai

load_dotenv()


class GeminiModelClient:
    """Real Gemini API client for generation, evaluation, and rewrite.

    Supports automatic fallback to secondary models when rate limits are hit.
    """

    def __init__(
        self,
        fallback_models: list[str] | None = None,
    ) -> None:
        """Initialize the Gemini model client.

        Args:
            fallback_models: Optional list of fallback model names to use
                when the primary model hits rate limits (HTTP 429).
                Example: ["gemini-flash-lite-latest"]
        """
        api_key = require_env("GEMINI_API_KEY")
        configure_genai(api_key=api_key)
        self.model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-flash-latest")
        self.fallback_models = fallback_models or []
        genai_logger = getattr(getattr(genai, "_logging", None), "logger", None)
        self.logger = genai_logger or logging.getLogger("GeminiModelClient")

    def generate(
        self,
        prompt: str,
        temperature: float = 0.2,
        role: str | None = None,
    ) -> str:
        """Generate text for a given prompt with automatic fallback on rate limits.

        Args:
            prompt: 입력 프롬프트.
            temperature: 생성 온도.
            role: 호출 의도(호환성용, 현재 로직에서는 사용하지 않음).

        Returns:
            Generated text string, or error message if all models fail.
        """
        _ = role  # kept for compatibility; not used in current generation flow

        # Build list of models to try: primary + fallbacks
        models_to_try = [self.model_name] + self.fallback_models
        last_error: Exception | None = None

        for model_name in models_to_try:  # noqa: PERF203
            try:
                start = time.perf_counter()
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(
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
                        prompt_tokens=getattr(usage, "prompt_token_count", 0),
                        completion_tokens=getattr(usage, "candidates_token_count", 0),
                    )
                return str(response.text)

            except Exception as e:  # noqa: BLE001, PERF203
                error_name = e.__class__.__name__
                if isinstance(e, google_exceptions.ResourceExhausted) or "429" in str(e):
                    # Rate limit hit - log warning and try next model
                    self.logger.warning(
                        "Rate limit hit for model '%s', switching to fallback... (%s)",
                        model_name,
                        str(e)[:100],
                    )
                    last_error = e
                    continue
                elif isinstance(e, google_exceptions.GoogleAPIError):
                    return f"[생성 실패: {e}]"
                elif isinstance(e, (ValueError, TypeError)):
                    return f"[생성 실패(입력 오류): {e}]"
                else:
                    return f"[생성 실패(알 수 없음): {e}]"

        # All models exhausted due to rate limits
        if last_error:
            return f"[생성 실패: 모든 모델 Rate Limit 초과 - {last_error}]"
        return "[생성 실패: 알 수 없는 오류]"

    def evaluate(self, question: str, answers: list[str]) -> dict[str, Any]:
        """Evaluate answers; parse 점수/최고 형식, otherwise length fallback."""
        if not answers:
            return self._length_fallback(answers, "평가 실패: 답변이 없습니다.")

        raw, latency_ms, fallback_note = self._generate_evaluation_raw(
            question, answers
        )
        if raw is None or latency_ms is None:
            return self._length_fallback(
                answers,
                fallback_note or "예상치 못한 오류로 길이 기반 평가 수행",
            )

        scores, best_idx = self._parse_evaluation_output(raw)
        if not scores:
            return self._length_fallback(answers)

        best_idx = self._normalize_best_index(best_idx, scores, answers)
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

    def _length_fallback(
        self,
        answers: list[str],
        notes: str = "길이 기반 임시 평가",
    ) -> dict[str, Any]:
        scores = [len(a) for a in answers]
        best_idx = scores.index(max(scores)) if scores else None
        return {
            "scores": scores,
            "best_index": best_idx,
            "best_answer": answers[best_idx] if best_idx is not None else None,
            "notes": notes,
        }

    def _generate_evaluation_raw(
        self,
        question: str,
        answers: list[str],
    ) -> tuple[str | None, float | None, str | None]:
        start = time.perf_counter()
        try:
            raw = self.generate(
                f"질문: {question}\n답변 수: {len(answers)}",
                role="evaluator",
            )
            latency_ms = (time.perf_counter() - start) * 1000
            return raw, latency_ms, None
        except Exception:  # noqa: BLE001
            return None, None, "예상치 못한 오류로 길이 기반 평가 수행"

    def _parse_evaluation_output(self, raw: str) -> tuple[list[int], int | None]:
        scores: list[int] = []
        best_idx: int | None = None
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("점수"):
                score = self._parse_score_line(stripped)
                if score is not None:
                    scores.append(score)
                continue
            if stripped.startswith("최고"):
                best_idx = self._parse_best_line(stripped) or best_idx
        return scores, best_idx

    def _parse_score_line(self, line: str) -> int | None:
        try:
            _, val = line.split(":", 1)
            return int(val.strip())
        except Exception:  # noqa: BLE001
            return None

    def _parse_best_line(self, line: str) -> int | None:
        try:
            _, val = line.split(":", 1)
            return int(val.strip()) - 1
        except Exception:  # noqa: BLE001
            return None

    def _normalize_best_index(
        self,
        best_idx: int | None,
        scores: list[int],
        answers: list[str],
    ) -> int:
        resolved = best_idx
        if resolved is None:
            resolved = scores.index(max(scores))
        return max(0, min(resolved, len(answers) - 1))

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
        except (ValueError, TypeError) as e:
            return f"[재작성 실패(입력 오류): {e}]"
        except Exception as e:  # noqa: BLE001
            return f"[재작성 실패(알 수 없음): {e}]"


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    client = GeminiModelClient()
    sample = client.generate("간단한 테스트 문장을 생성해 주세요.")
    logger.info("Generated sample: %s", sample)
