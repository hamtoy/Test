from __future__ import annotations

import types

from src.advanced_context_augmentation import AdvancedContextAugmentation


def test_augment_without_vector_store(monkeypatch):
    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            return types.SimpleNamespace(
                single=lambda: {
                    "blocks": [{"content": "text", "id": "b1"}],
                    "rules": [{"rule": "r1", "priority": 1, "examples": ["ex"]}],
                }
            )

    class _Driver:
        def session(self):
            return _Session()

    aug = AdvancedContextAugmentation.__new__(AdvancedContextAugmentation)
    aug.vector_index = None
    aug.graph = types.SimpleNamespace(_driver=_Driver())

    result = aug.augment_prompt_with_similar_cases("q", "explanation")
    assert result["similar_cases"] == ["text"]
    assert result["relevant_rules"][0]["rule"] == "r1"
