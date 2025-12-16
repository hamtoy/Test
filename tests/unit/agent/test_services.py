"""Tests for agent services module."""
# mypy: ignore-errors

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import ValidationError

from src.agent.services import QueryGeneratorService, ResponseEvaluatorService
from src.config.exceptions import APIRateLimitError


class TestQueryGeneratorService:
    """Tests for QueryGeneratorService."""

    def test_init(self):
        """Test service initialization."""
        mock_agent = Mock()
        service = QueryGeneratorService(mock_agent)

        assert service.agent == mock_agent

    @pytest.mark.asyncio
    @patch("src.agent.services.QueryResult")
    async def test_generate_query_success(self, mock_query_result):
        """Test successful query generation."""
        # Setup mocks
        mock_agent = Mock()
        mock_agent._api_call_counter = Mock()
        mock_agent._api_call_counter.add = Mock()
        mock_agent.jinja_env = Mock()
        mock_agent.logger = Mock()
        mock_agent._create_generative_model = Mock()
        mock_agent.context_manager = Mock()
        mock_agent.retry_handler = Mock()
        mock_agent.retry_handler.call = AsyncMock(
            return_value='{"queries": ["Query 1", "Query 2"]}'
        )
        mock_agent._is_rate_limit_error = Mock(return_value=False)

        # Setup template
        mock_template = Mock()
        mock_template.render = Mock(return_value="rendered prompt")
        mock_agent.jinja_env.get_template = Mock(return_value=mock_template)

        # Setup query result
        mock_result = Mock()
        mock_result.queries = ["Query 1", "Query 2"]
        mock_query_result.model_validate_json = Mock(return_value=mock_result)
        mock_query_result.model_json_schema = Mock(return_value={"type": "object"})

        service = QueryGeneratorService(mock_agent)

        # Execute
        result = await service.generate_query(
            ocr_text="Sample OCR text",
            user_intent="Find information",
            cached_content=None,
            template_name=None,
            query_type="explanation",
            kg=None,
            constraints=None,
        )

        # Verify
        assert result == ["Query 1", "Query 2"]
        mock_agent._api_call_counter.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_query_empty_response(self):
        """Test query generation with empty response."""
        mock_agent = Mock()
        mock_agent._api_call_counter = Mock()
        mock_agent._api_call_counter.add = Mock()
        mock_agent.jinja_env = Mock()
        mock_agent.logger = Mock()
        mock_agent._create_generative_model = Mock()
        mock_agent.context_manager = Mock()
        mock_agent.retry_handler = Mock()
        mock_agent.retry_handler.call = AsyncMock(return_value="")

        mock_template = Mock()
        mock_template.render = Mock(return_value="prompt")
        mock_agent.jinja_env.get_template = Mock(return_value=mock_template)

        service = QueryGeneratorService(mock_agent)

        result = await service.generate_query(
            ocr_text="text",
            user_intent=None,
            cached_content=None,
            template_name=None,
            query_type="explanation",
            kg=None,
            constraints=None,
        )

        assert result == []
        mock_agent.logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_generate_query_validation_error(self):
        """Test query generation with validation error."""
        mock_agent = Mock()
        mock_agent._api_call_counter = Mock()
        mock_agent._api_call_counter.add = Mock()
        mock_agent.jinja_env = Mock()
        mock_agent.logger = Mock()
        mock_agent._create_generative_model = Mock()
        mock_agent.context_manager = Mock()
        mock_agent.retry_handler = Mock()
        mock_agent.retry_handler.call = AsyncMock(return_value='{"invalid": "json"}')
        mock_agent._is_rate_limit_error = Mock(return_value=False)

        mock_template = Mock()
        mock_template.render = Mock(return_value="prompt")
        mock_agent.jinja_env.get_template = Mock(return_value=mock_template)

        service = QueryGeneratorService(mock_agent)

        with patch(
            "src.agent.services.QueryResult.model_validate_json"
        ) as mock_validate:
            mock_validate.side_effect = ValidationError.from_exception_data(
                "Test",
                [
                    {
                        "type": "value_error",
                        "loc": ("test",),
                        "msg": "Test error",
                        "input": {},
                        "ctx": {"error": "test"},
                    }
                ],
            )

            result = await service.generate_query(
                ocr_text="text",
                user_intent=None,
                cached_content=None,
                template_name=None,
                query_type="explanation",
                kg=None,
                constraints=None,
            )

            assert result == []

    @pytest.mark.asyncio
    async def test_generate_query_rate_limit_error(self):
        """Test query generation with rate limit error."""
        mock_agent = Mock()
        mock_agent._api_call_counter = Mock()
        mock_agent._api_call_counter.add = Mock()
        mock_agent.jinja_env = Mock()
        mock_agent.logger = Mock()
        mock_agent._create_generative_model = Mock()
        mock_agent.context_manager = Mock()
        mock_agent.retry_handler = Mock()

        rate_limit_exception = Exception("429 Rate Limit")
        mock_agent.retry_handler.call = AsyncMock(side_effect=rate_limit_exception)
        mock_agent._is_rate_limit_error = Mock(return_value=True)

        mock_template = Mock()
        mock_template.render = Mock(return_value="prompt")
        mock_agent.jinja_env.get_template = Mock(return_value=mock_template)

        service = QueryGeneratorService(mock_agent)

        with pytest.raises(APIRateLimitError):
            await service.generate_query(
                ocr_text="text",
                user_intent=None,
                cached_content=None,
                template_name=None,
                query_type="explanation",
                kg=None,
                constraints=None,
            )

    @pytest.mark.asyncio
    async def test_generate_query_with_constraints(self):
        """Test query generation with provided constraints."""
        mock_agent = Mock()
        mock_agent._api_call_counter = Mock()
        mock_agent._api_call_counter.add = Mock()
        mock_agent.jinja_env = Mock()
        mock_agent.logger = Mock()
        mock_agent._create_generative_model = Mock()
        mock_agent.context_manager = Mock()
        mock_agent.retry_handler = Mock()
        mock_agent.retry_handler.call = AsyncMock(
            return_value='{"queries": ["Query 1"]}'
        )
        mock_agent._is_rate_limit_error = Mock(return_value=False)

        mock_template = Mock()
        mock_template.render = Mock(return_value="prompt")
        mock_agent.jinja_env.get_template = Mock(return_value=mock_template)

        service = QueryGeneratorService(mock_agent)

        constraints = [{"category": "query", "priority": 10, "text": "Constraint 1"}]

        with patch("src.agent.services.QueryResult") as mock_qr:
            mock_result = Mock()
            mock_result.queries = ["Query 1"]
            mock_qr.model_validate_json = Mock(return_value=mock_result)
            mock_qr.model_json_schema = Mock(return_value={})

            result = await service.generate_query(
                ocr_text="text",
                user_intent=None,
                cached_content=None,
                template_name=None,
                query_type="explanation",
                kg=None,
                constraints=constraints,
            )

            assert result == ["Query 1"]


