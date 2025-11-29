from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from src.agent import GeminiAgent
from src.features.difficulty import AdaptiveDifficultyAdjuster
from src.workflow.inspection import inspect_answer, inspect_query
from typing import Any


# Mock dependencies
@pytest.fixture
def mock_agent() -> Any:
    agent = MagicMock(spec=GeminiAgent)
    agent.llm_provider = MagicMock()
    return agent


@pytest.fixture
def mock_components() -> Any:
    kg = MagicMock()
    kg.get_constraints_for_query_type.return_value = [{"description": "Rule 1"}]

    lats = MagicMock()

    difficulty = MagicMock()
    difficulty.analyze_image_complexity.return_value = {"level": "medium"}
    difficulty.analyze_text_complexity.return_value = {"level": "medium"}

    validator = MagicMock()
    validator.cross_validate_qa_pair.return_value = {"overall_score": 0.8}

    return kg, lats, difficulty, validator


@pytest.fixture
def mock_cache() -> Any:
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)  # No cache hit
    cache.set = AsyncMock()
    return cache


@pytest.mark.asyncio
async def test_inspect_query(mock_agent: Any, mock_components: Any) -> None:
    kg, lats, difficulty, _ = mock_components

    # Mock SelfCorrectingQAChain
    with patch("src.workflow.inspection.SelfCorrectingQAChain") as MockChain:
        chain_instance = MockChain.return_value
        chain_instance.generate_with_self_correction.return_value = {
            "output": "Corrected Query"
        }

        query = "Original Query"
        ocr_text = "OCR text for analysis"
        context = {"type": "general", "image_meta": {}}

        result = await inspect_query(
            mock_agent, query, ocr_text, context, kg, lats, difficulty
        )

        assert result == "Corrected Query"
        difficulty.analyze_text_complexity.assert_called_once_with(ocr_text)


@pytest.mark.asyncio
async def test_inspect_query_without_ocr(mock_agent: Any, mock_components: Any) -> None:
    """Test query inspection without OCR text (fallback to image complexity)"""
    kg, lats, difficulty, _ = mock_components

    with patch("src.workflow.inspection.SelfCorrectingQAChain") as MockChain:
        chain_instance = MockChain.return_value
        chain_instance.generate_with_self_correction.return_value = {
            "output": "Corrected Query"
        }

        query = "Original Query"
        ocr_text = ""  # No OCR text
        context = {"type": "general", "image_meta": {"text_density": 0.5}}

        result = await inspect_query(
            mock_agent, query, ocr_text, context, kg, lats, difficulty
        )

        assert result == "Corrected Query"
        difficulty.analyze_image_complexity.assert_called_once()


@pytest.mark.asyncio
async def test_inspect_query_with_cache_hit(
    mock_agent: Any, mock_components: Any, mock_cache: Any
) -> None:
    """Test query inspection with cache hit - returns original query"""
    kg, lats, difficulty, _ = mock_components
    mock_cache.get = AsyncMock(return_value=1.0)  # Cache hit (processed marker)

    with patch("src.workflow.inspection.SelfCorrectingQAChain") as MockChain:
        query = "Original Query"
        ocr_text = "OCR text"
        context = {"type": "general"}

        result = await inspect_query(
            mock_agent, query, ocr_text, context, kg, lats, difficulty, mock_cache
        )

        # When cache hits, return original query (already processed)
        assert result == "Original Query"
        # SelfCorrectingQAChain should not be called when cache hits
        MockChain.assert_not_called()


@pytest.mark.asyncio
async def test_inspect_answer(mock_agent: Any, mock_components: Any) -> None:
    kg, lats, _, validator = mock_components

    with patch("src.workflow.inspection.SelfCorrectingQAChain") as MockChain:
        chain_instance = MockChain.return_value
        chain_instance.generate_with_self_correction.return_value = {
            "output": "Corrected Answer"
        }

        answer = "Original Answer"
        query = "Query"
        ocr_text = "OCR"
        context = {"type": "general", "image_meta": {}}

        result = await inspect_answer(
            mock_agent, answer, query, ocr_text, context, kg, lats, validator
        )

        assert result == "Corrected Answer"
        validator.cross_validate_qa_pair.assert_called_once()


