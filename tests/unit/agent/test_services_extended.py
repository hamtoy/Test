"""Extended tests for agent services module to increase coverage."""
# mypy: ignore-errors

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import ValidationError

from src.agent.services import (
    QueryGeneratorService,
    ResponseEvaluatorService,
    RewriterService,
)
from src.config.exceptions import APIRateLimitError, ValidationFailedError


class TestQueryGeneratorServiceExtended:
    """Extended tests for QueryGeneratorService."""

    @pytest.mark.asyncio
    async def test_generate_query_with_constraints(self):
        """Test query generation with Neo4j constraints."""
        mock_agent = Mock()
        mock_agent._api_call_counter = Mock()
        mock_agent._api_call_counter.add = Mock()
        mock_agent.jinja_env = Mock()
        mock_agent.logger = Mock()
        mock_agent._create_generative_model = Mock()
        mock_agent.context_manager = Mock()
        mock_agent.retry_handler = Mock()
        mock_agent.retry_handler.call = AsyncMock(
            return_value='{"queries": ["Q1", "Q2"]}'
        )
        mock_agent._is_rate_limit_error = Mock(return_value=False)

        mock_template = Mock()
        mock_template.render = Mock(return_value="prompt")
        mock_agent.jinja_env.get_template = Mock(return_value=mock_template)

        with patch("src.agent.services.QueryResult") as mock_query_result:
            mock_result = Mock()
            mock_result.queries = ["Q1", "Q2"]
            mock_query_result.model_validate_json = Mock(return_value=mock_result)
            mock_query_result.model_json_schema = Mock(return_value={})

            service = QueryGeneratorService(mock_agent)

            constraints = [
                {"description": "Must be specific", "priority": 1},
                {"description": "Use numbers", "priority": 2},
            ]

            result = await service.generate_query(
                ocr_text="Sample text",
                user_intent="Find data",
                cached_content=None,
                template_name=None,
                query_type="table_summary",
                kg=None,
                constraints=constraints,
            )

            assert result == ["Q1", "Q2"]

    @pytest.mark.asyncio
    async def test_generate_query_with_kg(self):
        """Test query generation with knowledge graph."""
        mock_agent = Mock()
        mock_agent._api_call_counter = Mock()
        mock_agent._api_call_counter.add = Mock()
        mock_agent.jinja_env = Mock()
        mock_agent.logger = Mock()
        mock_agent._create_generative_model = Mock()
        mock_agent.context_manager = Mock()
        mock_agent.retry_handler = Mock()
        mock_agent.retry_handler.call = AsyncMock(
            return_value='{"queries": ["Query"]}'
        )
        mock_agent._is_rate_limit_error = Mock(return_value=False)

        mock_template = Mock()
        mock_template.render = Mock(return_value="prompt")
        mock_agent.jinja_env.get_template = Mock(return_value=mock_template)

        # Mock KG
        mock_kg = Mock()
        mock_kg.get_constraints_for_query_type = Mock(
            return_value=[{"description": "constraint", "category": "query", "priority": 1}]
        )
        mock_kg.find_relevant_rules = Mock(return_value=["Rule 1", "Rule 2"])
        mock_kg.get_formatting_rules = Mock(return_value="Format rules")

        with patch("src.agent.services.QueryResult") as mock_query_result, \
             patch("src.qa.rag_system.QAKnowledgeGraph", return_value=mock_kg):
            mock_result = Mock()
            mock_result.queries = ["Query"]
            mock_query_result.model_validate_json = Mock(return_value=mock_result)
            mock_query_result.model_json_schema = Mock(return_value={})

            service = QueryGeneratorService(mock_agent)

            result = await service.generate_query(
                ocr_text="Text",
                user_intent=None,
                cached_content=None,
                template_name=None,
                query_type="explanation",
                kg=mock_kg,
                constraints=None,
            )

            assert result == ["Query"]
            mock_kg.get_constraints_for_query_type.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_query_rate_limit_error(self):
        """Test handling of rate limit errors."""
        mock_agent = Mock()
        mock_agent._api_call_counter = Mock()
        mock_agent._api_call_counter.add = Mock()
        mock_agent.jinja_env = Mock()
        mock_agent.logger = Mock()
        mock_agent._create_generative_model = Mock()
        mock_agent.context_manager = Mock()
        mock_agent.retry_handler = Mock()
        mock_agent.retry_handler.call = AsyncMock(
            side_effect=Exception("Rate limit exceeded")
        )
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
    async def test_generate_query_validation_error(self):
        """Test handling of validation errors."""
        mock_agent = Mock()
        mock_agent._api_call_counter = Mock()
        mock_agent._api_call_counter.add = Mock()
        mock_agent.jinja_env = Mock()
        mock_agent.logger = Mock()
        mock_agent._create_generative_model = Mock()
        mock_agent.context_manager = Mock()
        mock_agent.retry_handler = Mock()
        mock_agent.retry_handler.call = AsyncMock(
            return_value='{"invalid": "json"}'
        )

        mock_template = Mock()
        mock_template.render = Mock(return_value="prompt")
        mock_agent.jinja_env.get_template = Mock(return_value=mock_template)

        with patch("src.agent.services.QueryResult") as mock_query_result:
            mock_query_result.model_validate_json = Mock(
                side_effect=ValidationError.from_exception_data("test", [])
            )
            mock_query_result.model_json_schema = Mock(return_value={})

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
    async def test_generate_query_json_decode_error(self):
        """Test handling of JSON decode errors."""
        mock_agent = Mock()
        mock_agent._api_call_counter = Mock()
        mock_agent._api_call_counter.add = Mock()
        mock_agent.jinja_env = Mock()
        mock_agent.logger = Mock()
        mock_agent._create_generative_model = Mock()
        mock_agent.context_manager = Mock()
        mock_agent.retry_handler = Mock()
        mock_agent.retry_handler.call = AsyncMock(
            return_value='{"queries": ["Q1"]'  # Invalid JSON
        )

        mock_template = Mock()
        mock_template.render = Mock(return_value="prompt")
        mock_agent.jinja_env.get_template = Mock(return_value=mock_template)

        with patch("src.agent.services.QueryResult") as mock_query_result:
            mock_query_result.model_validate_json = Mock(
                side_effect=json.JSONDecodeError("error", "doc", 0)
            )
            mock_query_result.model_json_schema = Mock(return_value={})

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


