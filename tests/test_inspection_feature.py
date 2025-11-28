from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agent import GeminiAgent
from src.workflow.inspection import inspect_answer, inspect_query


# Mock dependencies
@pytest.fixture
def mock_agent():
    agent = MagicMock(spec=GeminiAgent)
    agent.llm_provider = MagicMock()
    return agent


@pytest.fixture
def mock_components():
    kg = MagicMock()
    kg.get_constraints_for_query_type.return_value = [{"description": "Rule 1"}]

    lats = MagicMock()

    difficulty = MagicMock()
    difficulty.analyze_image_complexity.return_value = {"level": "medium"}

    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()

    validator = MagicMock()
    validator.cross_validate_qa_pair.return_value = {"overall_score": 0.8}

    return kg, lats, difficulty, cache, validator


@pytest.mark.asyncio
async def test_inspect_query(mock_agent, mock_components):
    kg, lats, difficulty, cache, _ = mock_components

    # Mock SelfCorrectingQAChain
    with patch("src.workflow.inspection.SelfCorrectingQAChain") as MockChain:
        chain_instance = MockChain.return_value
        chain_instance.generate_with_self_correction.return_value = {
            "output": "Corrected Query"
        }

        context = {"type": "general", "image_meta": {}}
        query = "Original Query"

        result = await inspect_query(
            mock_agent, query, context, kg, lats, difficulty, cache
        )

        assert result == "Corrected Query"
        cache.get.assert_called_once()
        cache.set.assert_called_once()
        difficulty.analyze_image_complexity.assert_called_once()


@pytest.mark.asyncio
async def test_inspect_answer(mock_agent, mock_components):
    kg, lats, _, cache, validator = mock_components

    with patch("src.workflow.inspection.SelfCorrectingQAChain") as MockChain:
        chain_instance = MockChain.return_value
        chain_instance.generate_with_self_correction.return_value = {
            "output": "Corrected Answer"
        }

        context = {"type": "general", "image_meta": {}}
        answer = "Original Answer"
        query = "Query"
        ocr_text = "OCR"

        result = await inspect_answer(
            mock_agent, answer, query, ocr_text, context, kg, lats, validator, cache
        )

        assert result == "Corrected Answer"
        cache.get.assert_called_once()
        cache.set.assert_called_once()
        validator.cross_validate_qa_pair.assert_called_once()
