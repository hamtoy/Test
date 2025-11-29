"""Tests for the external evaluation workflow module."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agent import GeminiAgent
from src.workflow.external_eval import evaluate_external_answers


@pytest.fixture
def mock_agent() -> Any:
    """Create a mock GeminiAgent."""
    agent = MagicMock(spec=GeminiAgent)
    agent._create_generative_model = MagicMock(return_value=MagicMock())
    agent._call_api_with_retry = AsyncMock(
        return_value="점수: 85\n피드백: 좋은 답변입니다"
    )
    return agent


@pytest.mark.asyncio
async def test_evaluate_external_answers_basic(mock_agent: Any) -> None:
    """Test basic external answer evaluation."""
    results = await evaluate_external_answers(
        agent=mock_agent,
        ocr_text="테스트 OCR 텍스트",
        query="테스트 질의",
        answers=["답변 A", "답변 B", "답변 C"],
    )

    assert len(results) == 3
    assert results[0]["candidate_id"] == "A"
    assert results[1]["candidate_id"] == "B"
    assert results[2]["candidate_id"] == "C"


@pytest.mark.asyncio
async def test_evaluate_external_answers_scores(mock_agent: Any) -> None:
    """Test that scores are parsed correctly."""
    mock_agent._call_api_with_retry = AsyncMock(
        return_value="점수: 92\n피드백: 훌륭합니다"
    )

    results = await evaluate_external_answers(
        agent=mock_agent,
        ocr_text="OCR",
        query="질의",
        answers=["A", "B", "C"],
    )

    for result in results:
        assert result["score"] == 92
        assert result["feedback"] == "훌륭합니다"


@pytest.mark.asyncio
async def test_evaluate_external_answers_score_clamping(mock_agent: Any) -> None:
    """Test that scores are clamped to 0-100 range."""
    # Test score > 100
    mock_agent._call_api_with_retry = AsyncMock(
        return_value="점수: 150\n피드백: 테스트"
    )

    results = await evaluate_external_answers(
        agent=mock_agent,
        ocr_text="OCR",
        query="질의",
        answers=["A", "B", "C"],
    )

    for result in results:
        assert result["score"] == 100  # Clamped to 100


@pytest.mark.asyncio
async def test_evaluate_external_answers_negative_score_clamping(
    mock_agent: Any,
) -> None:
    """Test that negative scores are clamped to 0."""
    mock_agent._call_api_with_retry = AsyncMock(
        return_value="점수: -10\n피드백: 테스트"
    )

    results = await evaluate_external_answers(
        agent=mock_agent,
        ocr_text="OCR",
        query="질의",
        answers=["A", "B", "C"],
    )

    for result in results:
        assert result["score"] == 0  # Clamped to 0


@pytest.mark.asyncio
async def test_evaluate_external_answers_invalid_score(mock_agent: Any) -> None:
    """Test handling of invalid score format."""
    mock_agent._call_api_with_retry = AsyncMock(
        return_value="점수: not_a_number\n피드백: 테스트"
    )

    results = await evaluate_external_answers(
        agent=mock_agent,
        ocr_text="OCR",
        query="질의",
        answers=["A", "B", "C"],
    )

    # Should use default score of 50
    for result in results:
        assert result["score"] == 50


@pytest.mark.asyncio
async def test_evaluate_external_answers_no_ocr(mock_agent: Any) -> None:
    """Test evaluation without OCR text."""
    results = await evaluate_external_answers(
        agent=mock_agent,
        ocr_text="",  # Empty OCR
        query="질의",
        answers=["A", "B", "C"],
    )

    assert len(results) == 3
    # Verify the prompt includes the empty OCR marker
    call_args = mock_agent._call_api_with_retry.call_args
    prompt = call_args[0][1]
    assert "(제공되지 않음)" in prompt


@pytest.mark.asyncio
async def test_evaluate_external_answers_api_error(mock_agent: Any) -> None:
    """Test handling of API errors."""
    mock_agent._call_api_with_retry = AsyncMock(side_effect=Exception("API 연결 실패"))

    results = await evaluate_external_answers(
        agent=mock_agent,
        ocr_text="OCR",
        query="질의",
        answers=["A", "B", "C"],
    )

    # All results should have score 0 and error feedback
    for result in results:
        assert result["score"] == 0
        assert "평가 실패" in result["feedback"]


@pytest.mark.asyncio
async def test_evaluate_external_answers_prompt_structure(mock_agent: Any) -> None:
    """Test that the prompt has correct structure."""
    await evaluate_external_answers(
        agent=mock_agent,
        ocr_text="테스트 OCR",
        query="테스트 질의",
        answers=["답변 A", "답변 B", "답변 C"],
    )

    # Verify system prompt
    system_prompt = mock_agent._create_generative_model.call_args[0][0]
    assert "평가하는 전문가" in system_prompt

    # Verify user prompt structure
    call_args = mock_agent._call_api_with_retry.call_args
    prompt = call_args[0][1]
    assert "[OCR 텍스트]" in prompt
    assert "[질의]" in prompt
    assert "정확성" in prompt
    assert "완전성" in prompt
    assert "표현력" in prompt


@pytest.mark.asyncio
async def test_evaluate_external_answers_feedback_parsing(mock_agent: Any) -> None:
    """Test that feedback is parsed correctly."""
    mock_agent._call_api_with_retry = AsyncMock(
        return_value="점수: 75\n피드백: 개선이 필요합니다"
    )

    results = await evaluate_external_answers(
        agent=mock_agent,
        ocr_text="OCR",
        query="질의",
        answers=["A", "B", "C"],
    )

    for result in results:
        assert result["feedback"] == "개선이 필요합니다"


@pytest.mark.asyncio
async def test_evaluate_external_answers_multiline_response(mock_agent: Any) -> None:
    """Test handling of multiline response."""
    mock_agent._call_api_with_retry = AsyncMock(
        return_value="추가 설명\n점수: 88\n피드백: 잘했습니다\n추가 정보"
    )

    results = await evaluate_external_answers(
        agent=mock_agent,
        ocr_text="OCR",
        query="질의",
        answers=["A", "B", "C"],
    )

    for result in results:
        assert result["score"] == 88
        assert result["feedback"] == "잘했습니다"
