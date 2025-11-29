"""Tests for the workflow processor module."""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.exceptions import (
    APIRateLimitError,
    BudgetExceededError,
    SafetyFilterError,
    ValidationFailedError,
)
from src.core.models import EvaluationItem, EvaluationResultSchema, WorkflowResult


class TestSaveResultToFile:
    """Tests for save_result_to_file function."""

    def test_save_result_basic(self, tmp_path: Path) -> None:
        """Test saving result to file."""
        from src.workflow.processor import save_result_to_file

        # Create proper evaluation using models
        evaluation = EvaluationResultSchema(
            best_candidate="A",
            evaluations=[
                EvaluationItem(candidate_id="A", score=85, reason="Good answer"),
                EvaluationItem(candidate_id="B", score=70, reason="Average"),
            ],
        )

        # Create result
        result = WorkflowResult(
            turn_id=1,
            query="Test query?",
            evaluation=evaluation,
            best_answer="The best answer",
            rewritten_answer="Rewritten answer",
            cost=0.0015,
            success=True,
        )

        # Create mock config
        mock_config = MagicMock()
        mock_config.output_dir = tmp_path

        save_result_to_file(result, mock_config)

        # Verify file was created
        files = list(tmp_path.glob("result_turn_1_*.md"))
        assert len(files) == 1

        # Verify content
        content = files[0].read_text(encoding="utf-8")
        assert "# Turn 1 Result" in content
        assert "Test query?" in content
        assert "Best Candidate**: A" in content
        assert "The best answer" in content
        assert "Rewritten answer" in content


class TestEvaluateAndRewriteTurn:
    """Tests for _evaluate_and_rewrite_turn function."""

    @pytest.fixture
    def mock_context(self) -> Any:
        """Create a mock WorkflowContext."""
        ctx = MagicMock()
        ctx.logger = MagicMock()
        ctx.total_turns = 4
        ctx.ocr_text = "OCR text"
        ctx.candidates = {"A": "Answer A", "B": "Answer B"}
        ctx.cache = None

        # Create proper mock evaluation
        mock_eval = EvaluationResultSchema(
            best_candidate="A",
            evaluations=[
                EvaluationItem(candidate_id="A", score=90, reason="Good"),
            ],
        )

        ctx.agent = MagicMock()
        ctx.agent.evaluate_responses = AsyncMock(return_value=mock_eval)
        ctx.agent.rewrite_best_answer = AsyncMock(return_value="Rewritten")
        ctx.agent.get_total_cost.return_value = 0.001

        return ctx

    @pytest.mark.asyncio
    async def test_evaluate_and_rewrite_success(self, mock_context: Any) -> None:
        """Test successful evaluation and rewrite."""
        from src.workflow.processor import _evaluate_and_rewrite_turn

        result = await _evaluate_and_rewrite_turn(mock_context, "Test query", turn_id=1)

        assert result is not None
        assert result.turn_id == 1
        assert result.query == "Test query"
        assert result.success is True
        mock_context.agent.evaluate_responses.assert_called_once()
        mock_context.agent.rewrite_best_answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_and_rewrite_evaluation_fails(
        self, mock_context: Any
    ) -> None:
        """Test when evaluation returns None."""
        from src.workflow.processor import _evaluate_and_rewrite_turn

        mock_context.agent.evaluate_responses = AsyncMock(return_value=None)

        result = await _evaluate_and_rewrite_turn(mock_context, "Test query", turn_id=1)

        assert result is None
        mock_context.logger.warning.assert_called()


