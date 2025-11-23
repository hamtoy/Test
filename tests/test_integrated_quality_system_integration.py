from __future__ import annotations

import importlib
import sys
import types
from typing import Any, Dict


def test_generate_qa_with_all_enhancements(monkeypatch):
    """Mocked end-to-end path of IntegratedQualitySystem without external services."""

    # Provide dummy modules to satisfy imports in multimodal_understanding
    sys.modules["pytesseract"] = types.SimpleNamespace(
        image_to_string=lambda img, lang=None: ""
    )
    fake_pil = types.ModuleType("PIL")

    class _FakeImageObj:
        width = 100
        height = 100

    class _FakeImageModule:
        @staticmethod
        def open(path):
            return _FakeImageObj()

    fake_pil.Image = _FakeImageModule
    sys.modules["PIL"] = fake_pil
    sys.modules["PIL.Image"] = _FakeImageModule

    iqs = importlib.import_module("src.integrated_quality_system")

    class FakeKG:
        def __init__(self, *_, **__):
            self._graph = None

    class FakeAugmenter:
        def __init__(self, *_, **__):
            pass

        def generate_with_augmentation(
            self, user_query: str, query_type: str, base_context: Dict[str, Any]
        ) -> str:
            return "augmented-prompt"

    class FakeEnforcer:
        def __init__(self, *_, **__):
            pass

    class FakeAdjuster:
        def __init__(self, *_, **__):
            pass

        def analyze_image_complexity(self, image_meta: Dict[str, Any]) -> Dict[str, Any]:
            return {"text_density": 0.5, "has_structure": False, "level": "simple"}

        def adjust_query_requirements(
            self, complexity: Dict[str, Any], query_type: str
        ) -> Dict[str, Any]:
            return {"min_length": 100, "depth": "shallow"}

    class FakeValidator:
        def __init__(self, *_, **__):
            pass

        def cross_validate_qa_pair(
            self, question: str, answer: str, query_type: str, image_meta: Dict[str, Any]
        ) -> Dict[str, Any]:
            return {"valid": True, "issues": []}

    class FakeExampleSelector:
        def __init__(self, *_, **__):
            pass

        def select_best_examples(
            self, query_type: str, context: Dict[str, Any], k: int = 3
        ):
            return [{"example": "ex1"}]

    class FakeMultimodal:
        def __init__(self, *_, **__):
            pass

        def analyze_image_deep(self, image_path: str) -> Dict[str, Any]:
            return {"text_density": 0.5, "has_table_chart": False, "path": image_path}

    class FakeLLM:
        def __init__(self, *_, **__):
            pass

        def generate(self, prompt: str, role: str = "generator") -> str:
            return "fake-llm-output"

    monkeypatch.setattr(iqs, "QAKnowledgeGraph", FakeKG, raising=True)
    monkeypatch.setattr(iqs, "AdvancedContextAugmentation", FakeAugmenter, raising=True)
    monkeypatch.setattr(iqs, "RealTimeConstraintEnforcer", FakeEnforcer, raising=True)
    monkeypatch.setattr(iqs, "AdaptiveDifficultyAdjuster", FakeAdjuster, raising=True)
    monkeypatch.setattr(iqs, "CrossValidationSystem", FakeValidator, raising=True)
    monkeypatch.setattr(iqs, "DynamicExampleSelector", FakeExampleSelector, raising=True)
    monkeypatch.setattr(iqs, "MultimodalUnderstanding", FakeMultimodal, raising=True)
    monkeypatch.setattr(iqs, "GeminiModelClient", FakeLLM, raising=True)

    system = iqs.IntegratedQualitySystem("bolt://fake", "user", "pass")
    result = system.generate_qa_with_all_enhancements("fake.jpg", "explanation")

    assert result["output"] == "fake-llm-output"
    assert result["validation"]["valid"] is True
    assert result["metadata"]["examples_used"] == [{"example": "ex1"}]
