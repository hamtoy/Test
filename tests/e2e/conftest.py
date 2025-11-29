"""
End-to-End 테스트용 Fixture
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    pass


@dataclass
class QueryResult:
    """질의 결과 모의 객체"""

    query: str


@dataclass
class AnswerResult:
    """답변 결과 모의 객체"""

    answer: str


@dataclass
class EvaluationResult:
    """평가 결과 모의 객체"""

    score: float
    feedback: str


class MockCacheManager:
    """캐시 매니저 모의 객체"""

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}

    async def get(self, key: str) -> Any | None:
        return self._cache.get(key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        self._cache[key] = value

    async def clear_all(self) -> None:
        self._cache.clear()


class MockRAGSystem:
    """RAG 시스템 모의 객체"""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def search(self, query: str, k: int = 5) -> list[str]:
        return [f"Result for: {query}"]

    async def initialize_test_data(self) -> None:
        self._data = {"test": "test data"}

    async def cleanup(self) -> None:
        self._data.clear()


class MockGeminiAgent:
    """완전한 워크플로우 에이전트 모의 객체"""

    def __init__(
        self,
        cache_manager: MockCacheManager | None = None,
        rag_system: MockRAGSystem | None = None,
    ) -> None:
        self.cache_manager = cache_manager or MockCacheManager()
        self.rag_system = rag_system or MockRAGSystem()
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self._request_count = 0

    async def generate_query(self, ocr_text: str, intent: str) -> QueryResult:
        """질의 생성"""
        if not ocr_text:
            raise ValueError("OCR text cannot be empty")

        self._request_count += 1

        # 캐시 확인
        cache_key = f"query:{ocr_text}:{intent}"
        cached = await self.cache_manager.get(cache_key)
        if cached is not None:
            return QueryResult(query=cached.query)

        # 결과 생성
        result = QueryResult(query=f"Generated query for: {ocr_text}")

        # 캐시에 저장
        await self.cache_manager.set(cache_key, result)

        return result

    async def generate_answer(self, query: str, context: str) -> AnswerResult:
        """답변 생성"""
        return AnswerResult(answer=f"Answer for query: {query}")

    async def evaluate_answer(self, query: str, answer: str) -> EvaluationResult:
        """답변 평가"""
        return EvaluationResult(score=0.85, feedback="Good answer")

    async def rewrite_answer(
        self, query: str, answer: str, feedback: str
    ) -> AnswerResult:
        """답변 재작성"""
        return AnswerResult(answer=f"Rewritten: {answer}")


@pytest.fixture
def cache_manager() -> MockCacheManager:
    """캐시 매니저 (테스트용 Mock)"""
    return MockCacheManager()


@pytest.fixture
def rag_system() -> MockRAGSystem:
    """RAG 시스템 (테스트용 Mock)"""
    return MockRAGSystem()


@pytest.fixture
def full_workflow_agent(
    cache_manager: MockCacheManager,
    rag_system: MockRAGSystem,
) -> MockGeminiAgent:
    """완전한 워크플로우 에이전트"""
    return MockGeminiAgent(
        cache_manager=cache_manager,
        rag_system=rag_system,
    )
