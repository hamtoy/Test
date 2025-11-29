import types

from src.processing.context_augmentation import AdvancedContextAugmentation
from typing import Any


class _FakeSingle:
    def __init__(self, blocks: Any, rules: Any) -> None:
        self._blocks = blocks
        self._rules = rules

    def get(self, key: Any) -> Any:
        if key == "blocks":
            return self._blocks
        if key == "rules":
            return self._rules
        return None


class _FakeResult:
    def __init__(self, single_obj: Any) -> None:
        self.single_obj = single_obj

    def single(self) -> Any:
        return self.single_obj


class _FakeSession:
    def __init__(self, single_obj: Any) -> None:
        self.single_obj = single_obj

    def __enter__(self) -> Any:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
        return False

    def run(self, *args: Any, **kwargs: Any) -> Any:
        return _FakeResult(self.single_obj)


class _FakeDriver:
    def __init__(self, single_obj: Any) -> None:
        self.single_obj = single_obj

    def session(self) -> Any:
        return _FakeSession(self.single_obj)


def _make_augmenter(blocks: Any, rules: Any) -> Any:
    aug = object.__new__(AdvancedContextAugmentation)
    aug.graph = types.SimpleNamespace(_driver=_FakeDriver(_FakeSingle(blocks, rules)))  # type: ignore[assignment]
    aug.vector_index = None
    return aug


def test_augment_prompt_without_vector_index() -> None:
    blocks = [
        {"content": "block text 1"},
        {"text": "block text 2"},
    ]
    rules = [{"rule": "r1", "priority": 1, "examples": ["ex1"]}]
    aug = _make_augmenter(blocks, rules)

    result = aug.augment_prompt_with_similar_cases("query", "explanation")
    assert result["query_type"] == "explanation"
    assert len(result["similar_cases"]) == 2
    assert result["relevant_rules"][0]["rule"] == "r1"


def test_generate_with_augmentation_builds_prompt() -> None:
    blocks = [{"content": "case"}]
    rules = [{"rule": "rule text", "priority": 1, "examples": ["ex"]}]
    aug = _make_augmenter(blocks, rules)

    prompt = aug.generate_with_augmentation(
        "user query", "summary", base_context={"foo": "bar"}
    )
    assert "user query" in prompt
    assert "rule text" in prompt
    assert "case" in prompt
