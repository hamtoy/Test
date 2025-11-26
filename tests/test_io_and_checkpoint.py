import pytest
from unittest.mock import MagicMock
from src.workflow.processor import save_result_to_file
from src.infra.utils import load_checkpoint, append_checkpoint
from src.core.models import WorkflowResult, EvaluationResultSchema, EvaluationItem


def test_save_result_to_file(tmp_path):
    config = MagicMock()
    config.output_dir = tmp_path

    eval_item = EvaluationItem(candidate_id="A", score=90, reason="Good")
    eval_result = EvaluationResultSchema(best_candidate="A", evaluations=[eval_item])

    result = WorkflowResult(
        turn_id=1,
        query="Test Query",
        evaluation=eval_result,
        best_answer="Best Answer",
        rewritten_answer="Rewritten",
        cost=0.05,
        success=True,
    )

    save_result_to_file(result, config)

    # Check if file was created
    files = list(tmp_path.glob("result_turn_1_*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "Test Query" in content
    assert "Rewritten" in content


def test_save_result_to_file_io_error(monkeypatch, tmp_path):
    config = MagicMock()
    config.output_dir = tmp_path

    eval_item = EvaluationItem(candidate_id="A", score=90, reason="Good")
    eval_result = EvaluationResultSchema(best_candidate="A", evaluations=[eval_item])

    result = WorkflowResult(
        turn_id=1,
        query="Test Query",
        evaluation=eval_result,
        best_answer="Best Answer",
        rewritten_answer="Rewritten",
        cost=0.05,
        success=True,
    )

    monkeypatch.setattr("builtins.open", MagicMock(side_effect=PermissionError))
    with pytest.raises(PermissionError):
        save_result_to_file(result, config)


@pytest.mark.asyncio
async def test_checkpoint_roundtrip(tmp_path):
    path = tmp_path / "checkpoint.jsonl"
    eval_item = EvaluationItem(candidate_id="A", score=90, reason="Good")
    eval_result = EvaluationResultSchema(best_candidate="A", evaluations=[eval_item])
    result = WorkflowResult(
        turn_id=1,
        query="Query",
        evaluation=eval_result,
        best_answer="A",
        rewritten_answer="A",
        cost=0.0,
        success=True,
    )

    await append_checkpoint(path, result)
    loaded = await load_checkpoint(path)
    assert "Query" in loaded
    assert loaded["Query"].turn_id == 1