@pytest.mark.asyncio
async def test_inspect_answer_without_query(
    mock_agent: Any, mock_components: Any
) -> None:
    """Test answer inspection without query (cross-validation skipped)"""
    kg, lats, _, validator = mock_components

    with patch("src.workflow.inspection.SelfCorrectingQAChain") as MockChain:
        chain_instance = MockChain.return_value
        chain_instance.generate_with_self_correction.return_value = {
            "output": "Corrected Answer"
        }

        answer = "Original Answer"
        query = ""  # No query
        ocr_text = "OCR text"
        context = {"type": "general", "image_meta": {}}

        result = await inspect_answer(
            mock_agent, answer, query, ocr_text, context, kg, lats, validator
        )

        assert result == "Corrected Answer"
        # Validator should not be called when query is empty
        validator.cross_validate_qa_pair.assert_not_called()


@pytest.mark.asyncio
async def test_inspect_answer_low_coverage(
    mock_agent: Any, mock_components: Any
) -> None:
    """Test answer inspection with low keyword coverage warning"""
    kg, lats, _, validator = mock_components

    with patch("src.workflow.inspection.SelfCorrectingQAChain") as MockChain:
        chain_instance = MockChain.return_value
        chain_instance.generate_with_self_correction.return_value = {
            "output": "Corrected Answer"
        }

        answer = "Short answer"  # Short answer with few keywords
        query = "Query"
        ocr_text = "Very long OCR text with many many words keywords data"
        context = {"type": "general", "image_meta": {}}

        result = await inspect_answer(
            mock_agent, answer, query, ocr_text, context, kg, lats, validator
        )

        assert result == "Corrected Answer"


class TestAdaptiveDifficultyAdjuster:
    """Tests for text complexity analysis"""

    def test_analyze_text_complexity_empty(self) -> None:
        """Test complexity analysis with empty text"""
        kg = MagicMock()
        adjuster = AdaptiveDifficultyAdjuster(kg)

        result = adjuster.analyze_text_complexity("")

        assert result["level"] == "simple"
        assert result["word_count"] == 0
        assert result["reasoning_possible"] is False

    def test_analyze_text_complexity_simple(self) -> None:
        """Test complexity analysis with short text"""
        kg = MagicMock()
        adjuster = AdaptiveDifficultyAdjuster(kg)

        result = adjuster.analyze_text_complexity("This is a short text.")

        assert result["level"] == "simple"
        assert result["word_count"] < 100
        assert result["text_density"] < 0.4

    def test_analyze_text_complexity_medium(self) -> None:
        """Test complexity analysis with medium length text"""
        kg = MagicMock()
        adjuster = AdaptiveDifficultyAdjuster(kg)

        # Create a text with about 150 words
        words = ["word"] * 150
        text = " ".join(words)

        result = adjuster.analyze_text_complexity(text)

        assert result["level"] == "medium"
        assert result["word_count"] == 150

    def test_analyze_text_complexity_complex(self) -> None:
        """Test complexity analysis with long text"""
        kg = MagicMock()
        adjuster = AdaptiveDifficultyAdjuster(kg)

        # Create a text with 350+ words
        words = ["word"] * 350
        text = " ".join(words)

        result = adjuster.analyze_text_complexity(text)

        assert result["level"] == "complex"
        assert result["word_count"] == 350
        assert result["recommended_turns"] == 4

    def test_analyze_text_complexity_with_structure(self) -> None:
        """Test complexity analysis with structural patterns"""
        kg = MagicMock()
        adjuster = AdaptiveDifficultyAdjuster(kg)

        text = "• Item 1\n• Item 2\n• Item 3"

        result = adjuster.analyze_text_complexity(text)

        assert result["has_structure"] is True

    def test_analyze_text_complexity_with_numbers(self) -> None:
        """Test complexity analysis with numeric data"""
        kg = MagicMock()
        adjuster = AdaptiveDifficultyAdjuster(kg)

        text = "The revenue was 1,234,567 dollars, a 15.5% increase."

        result = adjuster.analyze_text_complexity(text)

        assert result["has_numbers"] is True


