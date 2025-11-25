from __future__ import annotations

import types
from src import semantic_analysis
from src import smart_autocomplete
from src import dynamic_example_selector
from src import adaptive_difficulty


def test_semantic_analysis_utils(monkeypatch):
    monkeypatch.setattr(semantic_analysis, "MIN_FREQ", 1)
    tokens = semantic_analysis.tokenize("This is a Sample sample text with 숫자123")
    assert "sample" in tokens

    counter = semantic_analysis.count_keywords(["alpha beta alpha", "beta gamma"])
    assert counter["alpha"] >= 1

    store = []

    class _SATx:
        def __init__(self, store_ref):
            self.store_ref = store_ref

        def run(self, _query, topics=None, links=None):
            if topics is not None:
                self.store_ref.extend(topics)
            if links is not None:
                self.store_ref.extend(links)

    class _SASession:
        def __init__(self, store_ref):
            self.store_ref = store_ref

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute_write(self, func, items):
            func(_SATx(self.store_ref), items)

        def run(self, *_args, **_kwargs):
            return [{"id": "b1", "content": "alpha beta gamma"}]

    class _SADriver:
        def __init__(self):
            self.session_obj = _SASession(store)

        def session(self):
            return self.session_obj

    driver = _SADriver()
    semantic_analysis.create_topics(driver, [("alpha", 3)])
    semantic_analysis.link_blocks_to_topics(
        driver, [{"id": "b1", "content": "alpha beta"}], [("alpha", 3)]
    )


def test_smart_autocomplete(monkeypatch):
    class _SmartSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, query, **_kwargs):
            if "ErrorPattern" in query:
                return [{"pattern": "bad", "desc": "bad pattern"}]
            if "Constraint" in query:
                return [{"pattern": "warn", "desc": "warn desc"}]
            return [
                {"name": "summary", "korean": "요약", "limit": 2, "priority": 1},
                {"name": "explanation", "korean": "설명", "limit": 1, "priority": 0},
            ]

    class _SmartKG:
        def __init__(self):
            self._graph = types.SimpleNamespace(session=lambda: _SmartSession())

    monkeypatch.setattr(
        smart_autocomplete,
        "find_violations",
        lambda text: [{"type": "local", "match": text}],
    )
    sa = smart_autocomplete.SmartAutocomplete(_SmartKG())
    suggestions = sa.suggest_next_query_type([{"type": "summary"}])
    assert any(s["name"] == "explanation" for s in suggestions)

    compliance = sa.suggest_constraint_compliance("bad output warn", "summary")
    assert compliance["violations"]


def test_dynamic_example_selector(monkeypatch):
    class _DESession:
        def __init__(self):
            self.updated = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, query, **params):
            class _Result(list):
                def data(self_inner):
                    return list(self_inner)

            if "RETURN e.text AS example" in query:
                return _Result([{"example": "ex", "rate": 0.9, "usage": 0}])
            if "SET e.usage_count" in query:
                self.updated.append(params["text"])
                return _Result([])
            return _Result([])

    class _DEKG:
        def __init__(self):
            self._graph = types.SimpleNamespace(session=lambda: _DESession())

    selector = dynamic_example_selector.DynamicExampleSelector(_DEKG())
    examples = selector.select_best_examples(
        "explanation", {"text_density": 0.8, "has_table_chart": True}, k=1
    )
    assert examples


def test_adaptive_difficulty(monkeypatch):
    class _ADSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            class _Result:
                def single(self_inner):
                    return {"avg_blocks": 5}

            return _Result()

    fake_kg = types.SimpleNamespace(
        _graph=types.SimpleNamespace(session=lambda: _ADSession())
    )
    adjuster = adaptive_difficulty.AdaptiveDifficultyAdjuster(fake_kg)
    complexity = adjuster.analyze_image_complexity({"text_density": 0.8})
    assert complexity["estimated_blocks"] == 5
    adjustments = adjuster.adjust_query_requirements(complexity, "explanation")
    assert adjustments["min_length"] >= 300
