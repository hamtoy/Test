"""Comprehensive tests for src/web/routers/workspace_generation.py to improve coverage to 80%+."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.web.routers.workspace_generation import (
    _evaluate_answer_quality,
    _generate_lats_answer,
    _lats_evaluate_answer,
    api_generate_answer_from_query,
    api_generate_query_from_answer,
)


@pytest.fixture
def mock_agent():
    """Mock GeminiAgent."""
    agent = AsyncMock()
    agent._create_generative_model = MagicMock()
    agent._call_api_with_retry = AsyncMock(return_value="Generated answer")
    agent.rewrite_best_answer = AsyncMock(return_value="Rewritten answer")
    agent.generate_query = AsyncMock(return_value=["Generated query"])
    return agent


@pytest.fixture
def mock_kg():
    """Mock KnowledgeGraph."""
    kg = MagicMock()
    kg.get_rules_for_query_type = MagicMock(return_value=[])
    return kg


@pytest.fixture
def mock_config():
    """Mock AppConfig."""
    config = MagicMock()
    config.workspace_timeout = 30
    config.temperature = 0.7
    config.max_output_tokens = 8192
    return config


class TestApiGenerateAnswerFromQuery:
    """Test api_generate_answer_from_query endpoint."""

    @pytest.mark.asyncio
    async def test_generate_answer_success(self, mock_agent, mock_kg, mock_config):
        """Test successful answer generation."""
        with patch("src.web.routers.workspace_generation._get_agent", return_value=mock_agent):
            with patch("src.web.routers.workspace_generation._get_kg", return_value=mock_kg):
                with patch("src.web.routers.workspace_generation._get_config", return_value=mock_config):
                    with patch("src.web.routers.workspace_generation.RuleLoader") as mock_rule_loader:
                        mock_loader = MagicMock()
                        mock_loader.get_rules_for_type.return_value = ["Rule 1", "Rule 2"]
                        mock_rule_loader.return_value = mock_loader

                        body = {
                            "query": "Test query",
                            "ocr_text": "Test OCR text",
                            "query_type": "explanation",
                        }

                        result = await api_generate_answer_from_query(body)

                        assert "query" in result
                        assert "answer" in result
                        assert result["query"] == "Test query"

    @pytest.mark.asyncio
    async def test_generate_answer_retries_on_violations(self, mock_agent, mock_kg, mock_config):
        """Test answer generation retries when violations found."""
        mock_agent.rewrite_best_answer = AsyncMock(
            side_effect=["Answer with **markdown**", "Clean answer"]
        )

        with patch("src.web.routers.workspace_generation._get_agent", return_value=mock_agent):
            with patch("src.web.routers.workspace_generation._get_kg", return_value=mock_kg):
                with patch("src.web.routers.workspace_generation._get_config", return_value=mock_config):
                    with patch("src.web.routers.workspace_generation.RuleLoader") as mock_rule_loader:
                        mock_loader = MagicMock()
                        mock_loader.get_rules_for_type.return_value = []
                        mock_rule_loader.return_value = mock_loader

                        with patch("src.web.routers.workspace_generation.find_violations") as mock_violations:
                            mock_violations.side_effect = [
                                [{"type": "markdown"}],  # First answer has violation
                                [],  # Second answer is clean
                            ]

                            body = {
                                "query": "Test query",
                                "ocr_text": "Test OCR",
                            }

                            result = await api_generate_answer_from_query(body)

                            # Should have retried once
                            assert mock_agent.rewrite_best_answer.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_answer_handles_timeout(self, mock_agent, mock_kg, mock_config):
        """Test answer generation handles timeout."""
        mock_agent.rewrite_best_answer = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch("src.web.routers.workspace_generation._get_agent", return_value=mock_agent):
            with patch("src.web.routers.workspace_generation._get_kg", return_value=mock_kg):
                with patch("src.web.routers.workspace_generation._get_config", return_value=mock_config):
                    with patch("src.web.routers.workspace_generation.RuleLoader"):
                        body = {"query": "Test", "ocr_text": "Test"}

                        with pytest.raises(HTTPException) as exc_info:
                            await api_generate_answer_from_query(body)

                        assert exc_info.value.status_code == 504

    @pytest.mark.asyncio
    async def test_generate_answer_requires_agent(self):
        """Test answer generation requires agent."""
        with patch("src.web.routers.workspace_generation._get_agent", return_value=None):
            body = {"query": "Test", "ocr_text": "Test"}

            with pytest.raises(HTTPException) as exc_info:
                await api_generate_answer_from_query(body)

            assert exc_info.value.status_code == 500


class TestApiGenerateQueryFromAnswer:
    """Test api_generate_query_from_answer endpoint."""

    @pytest.mark.asyncio
    async def test_generate_query_success(self, mock_agent, mock_config):
        """Test successful query generation."""
        with patch("src.web.routers.workspace_generation._get_agent", return_value=mock_agent):
            with patch("src.web.routers.workspace_generation._get_config", return_value=mock_config):
                body = {
                    "answer": "Test answer",
                    "ocr_text": "Test OCR",
                }

                result = await api_generate_query_from_answer(body)

                assert "query" in result
                assert "answer" in result
                assert result["answer"] == "Test answer"

    @pytest.mark.asyncio
    async def test_generate_query_handles_timeout(self, mock_agent, mock_config):
        """Test query generation handles timeout."""
        mock_agent.generate_query = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch("src.web.routers.workspace_generation._get_agent", return_value=mock_agent):
            with patch("src.web.routers.workspace_generation._get_config", return_value=mock_config):
                body = {"answer": "Test"}

                with pytest.raises(HTTPException) as exc_info:
                    await api_generate_query_from_answer(body)

                assert exc_info.value.status_code == 504


class TestEvaluateAnswerQuality:
    """Test _evaluate_answer_quality function."""

    @pytest.mark.asyncio
    async def test_evaluate_short_answer(self):
        """Test evaluation of too-short answer."""
        score = await _evaluate_answer_quality("Hi", "Test OCR", "explanation")

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_evaluate_good_answer(self):
        """Test evaluation of good quality answer."""
        answer = "2023년 매출은 100억원, 2024년 매출은 150억원으로 50% 증가했습니다."
        ocr_text = "2023: 100억, 2024: 150억"

        score = await _evaluate_answer_quality(answer, ocr_text)

        assert score > 0.5

    @pytest.mark.asyncio
    async def test_evaluate_with_forbidden_patterns(self):
        """Test evaluation penalizes forbidden patterns."""
        answer = "Answer with **bold** and - bullet points"
        ocr_text = "Test"

        score = await _evaluate_answer_quality(answer, ocr_text)

        # Should be penalized for forbidden patterns
        assert score < 1.0


class TestGenerateLatsAnswer:
    """Test _generate_lats_answer function."""

    @pytest.mark.asyncio
    async def test_generate_lats_answer_success(self, mock_agent):
        """Test LATS answer generation."""
        mock_model = MagicMock()
        mock_agent._create_generative_model.return_value = mock_model
        mock_agent._call_api_with_retry.return_value = "Generated answer text"

        with patch("src.web.routers.workspace_generation._get_agent", return_value=mock_agent):
            with patch("src.web.routers.workspace_generation._evaluate_answer_quality") as mock_eval:
                mock_eval.return_value = 0.8  # High quality score

                answer, meta = await _generate_lats_answer(
                    "Test query",
                    "Test OCR text with numbers 100 and 200",
                    "explanation",
                )

                assert isinstance(answer, str)
                assert isinstance(meta, dict)
                assert "candidates" in meta

    @pytest.mark.asyncio
    async def test_generate_lats_returns_empty_on_low_quality(self, mock_agent):
        """Test LATS returns empty when all candidates are low quality."""
        mock_agent._create_generative_model.return_value = MagicMock()
        mock_agent._call_api_with_retry.return_value = "Short"

        with patch("src.web.routers.workspace_generation._get_agent", return_value=mock_agent):
            with patch("src.web.routers.workspace_generation._evaluate_answer_quality", return_value=0.3):
                answer, meta = await _generate_lats_answer("Query", "OCR", "explanation")

                assert answer == ""
                assert meta["reason"] == "all_low_quality"


class TestLatsEvaluateAnswer:
    """Test _lats_evaluate_answer function."""

    @pytest.mark.asyncio
    async def test_lats_evaluate_empty_answer(self):
        """Test LATS evaluation of empty answer."""
        mock_node = MagicMock()
        mock_node.state.current_answer = ""
        mock_node.state.ocr_text = "Test OCR"

        score = await _lats_evaluate_answer(mock_node)

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_lats_evaluate_good_answer(self, mock_kg):
        """Test LATS evaluation of quality answer."""
        mock_node = MagicMock()
        mock_node.state.current_answer = "This is a good answer with proper length and 100 and 200"
        mock_node.state.ocr_text = "OCR text with 100 and 200"
        mock_node.state.metadata = {"query_type": "explanation"}

        with patch("src.web.routers.workspace_generation._get_kg", return_value=mock_kg):
            score = await _lats_evaluate_answer(mock_node)

            assert score > 0.0
            assert score <= 1.0
