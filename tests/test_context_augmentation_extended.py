from pathlib import Path
from typing import Any

from __future__ import annotations

import types
from src.processing import context_augmentation as aca


def test_advanced_context_augmentation_vector_index(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Doc:
        def __init__(self, text) -> None:
            self.page_content = text
            self.metadata = {"id": 1}

    class _Result:
        def data(self_inner):
            return [{"rule": "R", "priority": 1, "examples": ["ex1"]}]

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            return _Result()

    class _Driver:
        def session(self):
            return _Session()

    aug = aca.AdvancedContextAugmentation.__new__(aca.AdvancedContextAugmentation)
    aug.vector_index = types.SimpleNamespace(  # type: ignore[assignment]
        similarity_search=lambda q, k=5: [_Doc("doc")]
    )
    aug.graph = types.SimpleNamespace(_driver=_Driver())  # type: ignore[assignment]

    out = aug.augment_prompt_with_similar_cases("q", "explanation")
    assert out["similar_cases"] == ["doc"]
    assert out["relevant_rules"]


def test_advanced_context_augmentation_fallback_graph() -> None:
    record = {
        "blocks": [{"content": "b"}],
        "rules": [{"rule": "r", "priority": 1, "examples": ["e"]}],
    }

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            class _Res:
                def single(self_inner):
                    return record

            return _Res()

    aug = aca.AdvancedContextAugmentation.__new__(aca.AdvancedContextAugmentation)
    aug.vector_index = None
    aug.graph = types.SimpleNamespace(  # type: ignore[assignment]
        _driver=types.SimpleNamespace(session=lambda: _Session())
    )

    out = aug.augment_prompt_with_similar_cases("q", "explanation")
    assert out["similar_cases"]
    assert out["relevant_rules"]


def test_generate_with_augmentation_formats(monkeypatch: pytest.MonkeyPatch) -> None:
    aug = aca.AdvancedContextAugmentation.__new__(aca.AdvancedContextAugmentation)
    monkeypatch.setattr(
        aug,
        "augment_prompt_with_similar_cases",
        lambda uq, qt: {
            "similar_cases": ["case"],
            "relevant_rules": [{"rule": "R", "priority": 1, "examples": ["ex"]}],
            "query_type": qt,
        },
    )
    prompt = aug.generate_with_augmentation("u", "explanation", {"ctx": 1})
    assert "Similar Successful Cases" in prompt
