import types

from src.advanced_context_augmentation import AdvancedContextAugmentation


class _FakeSingle:
    def __init__(self, blocks, rules):
        self._blocks = blocks
        self._rules = rules

    def get(self, key):
        if key == "blocks":
            return self._blocks
        if key == "rules":
            return self._rules
        return None


class _FakeResult:
    def __init__(self, single_obj):
        self.single_obj = single_obj

    def single(self):
        return self.single_obj


class _FakeSession:
    def __init__(self, single_obj):
        self.single_obj = single_obj

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, *args, **kwargs):
        return _FakeResult(self.single_obj)


class _FakeDriver:
    def __init__(self, single_obj):
        self.single_obj = single_obj

    def session(self):
        return _FakeSession(self.single_obj)


def _make_augmenter(blocks, rules):
    aug = object.__new__(AdvancedContextAugmentation)
    aug.graph = types.SimpleNamespace(_driver=_FakeDriver(_FakeSingle(blocks, rules)))
    aug.vector_index = None
    return aug


def test_augment_prompt_without_vector_index():
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


def test_generate_with_augmentation_builds_prompt():
    blocks = [{"content": "case"}]
    rules = [{"rule": "rule text", "priority": 1, "examples": ["ex"]}]
    aug = _make_augmenter(blocks, rules)

    prompt = aug.generate_with_augmentation(
        "user query", "summary", base_context={"foo": "bar"}
    )
    assert "user query" in prompt
    assert "rule text" in prompt
    assert "case" in prompt
