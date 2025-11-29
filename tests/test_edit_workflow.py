"""Tests for the edit workflow module."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agent import GeminiAgent
from src.workflow.edit import edit_content


@pytest.fixture
def mock_agent() -> Any:
    """Create a mock GeminiAgent."""
    agent = MagicMock(spec=GeminiAgent)
    agent._create_generative_model = MagicMock(return_value=MagicMock())
    agent._call_api_with_retry = AsyncMock(return_value="수정된 답변 텍스트")
    return agent


@pytest.fixture
def mock_kg() -> Any:
    """Create a mock knowledge graph."""
    kg = MagicMock()
    kg.get_constraints_for_query_type = MagicMock(
        return_value=[{"description": "Rule 1"}, {"description": "Rule 2"}]
    )
    return kg


@pytest.mark.asyncio
async def test_edit_content_basic(mock_agent: Any) -> None:
    """Test basic edit content functionality."""
    result = await edit_content(
        agent=mock_agent,
        answer="원본 답변 텍스트",
        ocr_text="OCR 텍스트",
        query="질의 내용",
        edit_request="더 간결하게 수정해줘",
    )

    assert result == "수정된 답변 텍스트"
    mock_agent._create_generative_model.assert_called_once()
    mock_agent._call_api_with_retry.assert_called_once()


@pytest.mark.asyncio
async def test_edit_content_without_ocr(mock_agent: Any) -> None:
    """Test edit content without OCR text."""
    result = await edit_content(
        agent=mock_agent,
        answer="원본 답변",
        ocr_text="",  # No OCR
        query="",  # No query
        edit_request="표현을 자연스럽게 다듬어줘",
    )

    assert result == "수정된 답변 텍스트"
    # Verify the prompt includes the "(제공되지 않음)" marker for missing OCR
    call_args = mock_agent._call_api_with_retry.call_args
    prompt = call_args[0][1]  # Second argument is the prompt
    assert "(제공되지 않음)" in prompt


@pytest.mark.asyncio
async def test_edit_content_without_query(mock_agent: Any) -> None:
    """Test edit content without query."""
    result = await edit_content(
        agent=mock_agent,
        answer="원본 답변",
        ocr_text="OCR 내용",
        query="",  # No query
        edit_request="결론을 앞에 배치해줘",
    )

    assert result == "수정된 답변 텍스트"
    call_args = mock_agent._call_api_with_retry.call_args
    prompt = call_args[0][1]
    assert "(별도 질의 없음)" in prompt


@pytest.mark.asyncio
async def test_edit_content_with_kg(mock_agent: Any, mock_kg: Any) -> None:
    """Test edit content with knowledge graph rules."""
    result = await edit_content(
        agent=mock_agent,
        answer="원본 답변",
        ocr_text="OCR",
        query="질의",
        edit_request="수정 요청",
        kg=mock_kg,
    )

    assert result == "수정된 답변 텍스트"
    mock_kg.get_constraints_for_query_type.assert_called_once_with("general")


@pytest.mark.asyncio
async def test_edit_content_with_kg_error(mock_agent: Any, mock_kg: Any) -> None:
    """Test edit content handles knowledge graph errors gracefully."""
    mock_kg.get_constraints_for_query_type = MagicMock(
        side_effect=Exception("Neo4j connection failed")
    )

    # Should not raise, just log warning and continue
    result = await edit_content(
        agent=mock_agent,
        answer="원본 답변",
        ocr_text="OCR",
        query="",
        edit_request="수정 요청",
        kg=mock_kg,
    )

    assert result == "수정된 답변 텍스트"


@pytest.mark.asyncio
async def test_edit_content_prompt_structure(mock_agent: Any) -> None:
    """Test that the prompt has the correct structure."""
    await edit_content(
        agent=mock_agent,
        answer="테스트 답변",
        ocr_text="테스트 OCR",
        query="테스트 질의",
        edit_request="테스트 수정 요청",
    )

    # Check system prompt
    system_prompt = mock_agent._create_generative_model.call_args[0][0]
    assert "텍스트를 자연스럽게 수정하는 어시스턴트" in system_prompt

    # Check user prompt structure
    user_prompt = mock_agent._call_api_with_retry.call_args[0][1]
    assert "[OCR 텍스트]" in user_prompt
    assert "테스트 OCR" in user_prompt
    assert "[현재 답변]" in user_prompt
    assert "테스트 답변" in user_prompt
    assert "[질의]" in user_prompt
    assert "테스트 질의" in user_prompt
    assert "[수정 요청]" in user_prompt
    assert "테스트 수정 요청" in user_prompt
    assert "[추가 지침]" in user_prompt


@pytest.mark.asyncio
async def test_edit_content_strips_whitespace(mock_agent: Any) -> None:
    """Test that result is stripped of whitespace."""
    mock_agent._call_api_with_retry = AsyncMock(return_value="  수정된 텍스트  \n\n")

    result = await edit_content(
        agent=mock_agent,
        answer="원본",
        ocr_text="OCR",
        query="",
        edit_request="수정",
    )

    assert result == "수정된 텍스트"


@pytest.mark.asyncio
async def test_edit_content_with_kg_rules_in_prompt(
    mock_agent: Any, mock_kg: Any
) -> None:
    """Test that knowledge graph rules appear in the prompt."""
    await edit_content(
        agent=mock_agent,
        answer="답변",
        ocr_text="OCR",
        query="",
        edit_request="수정",
        kg=mock_kg,
    )

    user_prompt = mock_agent._call_api_with_retry.call_args[0][1]
    assert "- Rule 1" in user_prompt
    assert "- Rule 2" in user_prompt
