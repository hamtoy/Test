"""Tests for src/llm/mock_provider.py - MockLLMProvider."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from src.core.interfaces import GenerationResult
from src.core.models import EvaluationResultSchema, QueryResult, StructuredAnswerSchema
from src.llm.mock_provider import MockLLMProvider


class CustomPydanticModel(BaseModel):
    """Custom model for testing BaseModel fallback."""

    field: str


class TestMockLLMProviderInit:
    """Tests for MockLLMProvider initialization."""

    def test_init_default(self) -> None:
        """Test default initialization."""
        provider = MockLLMProvider()
        assert provider._queries == ["테스트 질의 1", "테스트 질의 2", "테스트 질의 3"]
        assert provider._best_candidate == "A"

    def test_init_with_custom_queries(self) -> None:
        """Test initialization with custom queries."""
        queries = ["Query 1", "Query 2"]
        provider = MockLLMProvider(queries=queries)
        assert provider._queries == queries

    def test_init_with_valid_best_candidate(self) -> None:
        """Test initialization with valid best candidate."""
        for candidate in ["A", "B", "C"]:
            provider = MockLLMProvider(best_candidate=candidate)
            assert provider._best_candidate == candidate

    def test_init_with_invalid_best_candidate(self) -> None:
        """Test initialization with invalid best candidate defaults to A."""
        provider = MockLLMProvider(best_candidate="D")
        assert provider._best_candidate == "A"

        provider = MockLLMProvider(best_candidate="invalid")
        assert provider._best_candidate == "A"


class TestMockLLMProviderGenerateContentAsync:
    """Tests for MockLLMProvider.generate_content_async method."""

    @pytest.fixture
    def provider(self) -> MockLLMProvider:
        """Create a MockLLMProvider instance."""
        return MockLLMProvider()

    @pytest.mark.asyncio
    async def test_generate_query_result(self, provider: MockLLMProvider) -> None:
        """Test generation with QueryResult schema."""
        result = await provider.generate_content_async(
            prompt="test prompt",
            response_schema=QueryResult,
        )

        assert isinstance(result, GenerationResult)
        assert result.finish_reason == "STOP"
        assert result.usage == {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

        content = json.loads(result.content)
        assert "queries" in content
        assert len(content["queries"]) == 3

    @pytest.mark.asyncio
    async def test_generate_evaluation_result(self, provider: MockLLMProvider) -> None:
        """Test generation with EvaluationResultSchema schema."""
        result = await provider.generate_content_async(
            prompt="test prompt",
            response_schema=EvaluationResultSchema,
        )

        assert isinstance(result, GenerationResult)
        content = json.loads(result.content)
        assert content["best_candidate"] == "A"
        assert len(content["evaluations"]) == 3

        for eval_item in content["evaluations"]:
            assert eval_item["reason"] == "Mock evaluation"

    @pytest.mark.asyncio
    async def test_generate_evaluation_result_custom_best(self) -> None:
        """Test evaluation result with custom best candidate."""
        provider = MockLLMProvider(best_candidate="B")
        result = await provider.generate_content_async(
            prompt="test prompt",
            response_schema=EvaluationResultSchema,
        )

        content = json.loads(result.content)
        assert content["best_candidate"] == "B"

    @pytest.mark.asyncio
    async def test_generate_structured_answer(self, provider: MockLLMProvider) -> None:
        """Test generation with StructuredAnswerSchema schema."""
        result = await provider.generate_content_async(
            prompt="test prompt",
            response_schema=StructuredAnswerSchema,
        )

        assert isinstance(result, GenerationResult)
        content = json.loads(result.content)
        assert "intro" in content
        assert "sections" in content
        assert "conclusion" in content
        assert content["intro"] == "테스트 도입부입니다."

    @pytest.mark.asyncio
    async def test_generate_custom_pydantic_model(
        self, provider: MockLLMProvider
    ) -> None:
        """Test generation with custom Pydantic model returns empty JSON."""
        result = await provider.generate_content_async(
            prompt="test prompt",
            response_schema=CustomPydanticModel,
        )

        assert isinstance(result, GenerationResult)
        assert result.content == "{}"
        assert result.finish_reason == "STOP"

    @pytest.mark.asyncio
    async def test_generate_unstructured_fallback(
        self, provider: MockLLMProvider
    ) -> None:
        """Test generation without schema returns OK."""
        result = await provider.generate_content_async(
            prompt="test prompt",
            response_schema=None,
        )

        assert isinstance(result, GenerationResult)
        assert result.content == "OK"
        assert result.finish_reason == "STOP"

    @pytest.mark.asyncio
    async def test_generate_ignores_all_parameters(
        self, provider: MockLLMProvider
    ) -> None:
        """Test that provider ignores prompt, temperature, etc."""
        result = await provider.generate_content_async(
            prompt="This prompt is ignored",
            system_instruction="This is ignored too",
            temperature=0.5,
            max_output_tokens=100,
            extra_param="also ignored",
        )

        assert isinstance(result, GenerationResult)
        assert result.content == "OK"


class TestMockLLMProviderCountTokens:
    """Tests for MockLLMProvider.count_tokens method."""

    @pytest.mark.asyncio
    async def test_count_tokens_single_word(self) -> None:
        """Test token counting with single word."""
        provider = MockLLMProvider()
        count = await provider.count_tokens("hello")
        assert count == 1

    @pytest.mark.asyncio
    async def test_count_tokens_multiple_words(self) -> None:
        """Test token counting with multiple words."""
        provider = MockLLMProvider()
        count = await provider.count_tokens("hello world how are you")
        assert count == 5

    @pytest.mark.asyncio
    async def test_count_tokens_empty_string(self) -> None:
        """Test token counting with empty string."""
        provider = MockLLMProvider()
        count = await provider.count_tokens("")
        # "".split() returns [] so count is 0
        assert count == 0

    @pytest.mark.asyncio
    async def test_count_tokens_whitespace_only(self) -> None:
        """Test token counting with whitespace only."""
        provider = MockLLMProvider()
        count = await provider.count_tokens("   ")
        assert count == 0  # split removes all whitespace


class TestMockLLMProviderConstants:
    """Tests for MockLLMProvider class constants."""

    def test_mock_reason_constant(self) -> None:
        """Test that _MOCK_REASON constant is defined."""
        assert MockLLMProvider._MOCK_REASON == "Mock evaluation"
