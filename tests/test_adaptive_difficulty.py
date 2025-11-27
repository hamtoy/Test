import types

from src.features.difficulty import AdaptiveDifficultyAdjuster


class _FakeSession:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, *args, **kwargs):
        return self

    def single(self):
        return {"avg_blocks": self.value}


class _FakeGraph:
    def __init__(self, value):
        self.value = value

    def session(self):
        return _FakeSession(self.value)


def test_analyze_image_complexity_levels():
    kg = types.SimpleNamespace(_graph=_FakeGraph(5))
    adjuster = AdaptiveDifficultyAdjuster(kg)

    # simple
    comp_simple = adjuster.analyze_image_complexity({"text_density": 0.2})
    assert comp_simple["level"] == "simple"
    assert comp_simple["recommended_turns"] == 3
    assert comp_simple["reasoning_possible"] is False

    # medium
    comp_medium = adjuster.analyze_image_complexity({"text_density": 0.5})
    assert comp_medium["level"] == "medium"
    assert comp_medium["recommended_turns"] == 3

    # complex
    comp_complex = adjuster.analyze_image_complexity({"text_density": 0.8})
    assert comp_complex["level"] == "complex"
    assert comp_complex["recommended_turns"] == 4
    assert comp_complex["estimated_blocks"] == 5.0


def test_adjust_query_requirements():
    kg = types.SimpleNamespace(_graph=_FakeGraph(None))
    adjuster = AdaptiveDifficultyAdjuster(kg)

    comp_simple = {"level": "simple", "reasoning_possible": False}
    adj_expl = adjuster.adjust_query_requirements(comp_simple, "explanation")
    assert adj_expl["depth"] == "shallow"

    adj_reasoning = adjuster.adjust_query_requirements(comp_simple, "reasoning")
    assert adj_reasoning["fallback"] == "target"

    comp_complex = {"level": "complex", "reasoning_possible": True}
    adj_expl2 = adjuster.adjust_query_requirements(comp_complex, "explanation")
    assert adj_expl2["depth"] == "deep"
