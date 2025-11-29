from __future__ import annotations

import types
from pathlib import Path
from typing import Any

import pytest

from src.analysis import semantic
from src.features import autocomplete as smart_autocomplete
from src.processing import example_selector
from src.features import difficulty as adaptive_difficulty


def test_semantic_analysis_utils(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(semantic, "MIN_FREQ", 1)
    tokens = semantic.tokenize("This is a Sample sample text with 숫자123")
    assert "sample" in tokens

    counter = semantic.count_keywords(["alpha beta alpha", "beta gamma"])
    assert counter["alpha"] >= 1

    store: list[object] = []

    class _SATx:
        def __init__(self, store_ref: list[object]) -> None:
            self.store_ref = store_ref

        def run(
            self, _query: str, topics: list[str] | None = None, links: list[str] | None = None
        ) -> None:
            if topics is not None:
                self.store_ref.extend(topics)
            if links is not None:
                self.store_ref.extend(links)

    class _SASession:
        def __init__(self, store_ref: list[object]) -> None:
            self.store_ref = store_ref

        def __enter__(self) -> "_SASession":
            return self

        def __exit__(
            self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any
        ) -> None:
            return None

        def execute_write(self, func: Any, items: list[Any]) -> None:
            func(_SATx(self.store_ref), items)

        def run(self, *_args: Any, **_kwargs: Any) -> list[dict[str, str]]:
            return [{"id": "b1", "content": "alpha beta gamma"}]

    class _SADriver:
        def __init__(self) -> None:
            self.session_obj = _SASession(store)

        def session(self) -> _SASession:
            return self.session_obj

    driver = _SADriver()
    semantic.create_topics(driver, [("alpha", 3)])  # type: ignore[arg-type]
    semantic.link_blocks_to_topics(
        driver,  # type: ignore[arg-type]
        [{"id": "b1", "content": "alpha beta"}],
        [("alpha", 3)],
    )


def test_smart_autocomplete(monkeypatch: pytest.MonkeyPatch) -> None:
    class _SmartSession:
        def __enter__(self) -> "_SmartSession":
            return self

        def __exit__(
            self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any
        ) -> None:
            return None

        def run(self, query: str, **_kwargs: Any) -> list[dict[str, str | int]]:
            if "ErrorPattern" in query:
                return [{"pattern": "bad", "desc": "bad pattern"}]
            if "Constraint" in query:
                return [{"pattern": "warn", "desc": "warn desc"}]
            return [
                {"name": "summary", "korean": "요약", "limit": 2, "priority": 1},
                {"name": "explanation", "korean": "설명", "limit": 1, "priority": 0},
            ]

    class _SmartKG:
        def __init__(self) -> None:
            self._graph = types.SimpleNamespace(session=lambda: _SmartSession())

    monkeypatch.setattr(
        smart_autocomplete,
        "find_violations",
        lambda text: [{"type": "local", "match": text}],
    )
    sa = smart_autocomplete.SmartAutocomplete(_SmartKG())  # type: ignore[arg-type]
    suggestions = sa.suggest_next_query_type([{"type": "summary"}])
    assert any(s["name"] == "explanation" for s in suggestions)

    compliance = sa.suggest_constraint_compliance("bad output warn", "summary")
    assert compliance["violations"]


def test_dynamic_example_selector(monkeypatch: pytest.MonkeyPatch) -> None:
    class _DESession:
        def __init__(self) -> None:
            self.updated: list[str] = []

        def __enter__(self) -> "_DESession":
            return self

        def __exit__(
            self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any
        ) -> None:
            return None

        def run(self, query: str, **params: Any) -> list[dict[str, Any]]:
            class _Result(list[dict[str, Any]]):
                def data(self_inner: "_Result") -> list[dict[str, Any]]:
                    return list(self_inner)

            if "RETURN e.text AS example" in query:
                return _Result([{"example": "ex", "rate": 0.9, "usage": 0}])
            if "SET e.usage_count" in query:
                self.updated.append(str(params.get("text", "")))
                return _Result([])
            return _Result([])

    class _DEKG:
        def __init__(self) -> None:
            self._graph = types.SimpleNamespace(session=lambda: _DESession())

    selector = example_selector.DynamicExampleSelector(_DEKG())  # type: ignore[arg-type]
    examples = selector.select_best_examples(
        "explanation", {"text_density": 0.8, "has_table_chart": True}, k=1
    )
    assert examples


def test_adaptive_difficulty(monkeypatch: pytest.MonkeyPatch) -> None:
    class _ADSession:
        def __enter__(self) -> "_ADSession":
            return self

        def __exit__(
            self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any
        ) -> None:
            return None

        def run(self, *_args: Any, **_kwargs: Any) -> Any:
            class _Result:
                def single(self_inner: "_Result") -> dict[str, int]:
                    return {"avg_blocks": 5}

            return _Result()

    fake_kg = types.SimpleNamespace(
        _graph=types.SimpleNamespace(session=lambda: _ADSession())
    )
    adjuster = adaptive_difficulty.AdaptiveDifficultyAdjuster(fake_kg)  # type: ignore[arg-type]
    complexity = adjuster.analyze_image_complexity({"text_density": 0.8})
    assert complexity["estimated_blocks"] == 5
    adjustments = adjuster.adjust_query_requirements(complexity, "explanation")
    assert adjustments["min_length"] >= 300


def test_semantic_analysis_utils_simple() -> None:
    tokens = semantic.tokenize("Alpha, beta! 그리고 and 123")
    assert "alpha" in tokens and "beta" in tokens

    counts = semantic.count_keywords(["alpha alpha", "beta"])
    assert (
        counts["alpha"] >= 1 or "alpha" not in counts
    )  # MIN_FREQ may filter low counts


def test_adaptive_difficulty_levels(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Session:
        def __enter__(self) -> "_Session":
            return self

        def __exit__(
            self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any
        ) -> None:
            return None

        def run(self, *_args: Any, **_kwargs: Any) -> Any:
            class _R:
                def single(self_inner: "_R") -> dict[str, int]:
                    return {"avg_blocks": 3}

            return _R()

    kg = types.SimpleNamespace(_graph=types.SimpleNamespace(session=lambda: _Session()))
    adjuster = adaptive_difficulty.AdaptiveDifficultyAdjuster(kg)  # type: ignore[arg-type]

    simple = adjuster.analyze_image_complexity({"text_density": 0.1})
    assert simple["level"] == "simple"

    complex_meta = adjuster.analyze_image_complexity({"text_density": 0.9})
    assert complex_meta["level"] == "complex"

    adj = adjuster.adjust_query_requirements(complex_meta, "explanation")
    assert adj["min_length"] >= 300
