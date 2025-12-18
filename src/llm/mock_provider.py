"""Mock LLM provider for testing and dry-run CLI flows."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from src.core.interfaces import GenerationResult, LLMProvider
from src.core.models import EvaluationResultSchema, QueryResult, StructuredAnswerSchema


class MockLLMProvider(LLMProvider):
    """Deterministic LLM provider for tests and dry-run CLI flows."""

    def __init__(
        self,
        *,
        queries: list[str] | None = None,
        best_candidate: str = "A",
    ) -> None:
        """Initialize the mock LLM provider.

        Args:
            queries: Optional list of predefined query strings.
            best_candidate: The candidate to return as best (A, B, or C).
        """
        self._queries = queries or ["테스트 질의 1", "테스트 질의 2", "테스트 질의 3"]
        self._best_candidate = (
            best_candidate if best_candidate in {"A", "B", "C"} else "A"
        )

    async def generate_content_async(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        response_schema: Any | None = None,
        **kwargs: Any,
    ) -> GenerationResult:
        """Generate mock content based on the response schema.

        Args:
            prompt: The input prompt (ignored in mock).
            system_instruction: Optional system instruction (ignored in mock).
            temperature: Sampling temperature (ignored in mock).
            max_output_tokens: Maximum tokens (ignored in mock).
            response_schema: Schema determining the mock response type.
            **kwargs: Additional arguments (ignored in mock).

        Returns:
            GenerationResult with deterministic mock content.
        """
        _ = (
            prompt,
            system_instruction,
            temperature,
            max_output_tokens,
            kwargs,
        )

        if response_schema is QueryResult:
            payload: dict[str, Any] = {"queries": list(self._queries)}
            return GenerationResult(
                content=json.dumps(payload, ensure_ascii=False),
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                finish_reason="STOP",
            )

        if response_schema is EvaluationResultSchema:
            evaluations = [
                {"candidate_id": "A", "score": 5, "reason": "Mock evaluation"},
                {"candidate_id": "B", "score": 4, "reason": "Mock evaluation"},
                {"candidate_id": "C", "score": 3, "reason": "Mock evaluation"},
            ]
            payload = {
                "best_candidate": self._best_candidate,
                "evaluations": evaluations,
            }
            return GenerationResult(
                content=json.dumps(payload, ensure_ascii=False),
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                finish_reason="STOP",
            )

        if response_schema is StructuredAnswerSchema:
            payload = {
                "intro": "테스트 도입부입니다.",
                "sections": [
                    {
                        "title": "핵심 내용",
                        "items": [
                            {"label": "항목 1", "text": "테스트용 문장입니다."},
                            {"label": "항목 2", "text": "테스트용 문장입니다."},
                        ],
                    }
                ],
                "conclusion": "종합하면 테스트입니다.",
            }
            return GenerationResult(
                content=json.dumps(payload, ensure_ascii=False),
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                finish_reason="STOP",
            )

        if isinstance(response_schema, type) and issubclass(response_schema, BaseModel):
            return GenerationResult(
                content="{}",
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                finish_reason="STOP",
            )

        # Unstructured fallback
        return GenerationResult(
            content="OK",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            finish_reason="STOP",
        )

    async def count_tokens(self, text: str) -> int:
        """Count tokens as word count for testing purposes.

        Args:
            text: The text to count tokens for.

        Returns:
            The number of whitespace-separated words.
        """
        return len(text.split())