class TestResponseEvaluatorServiceExtended:
    """Extended tests for ResponseEvaluatorService."""

    @pytest.mark.asyncio
    async def test_evaluate_responses_empty_query(self):
        """Test evaluation with empty query."""
        mock_agent = Mock()
        service = ResponseEvaluatorService(mock_agent)

        result = await service.evaluate_responses(
            ocr_text="text",
            query="",
            candidates={"a": "Answer A"},
            cached_content=None,
            query_type="explanation",
            kg=None,
        )

        assert result is None

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
            return_value='{"best_answer": "a", "score": 0.9}'
        )
        mock_agent._is_rate_limit_error = Mock(return_value=False)

        mock_template = Mock()
        mock_template.render = Mock(return_value="system prompt")
        mock_agent.jinja_env.get_template = Mock(return_value=mock_template)

        mock_kg = Mock()
        mock_kg.get_constraints_for_query_type = Mock(
            return_value=[{"description": "constraint"}]
        )
        mock_kg.find_relevant_rules = Mock(return_value=["rule1"])
        mock_kg.get_formatting_rules = Mock(return_value="formatting")

        with patch("src.agent.services.EvaluationResultSchema") as mock_eval:
            mock_result = Mock()
            mock_eval.model_validate_json = Mock(return_value=mock_result)

            service = ResponseEvaluatorService(mock_agent)

            result = await service.evaluate_responses(
                ocr_text="text",
                query="query",
                candidates={"a": "Answer A", "b": "Answer B"},
                cached_content=None,
                query_type="explanation",
                kg=mock_kg,
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_evaluate_responses_rate_limit(self):
        """Test evaluation with rate limit error."""
        mock_agent = Mock()
        mock_agent._api_call_counter = Mock()
        mock_agent._api_call_counter.add = Mock()
        mock_agent.jinja_env = Mock()
        mock_agent.logger = Mock()
        mock_agent._create_generative_model = Mock()
        mock_agent.context_manager = Mock()
        mock_agent.retry_handler = Mock()
        mock_agent.retry_handler.call = AsyncMock(
            side_effect=Exception("Rate limit")
        )
        mock_agent._is_rate_limit_error = Mock(return_value=True)

        mock_template = Mock()
        mock_template.render = Mock(return_value="prompt")
        mock_agent.jinja_env.get_template = Mock(return_value=mock_template)

        service = ResponseEvaluatorService(mock_agent)

        with pytest.raises(APIRateLimitError):
            await service.evaluate_responses(
                ocr_text="text",
                query="query",
                candidates={"a": "Answer"},
                cached_content=None,
                query_type="explanation",
                kg=None,
            )

    @pytest.mark.asyncio
    async def test_evaluate_responses_validation_error(self):
        """Test evaluation with validation error."""
        mock_agent = Mock()
        mock_agent._api_call_counter = Mock()
        mock_agent._api_call_counter.add = Mock()
        mock_agent.jinja_env = Mock()
        mock_agent.logger = Mock()
        mock_agent._create_generative_model = Mock()
        mock_agent.context_manager = Mock()
        mock_agent.retry_handler = Mock()
        mock_agent.retry_handler.call = AsyncMock(
            return_value='invalid json'
        )

        mock_template = Mock()
        mock_template.render = Mock(return_value="prompt")
        mock_agent.jinja_env.get_template = Mock(return_value=mock_template)

        with patch("src.agent.services.EvaluationResultSchema") as mock_eval:
            mock_eval.model_validate_json = Mock(
                side_effect=ValidationError.from_exception_data("test", [])
            )

            service = ResponseEvaluatorService(mock_agent)

            with pytest.raises(ValidationFailedError):
                await service.evaluate_responses(
                    ocr_text="text",
                    query="query",
                    candidates={"a": "Answer"},
                    cached_content=None,
                    query_type="explanation",
                    kg=None,
                )


class TestRewriterService:
    """Tests for RewriterService."""

    @pytest.mark.asyncio
    async def test_rewrite_basic(self):
        """Test basic answer rewriting."""
        mock_agent = Mock()
        mock_agent.logger = Mock()
        mock_agent._create_generative_model = Mock()
        mock_agent.context_manager = Mock()
        mock_agent.retry_handler = Mock()
        mock_agent.retry_handler.call = AsyncMock(
            return_value="Rewritten answer"
        )
        mock_agent._is_rate_limit_error = Mock(return_value=False)
        mock_agent.config = Mock()
        mock_agent.config.target_length = None

        mock_template = Mock()
        mock_template.render = Mock(return_value="system prompt")
        mock_agent.jinja_env = Mock()
        mock_agent.jinja_env.get_template = Mock(return_value=mock_template)

        service = RewriterService(mock_agent)

        result = await service.rewrite_best_answer(
            user_query="Query",
            selected_answer="Original answer",
            edit_request=None,
            formatting_rules=None,
            cached_content=None,
            query_type="explanation",
        )

        assert result == "Rewritten answer"

    @pytest.mark.asyncio
    async def test_rewrite_with_kg_constraints(self):
        """Test rewriting with KG constraints."""
        mock_agent = Mock()
        mock_agent.logger = Mock()
        mock_agent._create_generative_model = Mock()
        mock_agent.context_manager = Mock()
        mock_agent.retry_handler = Mock()
        mock_agent.retry_handler.call = AsyncMock(
            return_value='{"rewritten_answer": "New answer"}'
        )
        mock_agent._is_rate_limit_error = Mock(return_value=False)
        mock_agent.config = Mock()
        mock_agent.config.target_length = 500

        mock_template = Mock()
        mock_template.render = Mock(return_value="prompt")
        mock_agent.jinja_env = Mock()
        mock_agent.jinja_env.get_template = Mock(return_value=mock_template)

        mock_kg = Mock()
        mock_kg.get_constraints_for_query_type = Mock(
            return_value=[
                {"description": "Use numbers", "priority": 2},
                {"description": "Be specific", "priority": 1},
            ]
        )
        mock_kg.find_relevant_rules = Mock(return_value=["rule1"])

        with patch("src.qa.rag_system.QAKnowledgeGraph", return_value=mock_kg):
            service = RewriterService(mock_agent)

            result = await service.rewrite_best_answer(
                user_query="Query",
                selected_answer="Answer",
                edit_request="Make it shorter",
                formatting_rules="Format rules",
                cached_content=None,
                query_type="table_summary",
            )

            assert result == "New answer"

    @pytest.mark.asyncio
    async def test_rewrite_with_template_context(self):
        """Test rewriting with template context from CSV."""
        mock_agent = Mock()
        mock_agent.logger = Mock()
        mock_agent._create_generative_model = Mock()
        mock_agent.context_manager = Mock()
        mock_agent.retry_handler = Mock()
        mock_agent.retry_handler.call = AsyncMock(
            return_value="Answer"
        )
        mock_agent._is_rate_limit_error = Mock(return_value=False)
        mock_agent.config = Mock()
        mock_agent.config.target_length = None

        mock_template = Mock()
        mock_template.render = Mock(return_value="prompt")
        mock_agent.jinja_env = Mock()
        mock_agent.jinja_env.get_template = Mock(return_value=mock_template)

        with patch("src.qa.template_rules.get_all_template_context") as mock_context, \
             patch("src.qa.template_rules.get_neo4j_config") as mock_config:
            mock_config.return_value = {
                "neo4j_uri": "bolt://localhost",
                "neo4j_user": "neo4j",
                "neo4j_password": "password",
            }
            mock_context.return_value = {
                "guide_rules": [{"text": "Guide 1"}],
                "common_mistakes": [{"mistake": "Error 1"}],
            }

            service = RewriterService(mock_agent)

            result = await service.rewrite_best_answer(
                user_query="Q",
                selected_answer="A",
                edit_request=None,
                formatting_rules=None,
                cached_content=None,
                query_type="explanation",
            )

            assert result == "Answer"

    @pytest.mark.asyncio
    async def test_rewrite_rate_limit_error(self):
        """Test rewriting with rate limit error."""
        mock_agent = Mock()
        mock_agent.logger = Mock()
        mock_agent._create_generative_model = Mock()
        mock_agent.context_manager = Mock()
        mock_agent.retry_handler = Mock()
        mock_agent.retry_handler.call = AsyncMock(
            side_effect=Exception("Rate limit")
        )
        mock_agent._is_rate_limit_error = Mock(return_value=True)
        mock_agent.config = Mock()
        mock_agent.config.target_length = None

        mock_template = Mock()
        mock_template.render = Mock(return_value="prompt")
        mock_agent.jinja_env = Mock()
        mock_agent.jinja_env.get_template = Mock(return_value=mock_template)

        service = RewriterService(mock_agent)

        with pytest.raises(APIRateLimitError):
            await service.rewrite_best_answer(
                user_query="Q",
                selected_answer="A",
                edit_request=None,
                formatting_rules=None,
                cached_content=None,
                query_type="explanation",
            )

    @pytest.mark.asyncio
    async def test_rewrite_constraint_priority_none(self):
        """Test constraint handling with None priority."""
        mock_agent = Mock()
        mock_agent.logger = Mock()
        mock_agent._create_generative_model = Mock()
        mock_agent.context_manager = Mock()
        mock_agent.retry_handler = Mock()
        mock_agent.retry_handler.call = AsyncMock(
            return_value="Answer"
        )
        mock_agent._is_rate_limit_error = Mock(return_value=False)
        mock_agent.config = Mock()
        mock_agent.config.target_length = None

        mock_template = Mock()
        mock_template.render = Mock(return_value="prompt")
        mock_agent.jinja_env = Mock()
        mock_agent.jinja_env.get_template = Mock(return_value=mock_template)

        mock_kg = Mock()
        mock_kg.get_constraints_for_query_type = Mock(
            return_value=[
                {"description": "C1", "priority": None},
                {"description": "C2", "priority": "invalid"},
                {"description": "C3", "priority": 5},
            ]
        )
        mock_kg.find_relevant_rules = Mock(return_value=[])

        with patch("src.qa.rag_system.QAKnowledgeGraph", return_value=mock_kg):
            service = RewriterService(mock_agent)

            result = await service.rewrite_best_answer(
                user_query="Q",
                selected_answer="A",
                edit_request=None,
                formatting_rules=None,
                cached_content=None,
                query_type="explanation",
            )

            # Should not raise error and return answer
            assert result == "Answer"

    @pytest.mark.asyncio
    async def test_rewrite_fallback_template(self):
        """Test fallback to basic template on error."""
        mock_agent = Mock()
        mock_agent.logger = Mock()
        mock_agent._create_generative_model = Mock()
        mock_agent.context_manager = Mock()
        mock_agent.retry_handler = Mock()
        mock_agent.retry_handler.call = AsyncMock(
            return_value="Answer"
        )
        mock_agent._is_rate_limit_error = Mock(return_value=False)
        mock_agent.config = Mock()
        mock_agent.config.target_length = None

        # First template call fails, second succeeds
        mock_template_fail = Mock()
        mock_template_fail.render = Mock(side_effect=Exception("Template error"))
        mock_template_ok = Mock()
        mock_template_ok.render = Mock(return_value="fallback prompt")

        mock_agent.jinja_env = Mock()
        mock_agent.jinja_env.get_template = Mock(
            side_effect=[mock_template_fail, mock_template_ok]
        )

        service = RewriterService(mock_agent)

        result = await service.rewrite_best_answer(
            user_query="Q",
            selected_answer="A",
            edit_request=None,
            formatting_rules=None,
            cached_content=None,
            query_type="explanation",
        )

        assert result == "Answer"
        assert mock_agent.logger.warning.called
