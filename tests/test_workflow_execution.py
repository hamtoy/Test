import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.workflow import execute_workflow
from src.workflow.executor import _gather_results
from src.core.models import EvaluationResultSchema, EvaluationItem
from src.config.exceptions import BudgetExceededError
from typing import Any


@pytest.fixture
def mock_agent() -> Any:
    agent = MagicMock()
    agent.generate_query = AsyncMock(return_value=["Query 1"])
    agent.evaluate_responses = AsyncMock()
    agent.rewrite_best_answer = AsyncMock(return_value="Rewritten Answer")
    agent.create_context_cache = AsyncMock(return_value=None)
    agent.get_total_cost = MagicMock(return_value=0.1)
    agent.get_budget_usage_percent = MagicMock(return_value=50.0)
    agent.check_budget = MagicMock(return_value=None)
    return agent


@pytest.fixture
def mock_logger() -> Any:
    return MagicMock()


@pytest.mark.asyncio
async def test_execute_workflow_success(mock_agent: Any, mock_logger: Any) -> None:
    ocr_text = "ocr"
    candidates = {"A": "a", "B": "b", "C": "c"}

    # Mock evaluation result
    eval_item = EvaluationItem(candidate_id="A", score=90, reason="Good")
    eval_result = EvaluationResultSchema(best_candidate="A", evaluations=[eval_item])
    mock_agent.evaluate_responses.return_value = eval_result

    with patch(
        "src.workflow.executor.reload_data_if_needed", new_callable=AsyncMock
    ) as mock_reload:
        mock_reload.return_value = (ocr_text, candidates)

        # Mock save_result_to_file to avoid file I/O
        with patch("src.workflow.processor.save_result_to_file") as mock_save:
            results = await execute_workflow(
                agent=mock_agent,
                ocr_text=ocr_text,
                user_intent=None,
                logger=mock_logger,
                ocr_filename="ocr.txt",
                cand_filename="cand.json",
                config=None,
                is_interactive=False,
            )

            assert len(results) == 1
            assert results[0].query == "Query 1"
            assert results[0].best_answer == "a"
            assert results[0].rewritten_answer == "Rewritten Answer"
            mock_save.assert_called_once()


@pytest.mark.asyncio
async def test_execute_workflow_query_gen_fail(mock_agent: Any, mock_logger: Any) -> None:
    mock_agent.generate_query.return_value = []

    results = await execute_workflow(
        agent=mock_agent,
        ocr_text="ocr",
        user_intent=None,
        logger=mock_logger,
        ocr_filename="ocr.txt",
        cand_filename="cand.json",
        config=None,
        is_interactive=False,
    )

    assert len(results) == 0
    mock_logger.error.assert_called_with("질의 생성 실패")


@pytest.mark.asyncio
async def test_execute_workflow_budget_exceeded(mock_logger: Any) -> None:
    mock_agent = MagicMock()
    mock_agent.generate_query = AsyncMock(return_value=["Query 1"])
    mock_agent.check_budget = MagicMock(side_effect=BudgetExceededError("limit"))
    mock_agent.get_budget_usage_percent = MagicMock(return_value=95.0)
    mock_agent.create_context_cache = AsyncMock(return_value=None)

    with patch(
        "src.workflow.executor.reload_data_if_needed", new_callable=AsyncMock
    ) as mock_reload:
        mock_reload.return_value = ("ocr", {"A": "a"})

        results = await execute_workflow(
            agent=mock_agent,
            ocr_text="ocr",
            user_intent=None,
            logger=mock_logger,
            ocr_filename="ocr.txt",
            cand_filename="cand.json",
            config=None,
            is_interactive=False,
        )

    assert results == []
    mock_logger.error.assert_any_call("Budget limit exceeded: limit")


@pytest.mark.asyncio
async def test_gather_results_propagates_budget_error(mock_logger: Any) -> None:
    async def _raise_budget() -> None:
        raise BudgetExceededError("limit")

    task = asyncio.create_task(_raise_budget())
    with pytest.raises(BudgetExceededError):
        await _gather_results([task], mock_logger)


@pytest.mark.asyncio
async def test_execute_workflow_interactive_skip_reload(mock_agent: Any, mock_logger: Any) -> None:
    mock_agent.create_context_cache = AsyncMock(return_value=None)
    eval_item = EvaluationItem(candidate_id="A", score=90, reason="Good")
    eval_result = EvaluationResultSchema(best_candidate="A", evaluations=[eval_item])
    mock_agent.evaluate_responses = AsyncMock(return_value=eval_result)
    mock_agent.rewrite_best_answer = AsyncMock(return_value="rewritten")

    with (
        patch("src.workflow.executor.Confirm.ask", return_value=False),
        patch(
            "src.workflow.executor.reload_data_if_needed", new_callable=AsyncMock
        ) as mock_reload,
    ):
        mock_reload.return_value = ("ocr", {"A": "a"})

        results = await execute_workflow(
            agent=mock_agent,
            ocr_text="ocr",
            user_intent=None,
            logger=mock_logger,
            ocr_filename="ocr.txt",
            cand_filename="cand.json",
            config=None,
            is_interactive=True,
        )

    assert len(results) == 1
    mock_reload.assert_called_once()
    mock_agent.rewrite_best_answer.assert_awaited()
