"""End-to-end tests for the complete workflow pipeline.

These tests verify the entire flow from query generation
to answer evaluation and rewriting, using mocked API responses.
"""

from __future__ import annotations

import json
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agent import GeminiAgent
from src.config import AppConfig
from src.core.models import EvaluationResultSchema, QueryResult


@pytest.fixture
def mock_config() -> AppConfig:
    """Create a mock AppConfig for testing."""
    with patch.dict(
        "os.environ",
        {
            "GEMINI_API_KEY": "AIza" + "x" * 35,
            "GEMINI_MODEL_NAME": "gemini-3-pro-preview",
        },
    ):
        config = AppConfig()
    return config


@pytest.fixture
def mock_jinja_env() -> MagicMock:
    """Create a mock Jinja2 environment."""
    env = MagicMock()
    template = MagicMock()
    template.render.return_value = "System prompt"
    env.get_template.return_value = template
    return env


@pytest.fixture
def mock_agent(mock_config: AppConfig, mock_jinja_env: MagicMock) -> GeminiAgent:
    """Create a GeminiAgent with mocked dependencies."""
    return GeminiAgent(
        config=mock_config,
        jinja_env=mock_jinja_env,
    )


class TestWorkflowE2E:
    """End-to-end workflow tests."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_full_workflow_query_to_rewrite(
        self,
        mock_agent: GeminiAgent,
    ) -> None:
        """Test complete workflow: query generation → evaluation → rewrite."""
        # Mock API responses
        query_response = QueryResult(queries=["What is the main topic?"])
        eval_response = EvaluationResultSchema(
            best_candidate="A",
            evaluations=[
                {"candidate_id": "A", "score": 85, "reason": "Clear and accurate"},
                {"candidate_id": "B", "score": 70, "reason": "Partially correct"},
            ],
        )
        rewrite_response = "This is the improved answer with better clarity."

        with patch.object(
            mock_agent,
            "_call_api_with_retry",
            new_callable=AsyncMock,
        ) as mock_api:
            # Configure mock responses
            mock_api.side_effect = [
                query_response.model_dump_json(),
                eval_response.model_dump_json(),
                rewrite_response,
            ]

            # Step 1: Generate queries
            ocr_text = "Sample OCR text content for testing."
            queries = await mock_agent.generate_query(ocr_text)
            
            assert len(queries) > 0
            assert queries[0] == "What is the main topic?"

            # Step 2: Evaluate responses
            candidates = {
                "A": "This is answer A.",
                "B": "This is answer B.",
            }
            evaluation = await mock_agent.evaluate_responses(
                ocr_text=ocr_text,
                query=queries[0],
                candidates=candidates,
            )
            
            assert evaluation is not None
            assert evaluation.best_candidate == "A"

            # Step 3: Rewrite best answer
            rewritten = await mock_agent.rewrite_best_answer(
                ocr_text=ocr_text,
                best_answer=candidates["A"],
            )
            
            assert "improved" in rewritten.lower()

    @pytest.mark.e2e
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_workflow_with_cache(
        self,
        mock_agent: GeminiAgent,
    ) -> None:
        """Test workflow with context caching enabled."""
        # Skip if cache creation is mocked
        with patch.object(
            mock_agent,
            "create_context_cache",
            new_callable=AsyncMock,
            return_value=None,
        ):
            with patch.object(
                mock_agent,
                "_call_api_with_retry",
                new_callable=AsyncMock,
                return_value='{"queries": ["Test query"]}',
            ):
                queries = await mock_agent.generate_query(
                    "Long OCR text " * 500,  # Simulate large input
                    user_intent="Summarize",
                )
                
                assert len(queries) > 0

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_workflow_error_recovery(
        self,
        mock_agent: GeminiAgent,
    ) -> None:
        """Test workflow handles API errors gracefully."""
        call_count = 0

        async def failing_api(*args: Any, **kwargs: Any) -> str:
            nonlocal call_count
            call_count += 1
            raise TimeoutError("Simulated timeout")

        with patch.object(
            mock_agent,
            "_call_api_with_retry",
            side_effect=failing_api,
        ):
            # Should raise the error
            with pytest.raises(TimeoutError):
                await mock_agent.generate_query("Test OCR")
            
            assert call_count == 1  # Called once before raising

        # After error, agent should still work with successful response
        call_count = 0
        
        async def success_api(*args: Any, **kwargs: Any) -> str:
            nonlocal call_count
            call_count += 1
            return '{"queries": ["Recovered query"]}'

        with patch.object(
            mock_agent,
            "_call_api_with_retry",
            side_effect=success_api,
        ):
            queries = await mock_agent.generate_query("Test OCR")
            
            assert len(queries) > 0
            assert call_count == 1


class TestWorkflowPerformance:
    """Performance regression tests for workflow."""

    @pytest.mark.e2e
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_query_generation_latency(
        self,
        mock_agent: GeminiAgent,
    ) -> None:
        """Verify query generation completes within acceptable time."""
        import time

        with patch.object(
            mock_agent,
            "_call_api_with_retry",
            new_callable=AsyncMock,
            return_value='{"queries": ["Quick query"]}',
        ):
            start = time.perf_counter()
            await mock_agent.generate_query("Test OCR text")
            elapsed = time.perf_counter() - start

            # Should complete mock call in under 1 second
            assert elapsed < 1.0, f"Query generation too slow: {elapsed:.2f}s"
