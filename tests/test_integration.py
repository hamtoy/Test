import logging

import pytest

from src.main import execute_workflow
from src.models import EvaluationItem, EvaluationResultSchema

VALID_API_KEY = "AIza" + "A" * 35


class DummyAgent:
    def __init__(self) -> None:
        self.total_input_tokens = 1_000
        self.total_output_tokens = 500

    async def generate_query(self, ocr_text, user_intent):
        return ["strategic query"]

    async def create_context_cache(self, ocr_text):
        return None

    async def evaluate_responses(self, ocr_text, query, candidates, cached_content=None):
        return EvaluationResultSchema(
            best_candidate="A",
            evaluations=[EvaluationItem(candidate_id="A", score=10, reason="strong")],
        )

    async def rewrite_best_answer(self, ocr_text, best_answer, cached_content=None):
        return f"rewritten: {best_answer}"

    def get_total_cost(self) -> float:
        return 0.123


@pytest.mark.asyncio
async def test_execute_workflow_e2e(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", VALID_API_KEY)
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))

    async def fake_reload_data(config, ocr_filename, cand_filename, interactive=False):
        return "ocr text", {"A": '{"A": "Best answer"}'}

    monkeypatch.setattr("src.main.reload_data_if_needed", fake_reload_data)

    agent = DummyAgent()
    logger = logging.getLogger("GeminiWorkflow")

    results = await execute_workflow(
        agent,
        ocr_text="ocr body",
        user_intent="intent",
        logger=logger,
        ocr_filename="ocr.txt",
        cand_filename="cand.json",
        is_interactive=False,
    )

    assert len(results) == 1
    result = results[0]
    assert result.best_answer == "Best answer"
    assert result.rewritten_answer == "rewritten: Best answer"
    assert result.success is True
    assert result.cost == pytest.approx(0.123)