class TestProcessSingleQuery:
    """Tests for process_single_query function."""

    @pytest.fixture
    def mock_context(self, tmp_path: Path) -> Any:
        """Create a mock WorkflowContext."""
        ctx = MagicMock()
        ctx.logger = MagicMock()
        ctx.total_turns = 4
        ctx.ocr_text = "OCR text"
        ctx.candidates = {"A": "Answer A", "B": "Answer B"}
        ctx.cache = None
        ctx.progress = None
        ctx.checkpoint_path = None

        # Mock config
        ctx.config = MagicMock()
        ctx.config.output_dir = tmp_path

        # Create proper mock evaluation
        mock_eval = EvaluationResultSchema(
            best_candidate="A",
            evaluations=[
                EvaluationItem(candidate_id="A", score=90, reason="Good"),
            ],
        )

        ctx.agent = MagicMock()
        ctx.agent.evaluate_responses = AsyncMock(return_value=mock_eval)
        ctx.agent.rewrite_best_answer = AsyncMock(return_value="Rewritten answer here")
        ctx.agent.get_total_cost.return_value = 0.001

        return ctx

    @pytest.mark.asyncio
    async def test_process_single_query_success(self, mock_context: Any) -> None:
        """Test successful query processing."""
        from src.workflow.processor import process_single_query

        with patch("src.workflow.processor.console") as mock_console:
            result = await process_single_query(mock_context, "Test query", turn_id=1)

        assert result is not None
        assert result.success is True
        mock_console.print.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_single_query_with_progress(self, mock_context: Any) -> None:
        """Test query processing with progress tracking."""
        from src.workflow.processor import process_single_query

        mock_progress = MagicMock()
        mock_context.progress = mock_progress
        task_id = "task1"

        with patch("src.workflow.processor.console"):
            result = await process_single_query(
                mock_context, "Test query", turn_id=1, task_id=task_id
            )

        assert result is not None
        # Verify progress was updated
        mock_progress.update.assert_called()

    @pytest.mark.asyncio
    async def test_process_single_query_rate_limit_error(
        self, mock_context: Any
    ) -> None:
        """Test handling of rate limit error."""
        from src.workflow.processor import process_single_query

        mock_context.agent.evaluate_responses = AsyncMock(
            side_effect=APIRateLimitError("Rate limited")
        )

        result = await process_single_query(mock_context, "Test query", turn_id=1)

        assert result is None
        mock_context.logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_process_single_query_validation_error(
        self, mock_context: Any
    ) -> None:
        """Test handling of validation error."""
        from src.workflow.processor import process_single_query

        mock_context.agent.evaluate_responses = AsyncMock(
            side_effect=ValidationFailedError("Invalid input")
        )

        result = await process_single_query(mock_context, "Test query", turn_id=1)

        assert result is None

    @pytest.mark.asyncio
    async def test_process_single_query_safety_filter_error(
        self, mock_context: Any
    ) -> None:
        """Test handling of safety filter error."""
        from src.workflow.processor import process_single_query

        mock_context.agent.evaluate_responses = AsyncMock(
            side_effect=SafetyFilterError("Blocked")
        )

        result = await process_single_query(mock_context, "Test query", turn_id=1)

        assert result is None

    @pytest.mark.asyncio
    async def test_process_single_query_budget_exceeded(
        self, mock_context: Any
    ) -> None:
        """Test handling of budget exceeded error."""
        from src.workflow.processor import process_single_query

        mock_context.agent.evaluate_responses = AsyncMock(
            side_effect=BudgetExceededError("Budget exceeded")
        )

        with pytest.raises(BudgetExceededError):
            await process_single_query(mock_context, "Test query", turn_id=1)

    @pytest.mark.asyncio
    async def test_process_single_query_os_error(self, mock_context: Any) -> None:
        """Test handling of OS error."""
        from src.workflow.processor import process_single_query

        mock_context.agent.evaluate_responses = AsyncMock(
            side_effect=OSError("File error")
        )

        result = await process_single_query(mock_context, "Test query", turn_id=1)

        assert result is None
        mock_context.logger.exception.assert_called()

    @pytest.mark.asyncio
    async def test_process_single_query_runtime_error(self, mock_context: Any) -> None:
        """Test handling of runtime error."""
        from src.workflow.processor import process_single_query

        mock_context.agent.evaluate_responses = AsyncMock(
            side_effect=RuntimeError("Runtime error")
        )

        result = await process_single_query(mock_context, "Test query", turn_id=1)

        assert result is None
