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
        return_value=(
            "A점수: 5\nA피드백: 좋음\nB점수: 4\nB피드백: 보통\nC점수: 3\nC피드백: 부족"
        )
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
    assert [r["score"] for r in results] == [5, 4, 3]


@pytest.mark.asyncio
async def test_evaluate_external_answers_scores(mock_agent: Any) -> None:
    """Test that scores are parsed correctly."""
    mock_agent._call_api_with_retry = AsyncMock(
        return_value=(
            "A점수: 6\nA피드백: 훌륭\nB점수: 2\nB피드백: 나쁨\nC점수: 1\nC피드백: 최악"
        )
    )

    results = await evaluate_external_answers(
        agent=mock_agent,
        ocr_text="OCR",
        query="질의",
        answers=["A", "B", "C"],
    )

    assert [r["score"] for r in results] == [6, 2, 1]
    assert results[0]["feedback"] == "훌륭"


@pytest.mark.asyncio
async def test_evaluate_external_answers_score_clamping(mock_agent: Any) -> None:
    """Test that scores are clamped to 1-6 range."""
    mock_agent._call_api_with_retry = AsyncMock(
        return_value=(
            "A점수: 150\nA피드백: 테스트\nB점수: 0\nB피드백: 테스트\nC점수: -10\nC피드백: 테스트"
        )
    )

    results = await evaluate_external_answers(
        agent=mock_agent,
        ocr_text="OCR",
        query="질의",
        answers=["A", "B", "C"],
    )

    assert [r["score"] for r in results] == [6, 1, 1]


@pytest.mark.asyncio
async def test_evaluate_external_answers_negative_score_clamping(
    mock_agent: Any,
) -> None:
    """Test that negative scores are clamped to minimum (1)."""
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
        assert result["score"] == 1  # Clamped to 1


@pytest.mark.asyncio
async def test_evaluate_external_answers_invalid_score(mock_agent: Any) -> None:
    """Test handling of invalid score format."""
    mock_agent._call_api_with_retry = AsyncMock(
        return_value="A점수: not_a_number\nA피드백: 테스트\nB점수: \nB피드백:\nC피드백: 없음"
    )

    results = await evaluate_external_answers(
        agent=mock_agent,
        ocr_text="OCR",
        query="질의",
        answers=["A", "B", "C"],
    )

    assert [r["score"] for r in results] == [3, 3, 3]


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

    assert [r["score"] for r in results] == [3, 2, 1]
    for result in results:
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

    system_prompt = mock_agent._create_generative_model.call_args[0][0]
    assert "평가하는 전문가" in system_prompt
    assert "1~6점" in system_prompt or "1-6점" in system_prompt
    assert "동점 금지" in system_prompt

    call_args = mock_agent._call_api_with_retry.call_args
    prompt = call_args[0][1]
    assert "[OCR 텍스트]" in prompt
    assert "[질의]" in prompt
    assert "[답변 A]" in prompt and "[답변 B]" in prompt and "[답변 C]" in prompt


@pytest.mark.asyncio
async def test_evaluate_external_answers_feedback_parsing(mock_agent: Any) -> None:
    """Test that feedback is parsed correctly."""
    mock_agent._call_api_with_retry = AsyncMock(
        return_value=(
            "A점수: 4\nA피드백: 개선이 필요합니다\nB점수: 5\nB피드백: 좋음\nC점수: 2\nC피드백: 약함"
        )
    )

    results = await evaluate_external_answers(
        agent=mock_agent,
        ocr_text="OCR",
        query="질의",
        answers=["A", "B", "C"],
    )

    assert results[0]["feedback"] == "개선이 필요합니다"


@pytest.mark.asyncio
async def test_evaluate_external_answers_multiline_response(mock_agent: Any) -> None:
    """Test handling of multiline response."""
    mock_agent._call_api_with_retry = AsyncMock(
        return_value=(
            "추가 설명\nA점수: 8\nA피드백: 잘했습니다\n추가 정보\n"
            "B점수: 6\nB피드백: 좋음\nC점수: 5\nC피드백: 무난"
        )
    )

    results = await evaluate_external_answers(
        agent=mock_agent,
        ocr_text="OCR",
        query="질의",
        answers=["A", "B", "C"],
    )

    assert results[0]["score"] == 6  # clamped from 8
    assert results[0]["feedback"] == "잘했습니다"


@pytest.mark.asyncio
async def test_evaluate_external_answers_tie_breaking(mock_agent: Any) -> None:
    """점수 동점 시 자동 조정된다."""
    mock_agent._call_api_with_retry = AsyncMock(
        return_value=(
            "A점수: 5\nA피드백: A\nB점수: 5\nB피드백: B\nC점수: 5\nC피드백: C"
        )
    )

    results = await evaluate_external_answers(
        agent=mock_agent,
        ocr_text="OCR",
        query="질의",
        answers=["A", "B", "C"],
    )

    scores = [r["score"] for r in results]
    assert len(set(scores)) == 3
    assert max(scores) == 5