class TestResponseEvaluatorService:
    """Tests for ResponseEvaluatorService."""

    def test_init(self):
        """Test service initialization."""
        mock_agent = Mock()
        service = ResponseEvaluatorService(mock_agent)

        assert service.agent == mock_agent

    @pytest.mark.asyncio
    async def test_evaluate_responses_empty_query(self):
        """Test evaluation with empty query."""
        mock_agent = Mock()
        service = ResponseEvaluatorService(mock_agent)

        result = await service.evaluate_responses(
            ocr_text="text",
            query="",
            candidates={},
            cached_content=None,
            query_type="explanation",
            kg=None,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_evaluate_responses_success(self):
        """Test successful response evaluation."""
        mock_agent = Mock()
        mock_agent._api_call_counter = Mock()
        mock_agent._api_call_counter.add = Mock()
        mock_agent.jinja_env = Mock()
        mock_agent.logger = Mock()
        mock_agent._create_generative_model = Mock()
        mock_agent.context_manager = Mock()
        mock_agent.retry_handler = Mock()
        mock_agent.retry_handler.call = AsyncMock(
            return_value='{"best_candidate": "A", "evaluations": [{"candidate_id": "A", "score": 95, "reason": "Best answer"}]}'
        )
        mock_agent._is_rate_limit_error = Mock(return_value=False)

        mock_template = Mock()
        mock_template.render = Mock(return_value="prompt")
        mock_agent.jinja_env.get_template = Mock(return_value=mock_template)

        service = ResponseEvaluatorService(mock_agent)

        candidates = {"A": "Answer A", "B": "Answer B"}

        with patch(
            "src.agent.services.response_evaluator.EvaluationResultSchema"
        ) as mock_eval:
            mock_result = Mock()
            mock_result.best_candidate = "A"
            mock_eval.model_validate_json = Mock(return_value=mock_result)
            mock_eval.model_json_schema = Mock(return_value={})

            result = await service.evaluate_responses(
                ocr_text="text",
                query="What is this?",
                candidates=candidates,
                cached_content=None,
                query_type="explanation",
                kg=None,
            )

            assert result == mock_result
            mock_agent._api_call_counter.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_responses_with_kg(self):
        """Test evaluation with knowledge graph."""
        mock_agent = Mock()
        mock_agent._api_call_counter = Mock()
        mock_agent._api_call_counter.add = Mock()
        mock_agent.jinja_env = Mock()
        mock_agent.logger = Mock()
        mock_agent._create_generative_model = Mock()
        mock_agent.context_manager = Mock()
        mock_agent.retry_handler = Mock()
        mock_agent.retry_handler.call = AsyncMock(
            return_value='{"best_candidate": "A", "evaluations": [{"candidate_id": "A", "score": 90, "reason": "Good answer"}]}'
        )
        mock_agent._is_rate_limit_error = Mock(return_value=False)

        mock_template = Mock()
        mock_template.render = Mock(return_value="prompt")
        mock_agent.jinja_env.get_template = Mock(return_value=mock_template)

        mock_kg = Mock()
        mock_kg.find_relevant_rules = Mock(return_value=["Rule 1", "Rule 2"])
        mock_kg.get_constraints_for_query_type = Mock(return_value=[])

        service = ResponseEvaluatorService(mock_agent)

        with patch(
            "src.agent.services.response_evaluator.EvaluationResultSchema"
        ) as mock_eval:
            mock_result = Mock()
            mock_eval.model_validate_json = Mock(return_value=mock_result)
            mock_eval.model_json_schema = Mock(return_value={})

            result = await service.evaluate_responses(
                ocr_text="text",
                query="Query",
                candidates={"A": "Answer"},
                cached_content=None,
                query_type="explanation",
                kg=mock_kg,
            )

            assert result is not None
            mock_kg.find_relevant_rules.assert_called()
