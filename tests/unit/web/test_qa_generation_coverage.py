"""Additional tests for src/web/routers/qa_generation.py to improve coverage.

Targets uncovered lines and edge cases:
- Cache statistics endpoint
- Cache clear endpoint
- Batch type resolution
- Error handling in generation
- Timeout scenarios
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

from src.web.models import GenerateQARequest
from src.web.routers.qa_generation import (
    _append_previous_query,
    _fallback_pair,
    _generate_first_pair,
    _resolve_batch_types,
    _traceback_str,
    api_generate_qa,
    clear_cache,
    generate_single_qa_with_retry,
    get_cache_stats,
)


class TestCacheEndpoints:
    """Test cache management endpoints."""

    @pytest.mark.asyncio
    async def test_get_cache_stats_returns_metrics(self) -> None:
        """Test cache stats endpoint returns proper metrics."""
        with patch("src.web.routers.qa_generation.answer_cache") as mock_cache:
            mock_cache.get_stats.return_value = {
                "hits": 10,
                "misses": 5,
                "cache_size": 15,
                "hit_rate_percent": 66.7,
            }

            result = await get_cache_stats()

            assert result["success"] is True
            assert result["data"]["hits"] == 10
            assert result["data"]["misses"] == 5
            assert "estimated_time_saved_seconds" in result["data"]
            assert "estimated_time_saved_minutes" in result["data"]
            assert "Cache hit rate" in result["message"]

    @pytest.mark.asyncio
    async def test_clear_cache_returns_cleared_count(self) -> None:
        """Test cache clear endpoint returns number of cleared entries."""
        with patch("src.web.routers.qa_generation.answer_cache") as mock_cache:
            mock_cache.get_stats.return_value = {"cache_size": 42}
            mock_cache.clear = AsyncMock()

            result = await clear_cache()

            assert result["success"] is True
            assert result["data"]["entries_cleared"] == 42
            assert "Cleared 42" in result["message"]
            mock_cache.clear.assert_called_once()


class TestBatchTypeResolution:
    """Test batch type resolution logic."""

    def test_resolve_batch_types_default(self) -> None:
        """Test default batch types resolution."""
        body = GenerateQARequest(mode="batch")
        result = _resolve_batch_types(body)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_resolve_batch_types_custom(self) -> None:
        """Test custom batch types."""
        body = GenerateQARequest(
            mode="batch", batch_types=["explanation", "reasoning"]
        )
        result = _resolve_batch_types(body)
        assert result == ["explanation", "reasoning"]

    def test_resolve_batch_types_three_mode(self) -> None:
        """Test batch_three mode defaults."""
        body = GenerateQARequest(mode="batch_three")
        result = _resolve_batch_types(body)
        assert isinstance(result, list)

    def test_resolve_batch_types_empty_raises(self) -> None:
        """Test empty batch_types raises HTTPException."""
        body = GenerateQARequest(mode="batch", batch_types=[])
        with pytest.raises(HTTPException) as exc_info:
            _resolve_batch_types(body)
        assert exc_info.value.status_code == 400


class TestErrorHandling:
    """Test error handling in generation."""

    def test_fallback_pair_on_exception(self) -> None:
        """Test fallback pair generation on exception."""
        exc = ValueError("테스트 에러")
        result = _fallback_pair("reasoning", exc)

        assert result["type"] == "reasoning"
        assert result["query"] == "생성 실패"
        assert "일시적 오류" in result["answer"]
        assert "테스트 에러" in result["answer"]

    def test_traceback_str_formats_exception(self) -> None:
        """Test traceback string formatting."""
        try:
            raise ValueError("테스트 예외")
        except ValueError as e:
            result = _traceback_str(e)
            assert "ValueError" in result
            assert "테스트 예외" in result
            assert "Traceback" in result or "File" in result

    def test_append_previous_query_with_valid_query(self) -> None:
        """Test appending valid query to previous queries."""
        pair = {"query": "테스트 질문", "answer": "답변"}
        previous_queries: list[str] = []

        _append_previous_query(pair, previous_queries)

        assert len(previous_queries) == 1
        assert previous_queries[0] == "테스트 질문"

    def test_append_previous_query_skips_failed_query(self) -> None:
        """Test skipping failed query."""
        pair = {"query": "생성 실패", "answer": "에러"}
        previous_queries: list[str] = []

        _append_previous_query(pair, previous_queries)

        assert len(previous_queries) == 0

    def test_append_previous_query_with_no_query(self) -> None:
        """Test handling pair without query field."""
        pair = {"answer": "답변만 있음"}
        previous_queries: list[str] = []

        _append_previous_query(pair, previous_queries)

        assert len(previous_queries) == 0


class TestGenerateFirstPair:
    """Test first pair generation helper."""

    @pytest.mark.asyncio
    async def test_generate_first_pair_success(self) -> None:
        """Test successful first pair generation."""
        mock_agent = Mock()

        with patch(
            "src.web.routers.qa_generation.generate_single_qa_with_retry"
        ) as mock_gen:
            mock_gen.return_value = {"query": "질문", "answer": "답변"}
            with patch("src.web.routers.qa_generation._get_config") as mock_cfg:
                mock_cfg.return_value = Mock(qa_single_timeout=30)

                result, query = await _generate_first_pair(
                    mock_agent, "OCR 텍스트", "reasoning"
                )

                assert result["query"] == "질문"
                assert query == "질문"

    @pytest.mark.asyncio
    async def test_generate_first_pair_timeout(self) -> None:
        """Test first pair generation with timeout."""
        mock_agent = Mock()

        with patch(
            "src.web.routers.qa_generation.generate_single_qa_with_retry"
        ) as mock_gen:
            mock_gen.side_effect = asyncio.TimeoutError()
            with patch("src.web.routers.qa_generation._get_config") as mock_cfg:
                mock_cfg.return_value = Mock(qa_single_timeout=1)

                result, query = await _generate_first_pair(
                    mock_agent, "OCR 텍스트", "reasoning"
                )

                # Should return fallback pair
                assert result["query"] == "생성 실패"
                assert query == ""

    @pytest.mark.asyncio
    async def test_generate_first_pair_exception(self) -> None:
        """Test first pair generation with general exception."""
        mock_agent = Mock()

        with patch(
            "src.web.routers.qa_generation.generate_single_qa_with_retry"
        ) as mock_gen:
            mock_gen.side_effect = ValueError("생성 중 오류")
            with patch("src.web.routers.qa_generation._get_config") as mock_cfg:
                mock_cfg.return_value = Mock(qa_single_timeout=30)

                result, query = await _generate_first_pair(
                    mock_agent, "OCR 텍스트", "explanation"
                )

                assert result["query"] == "생성 실패"
                assert "생성 중 오류" in result["answer"]


class TestAPIGenerateQA:
    """Test main API endpoint."""

    @pytest.mark.asyncio
    async def test_api_generate_qa_no_agent(self) -> None:
        """Test API returns error when agent not initialized."""
        body = GenerateQARequest(mode="single", qtype="explanation")

        with patch("src.web.routers.qa_generation._get_agent", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await api_generate_qa(body)

            assert exc_info.value.status_code == 500
            assert "Agent 초기화 실패" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_api_generate_qa_single_mode_no_qtype(self) -> None:
        """Test single mode without qtype raises error."""
        body = GenerateQARequest(mode="single")

        mock_agent = Mock()
        with patch("src.web.routers.qa_generation._get_agent", return_value=mock_agent):
            with patch("src.web.routers.qa_generation.load_ocr_text") as mock_ocr:
                mock_ocr.return_value = "OCR 텍스트"
                with patch("src.web.routers.qa_generation._get_config"):
                    with pytest.raises(HTTPException) as exc_info:
                        await api_generate_qa(body)

                    assert exc_info.value.status_code == 400
                    assert "qtype이 필요합니다" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_api_generate_qa_batch_timeout(self) -> None:
        """Test batch mode timeout handling."""
        body = GenerateQARequest(mode="batch")

        mock_agent = Mock()
        with patch("src.web.routers.qa_generation._get_agent", return_value=mock_agent):
            with patch("src.web.routers.qa_generation.load_ocr_text") as mock_ocr:
                mock_ocr.return_value = "OCR 텍스트"
                with patch("src.web.routers.qa_generation._get_config") as mock_cfg:
                    mock_cfg.return_value = Mock(
                        qa_batch_timeout=1, qa_single_timeout=1
                    )
                    with patch(
                        "src.web.routers.qa_generation._process_batch_request"
                    ) as mock_batch:
                        # Simulate timeout
                        async def slow_process(*args: Any, **kwargs: Any) -> None:
                            import asyncio

                            await asyncio.sleep(10)

                        mock_batch.side_effect = slow_process

                        with pytest.raises(HTTPException) as exc_info:
                            await api_generate_qa(body)

                        assert exc_info.value.status_code == 504
                        assert "시간 초과" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_api_generate_qa_uses_provided_ocr(self) -> None:
        """Test API uses OCR text from request body."""
        body = GenerateQARequest(
            mode="single", qtype="explanation", ocr_text="직접 제공한 OCR"
        )

        mock_agent = Mock()
        with patch("src.web.routers.qa_generation._get_agent", return_value=mock_agent):
            with patch("src.web.routers.qa_generation._get_config") as mock_cfg:
                mock_cfg.return_value = Mock(qa_single_timeout=30)
                with patch(
                    "src.web.routers.qa_generation.generate_single_qa"
                ) as mock_gen:
                    mock_gen.return_value = {"query": "Q", "answer": "A"}

                    await api_generate_qa(body)

                    # Verify generate_single_qa was called with provided OCR
                    mock_gen.assert_called_once()
                    call_args = mock_gen.call_args
                    assert call_args[0][1] == "직접 제공한 OCR"


class TestGenerateSingleQAWithRetry:
    """Test retry wrapper for single QA generation."""

    @pytest.mark.asyncio
    async def test_generate_single_qa_with_retry_success(self) -> None:
        """Test successful generation without retry."""
        mock_agent = Mock()

        with patch("src.web.routers.qa_generation.generate_single_qa") as mock_gen:
            mock_gen.return_value = {"query": "Q", "answer": "A"}

            result = await generate_single_qa_with_retry(
                mock_agent, "OCR", "reasoning"
            )

            assert result["query"] == "Q"
            mock_gen.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_single_qa_with_retry_retries_on_failure(self) -> None:
        """Test retry logic on transient failures."""
        mock_agent = Mock()

        with patch("src.web.routers.qa_generation.generate_single_qa") as mock_gen:
            # First two calls fail, third succeeds
            mock_gen.side_effect = [
                ValueError("일시 오류"),
                ValueError("일시 오류"),
                {"query": "Q", "answer": "A"},
            ]

            result = await generate_single_qa_with_retry(
                mock_agent, "OCR", "explanation"
            )

            assert result["query"] == "Q"
            assert mock_gen.call_count == 3

    @pytest.mark.asyncio
    async def test_generate_single_qa_with_retry_exhausts_retries(self) -> None:
        """Test that retry exhaustion raises exception."""
        mock_agent = Mock()

        with patch("src.web.routers.qa_generation.generate_single_qa") as mock_gen:
            mock_gen.side_effect = ValueError("지속적인 오류")

            with pytest.raises(ValueError):
                await generate_single_qa_with_retry(mock_agent, "OCR", "reasoning")

    @pytest.mark.asyncio
    async def test_generate_single_qa_with_retry_with_optional_params(self) -> None:
        """Test retry with optional previous_queries and explanation_answer."""
        mock_agent = Mock()

        with patch("src.web.routers.qa_generation.generate_single_qa") as mock_gen:
            mock_gen.return_value = {"query": "Q", "answer": "A"}

            result = await generate_single_qa_with_retry(
                mock_agent,
                "OCR",
                "target_short",
                previous_queries=["이전 질문"],
                explanation_answer="설명 답변",
            )

            assert result["query"] == "Q"
            mock_gen.assert_called_once_with(
                mock_agent,
                "OCR",
                "target_short",
                ["이전 질문"],
                "설명 답변",
            )


class TestProcessBatchRequest:
    """Test batch request processing logic."""

    @pytest.mark.asyncio
    async def test_process_batch_request_with_reasoning_parallel(self) -> None:
        """Test batch processing with reasoning in parallel."""
        from src.web.routers.qa_generation import _process_batch_request

        body = GenerateQARequest(
            mode="batch",
            batch_types=["global_explanation", "reasoning", "target_short"],
        )
        mock_agent = Mock()

        with patch(
            "src.web.routers.qa_generation.generate_single_qa_with_retry"
        ) as mock_gen:
            mock_gen.side_effect = [
                {"query": "Q1", "answer": "A1", "type": "global_explanation"},
                {"query": "Q2", "answer": "A2", "type": "reasoning"},
                {"query": "Q3", "answer": "A3", "type": "target_short"},
            ]
            with patch("src.web.routers.qa_generation._get_config") as mock_cfg:
                mock_cfg.return_value = Mock()

                result = await _process_batch_request(
                    body, mock_agent, "OCR", datetime.now()
                )

                assert "pairs" in result["data"]
                # Should have all three results
                assert len(result["data"]["pairs"]) == 3
