from src.core.models import EvaluationResultSchema


def test_get_best_candidate_when_evaluations_empty_defaults_to_a():
    result = EvaluationResultSchema(best_candidate="A", evaluations=[])
    assert result.get_best_candidate_id() == "A"


def test_model_validation_handles_ties_by_preserving_first_max():
    data = {
        "best_candidate": "B",
        "evaluations": [
            {"candidate_id": "B", "score": 90, "reason": "Strong"},
            {"candidate_id": "C", "score": 90, "reason": "Also strong"},
        ],
    }
    result = EvaluationResultSchema(**data)  # type: ignore[arg-type]
    # Should not override when claimed best is tied for max
    assert result.best_candidate == "B"
    assert result.get_best_candidate_id() == "B"
