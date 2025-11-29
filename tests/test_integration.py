import logging

import pytest

from src.workflow import execute_workflow
from src.core.models import EvaluationItem, EvaluationResultSchema
from typing import Any
from pathlib import Path

VALID_API_KEY = "AIza" + "A" * 35


class DummyAgent:
    def __init__(self) -> None:
        self.total_input_tokens = 1_000
        self.total_output_tokens = 500
        self.budget_limit_usd = None

    async def generate_query(self, ocr_text: Any, user_intent: Any) -> Any:
        return ["strategic query"]

    async def create_context_cache(self, ocr_text: Any) -> Any:
        return None

    async def evaluate_responses(
        self, ocr_text: Any, query: Any, candidates: Any, cached_content: Any=None
    ) -> Any:
        return EvaluationResultSchema(
            best_candidate="A",
            evaluations=[EvaluationItem(candidate_id="A", score=10, reason="strong")],
        )

    async def rewrite_best_answer(self, ocr_text: Any, best_answer: Any, cached_content: Any=None) -> Any:
        return f"rewritten: {best_answer}"

    def get_total_cost(self) -> float:
        return 0.123

    def check_budget(self) -> Any:
        return None

    def get_budget_usage_percent(self) -> float:
        return 0.0


@pytest.mark.asyncio
async def test_execute_workflow_e2e(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", VALID_API_KEY)
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))

    async def fake_reload_data(config: Any, ocr_filename: Any, cand_filename: Any, interactive: Any=False) -> Any:
        return "ocr text", {"A": '{"A": "Best answer"}'}

    monkeypatch.setattr("src.workflow.executor.reload_data_if_needed", fake_reload_data)

    agent = DummyAgent()
    logger = logging.getLogger("GeminiWorkflow")

    results = await execute_workflow(
        agent,  # type: ignore[arg-type]
        ocr_text="ocr body",
        user_intent="intent",
        logger=logger,
        ocr_filename="ocr.txt",
        cand_filename="cand.json",
        config=None,
        is_interactive=False,
    )

    assert len(results) == 1
    result = results[0]
    assert result.best_answer == "Best answer"
    assert result.rewritten_answer == "rewritten: Best answer"
    assert result.success is True
    assert result.cost == pytest.approx(0.123)


class NoCallAgent(DummyAgent):
    async def generate_query(self, ocr_text: Any, user_intent: Any) -> Any:
        return ["strategic query"]

    async def evaluate_responses(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("Should not evaluate when resuming")

    async def rewrite_best_answer(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("Should not rewrite when resuming")


@pytest.mark.asyncio
async def test_execute_workflow_resume(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", VALID_API_KEY)
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))

    async def fake_reload_data(config: Any, ocr_filename: Any, cand_filename: Any, interactive: Any=False) -> Any:
        return "ocr text", {"A": '{"A": "Best answer"}'}

    monkeypatch.setattr("src.workflow.executor.reload_data_if_needed", fake_reload_data)

    checkpoint_path = tmp_path / "data" / "outputs" / "checkpoint.jsonl"
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    # Preload checkpoint entry
    from src.core.models import WorkflowResult

    existing = WorkflowResult(
        turn_id=1,
        query="strategic query",
        evaluation=None,
        best_answer="Cached answer",
        rewritten_answer="Cached rewritten",
        cost=0.0,
        success=True,
    )
    checkpoint_path.write_text(
        existing.model_dump_json(ensure_ascii=False) + "\n", encoding="utf-8"
    )

    agent = NoCallAgent()
    logger = logging.getLogger("GeminiWorkflow")

    results = await execute_workflow(
        agent,  # type: ignore[arg-type]
        ocr_text="ocr body",
        user_intent="intent",
        logger=logger,
        ocr_filename="ocr.txt",
        cand_filename="cand.json",
        config=None,
        is_interactive=False,
        resume=True,
        checkpoint_path=checkpoint_path,
    )

    assert len(results) == 1
    assert results[0].rewritten_answer == "Cached rewritten"
