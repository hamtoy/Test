from __future__ import annotations

import types

from src.processing.context_augmentation import AdvancedContextAugmentation
from typing import Any


def test_augment_without_vector_store(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Session:
        def __enter__(self) -> Any:
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
            return False

        def run(self, *_args: Any, **_kwargs: Any) -> Any:
            return types.SimpleNamespace(
                single=lambda: {
                    "blocks": [{"content": "text", "id": "b1"}],
                    "rules": [{"rule": "r1", "priority": 1, "examples": ["ex"]}],
                }
            )

    class _Driver:
        def session(self) -> Any:
            return _Session()

    aug = AdvancedContextAugmentation.__new__(AdvancedContextAugmentation)
    aug.vector_index = None
    aug.graph = types.SimpleNamespace(_driver=_Driver())  # type: ignore[assignment]

    result = aug.augment_prompt_with_similar_cases("q", "explanation")
    assert result["similar_cases"] == ["text"]
    assert result["relevant_rules"][0]["rule"] == "r1"