@pytest.mark.asyncio
async def test_inspect_query_without_kg(mock_agent: Any, mock_components: Any) -> None:
    """Test query inspection without knowledge graph (returns original query)."""
    _, lats, difficulty, _ = mock_components

    query = "Original Query"
    ocr_text = "OCR text"
    context = {"type": "general"}

    result = await inspect_query(
        mock_agent, query, ocr_text, context, kg=None, lats=lats, difficulty=difficulty
    )

    assert result == "Original Query"


@pytest.mark.asyncio
async def test_inspect_query_with_cache_miss_and_save(
    mock_agent: Any, mock_components: Any, mock_cache: Any
) -> None:
    """Test query inspection caches result after processing."""
    kg, lats, difficulty, _ = mock_components

    with patch("src.workflow.inspection.SelfCorrectingQAChain") as MockChain:
        chain_instance = MockChain.return_value
        chain_instance.generate_with_self_correction.return_value = {
            "output": "Corrected Query"
        }

        query = "Original Query"
        ocr_text = "OCR text"
        context = {"type": "general"}

        result = await inspect_query(
            mock_agent, query, ocr_text, context, kg, lats, difficulty, mock_cache
        )

        assert result == "Corrected Query"
        # Verify cache was set after processing
        mock_cache.set.assert_called_once()


@pytest.mark.asyncio
async def test_inspect_query_with_rules(mock_agent: Any, mock_components: Any) -> None:
    """Test query inspection with rules from knowledge graph."""
    kg, lats, difficulty, _ = mock_components
    kg.get_constraints_for_query_type.return_value = [
        {"description": "Rule 1"},
        {"description": "Rule 2"},
    ]

    with patch("src.workflow.inspection.SelfCorrectingQAChain") as MockChain:
        chain_instance = MockChain.return_value
        chain_instance.generate_with_self_correction.return_value = {
            "output": "Corrected Query"
        }

        query = "Original Query"
        ocr_text = "OCR text"
        context = {"type": "reasoning"}

        result = await inspect_query(
            mock_agent, query, ocr_text, context, kg, lats, difficulty
        )

        assert result == "Corrected Query"
        kg.get_constraints_for_query_type.assert_called_once_with("reasoning")


@pytest.mark.asyncio
async def test_inspect_answer_without_kg(mock_agent: Any, mock_components: Any) -> None:
    """Test answer inspection without knowledge graph (returns original answer)."""
    _, lats, _, validator = mock_components

    answer = "Original Answer"
    query = "Query"
    ocr_text = "OCR text"
    context = {"type": "general"}

    result = await inspect_answer(
        mock_agent,
        answer,
        query,
        ocr_text,
        context,
        kg=None,
        lats=lats,
        validator=validator,
    )

    # Without kg, original answer is returned
    assert result == "Original Answer"


@pytest.mark.asyncio
async def test_inspect_answer_with_cache_hit(
    mock_agent: Any, mock_components: Any, mock_cache: Any
) -> None:
    """Test answer inspection with cache hit returns original answer."""
    kg, lats, _, validator = mock_components
    mock_cache.get = AsyncMock(return_value=1.0)

    with patch("src.workflow.inspection.SelfCorrectingQAChain") as MockChain:
        answer = "Original Answer"
        query = "Query"
        ocr_text = "OCR text"
        context = {"type": "general"}

        result = await inspect_answer(
            mock_agent,
            answer,
            query,
            ocr_text,
            context,
            kg,
            lats,
            validator,
            mock_cache,
        )

        assert result == "Original Answer"
        MockChain.assert_not_called()


