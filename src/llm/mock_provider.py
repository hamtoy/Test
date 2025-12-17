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
        self._queries = queries or ["테스트 질의 1", "테스트 질의 2", "테스트 질의 3"]
        self._best_candidate = best_candidate if best_candidate in {"A", "B", "C"} else "A"

    async def generate_content_async(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        response_schema: Any | None = None,
        **kwargs: Any,
    ) -> GenerationResult:
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
        return len(text.split())