@pytest.mark.asyncio
async def test_inspect_answer_with_cache_save(
    mock_agent: Any, mock_components: Any, mock_cache: Any
) -> None:
    """Test answer inspection caches result after processing."""
    kg, lats, _, validator = mock_components

    with patch("src.workflow.inspection.SelfCorrectingQAChain") as MockChain:
        chain_instance = MockChain.return_value
        chain_instance.generate_with_self_correction.return_value = {
            "output": "Corrected Answer"
        }

        answer = "Original Answer"
        query = "Query"
        ocr_text = "OCR text"
        context = {"type": "general"}

        result = await inspect_answer(
            mock_agent,
            answer,
            query,
            ocr_text,
            context,
            kg,
            lats,
            validator,
            mock_cache,
        )

        assert result == "Corrected Answer"
        mock_cache.set.assert_called_once()


@pytest.mark.asyncio
async def test_inspect_answer_validation_failure(
    mock_agent: Any, mock_components: Any
) -> None:
    """Test answer inspection with validation failure."""
    kg, lats, _, validator = mock_components
    validator.cross_validate_qa_pair.return_value = {"overall_score": 0.5}  # Below 0.7

    with patch("src.workflow.inspection.SelfCorrectingQAChain") as MockChain:
        chain_instance = MockChain.return_value
        chain_instance.generate_with_self_correction.return_value = {
            "output": "Corrected Answer"
        }

        answer = "Original Answer"
        query = "Query"
        ocr_text = "OCR text"
        context = {"type": "general", "image_meta": {}}

        result = await inspect_answer(
            mock_agent, answer, query, ocr_text, context, kg, lats, validator
        )

        assert result == "Corrected Answer"
        # Validation warning should be set in context
        assert context.get("validation_warning")  # truthy check instead of identity


@pytest.mark.asyncio
async def test_inspect_query_with_context_none(
    mock_agent: Any, mock_components: Any
) -> None:
    """Test query inspection with None context."""
    kg, lats, difficulty, _ = mock_components

    with patch("src.workflow.inspection.SelfCorrectingQAChain") as MockChain:
        chain_instance = MockChain.return_value
        chain_instance.generate_with_self_correction.return_value = {
            "output": "Corrected Query"
        }

        query = "Original Query"
        ocr_text = "OCR text"

        result = await inspect_query(
            mock_agent,
            query,
            ocr_text,
            context=None,
            kg=kg,
            lats=lats,
            difficulty=difficulty,
        )

        assert result == "Corrected Query"


@pytest.mark.asyncio
async def test_inspect_answer_with_context_none(
    mock_agent: Any, mock_components: Any
) -> None:
    """Test answer inspection with None context."""
    kg, lats, _, validator = mock_components

    with patch("src.workflow.inspection.SelfCorrectingQAChain") as MockChain:
        chain_instance = MockChain.return_value
        chain_instance.generate_with_self_correction.return_value = {
            "output": "Corrected Answer"
        }

        answer = "Original Answer"
        query = "Query"
        ocr_text = "OCR text"

        result = await inspect_answer(
            mock_agent,
            answer,
            query,
            ocr_text,
            context=None,
            kg=kg,
            lats=lats,
            validator=validator,
        )

        assert result == "Corrected Answer"


@pytest.mark.asyncio
async def test_inspect_answer_without_ocr_text(
    mock_agent: Any, mock_components: Any
) -> None:
    """Test answer inspection without OCR text (keyword verification skipped)."""
    kg, lats, _, validator = mock_components

    with patch("src.workflow.inspection.SelfCorrectingQAChain") as MockChain:
        chain_instance = MockChain.return_value
        chain_instance.generate_with_self_correction.return_value = {
            "output": "Corrected Answer"
        }

        answer = "Original Answer"
        query = "Query"
        ocr_text = ""  # No OCR text
        context = {"type": "general"}

        result = await inspect_answer(
            mock_agent, answer, query, ocr_text, context, kg, lats, validator
        )

        assert result == "Corrected Answer"
