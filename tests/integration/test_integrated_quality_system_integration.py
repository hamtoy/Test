from __future__ import annotations

import sys
import types
from typing import Any

import pytest


@pytest.mark.asyncio
async def test_generate_qa_with_all_enhancements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mocked end-to-end path of IntegratedQualitySystem without external services."""

    # Provide dummy modules to satisfy imports in multimodal_understanding
    monkeypatch.setitem(
        sys.modules,
        "pytesseract",
        types.SimpleNamespace(
            image_to_string=lambda img, lang=None: "",
            pytesseract=types.SimpleNamespace(tesseract_cmd=None),
        ),
    )
    fake_pil = types.ModuleType("PIL")

    class _FakeImageObj:
        width = 100
        height = 100

    class _FakeImageModule:
        @staticmethod
        def open(path: str) -> _FakeImageObj:
            return _FakeImageObj()

    setattr(fake_pil, "Image", _FakeImageModule)
    monkeypatch.setitem(sys.modules, "PIL", fake_pil)
    monkeypatch.setitem(sys.modules, "PIL.Image", _FakeImageModule)

    class FakeKG:
        def __init__(self, *_: Any, **__: Any) -> None:
            self._graph = None

    class FakeAugmenter:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def generate_with_augmentation(
            self, user_query: str, query_type: str, base_context: dict[str, Any]
        ) -> str:
            return "augmented-prompt"

    class FakeEnforcer:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def validate_complete_output(
            self, output: str, query_type: str
        ) -> dict[str, Any]:
            return {"valid": True, "issues": []}

    class FakeAdjuster:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def analyze_image_complexity(
            self, image_meta: dict[str, Any]
        ) -> dict[str, Any]:
            return {"text_density": 0.5, "has_structure": False, "level": "simple"}

        def adjust_query_requirements(
            self, complexity: dict[str, Any], query_type: str
        ) -> dict[str, Any]:
            return {"min_length": 100, "depth": "shallow"}

    class FakeValidator:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def cross_validate_qa_pair(
            self,
            question: str,
            answer: str,
            query_type: str,
            image_meta: dict[str, Any],
        ) -> dict[str, Any]:
            return {"valid": True, "issues": []}

    class FakeExampleSelector:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def select_best_examples(
            self, query_type: str, context: dict[str, Any], k: int = 3
        ) -> list[dict[str, str]]:
            return [{"example": "ex1"}]

    class FakeMultimodal:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        async def analyze_image_deep(self, image_path: str) -> dict[str, Any]:
            return {"text_density": 0.5, "has_table_chart": False, "path": image_path}

    class FakeLLM:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def generate(self, prompt: str, role: str = "generator") -> str:
            return "fake-llm-output"

    class FakeSelfCorrector:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def generate_with_self_correction(
            self, query_type: str, context: dict[str, Any]
        ) -> dict[str, Any]:
            return {"output": "fake-llm-output", "iterations": 1, "validation": "yes"}

    class FakeAutocomplete:
        def __init__(self, *_: Any, **__: Any) -> None:
            pass

        def suggest_constraint_compliance(
            self, draft_output: str, query_type: str
        ) -> dict[str, list[str]]:
            return {"violations": [], "suggestions": []}

    # Patch the actual modules where the classes are defined/imported
    from src.qa import quality

    monkeypatch.setattr(quality, "QAKnowledgeGraph", FakeKG, raising=True)
    monkeypatch.setattr(
        quality, "AdvancedContextAugmentation", FakeAugmenter, raising=True
    )
    monkeypatch.setattr(
        quality, "RealTimeConstraintEnforcer", FakeEnforcer, raising=True
    )
    monkeypatch.setattr(
        quality, "AdaptiveDifficultyAdjuster", FakeAdjuster, raising=True
    )
    monkeypatch.setattr(quality, "CrossValidationSystem", FakeValidator, raising=True)
    monkeypatch.setattr(
        quality, "DynamicExampleSelector", FakeExampleSelector, raising=True
    )
    monkeypatch.setattr(
        quality, "MultimodalUnderstanding", FakeMultimodal, raising=True
    )
    monkeypatch.setattr(quality, "GeminiModelClient", FakeLLM, raising=True)
    monkeypatch.setattr(
        quality, "SelfCorrectingQAChain", FakeSelfCorrector, raising=True
    )
    monkeypatch.setattr(quality, "SmartAutocomplete", FakeAutocomplete, raising=True)

    system = quality.IntegratedQualitySystem("bolt://fake", "user", "pass")
    result = await system.generate_qa_with_all_enhancements("fake.jpg", "explanation")

    assert result["output"] == "fake-llm-output"
    assert result["validation"]["valid"] is True
    assert result["metadata"]["examples_used"] == [{"example": "ex1"}]
    assert result["constraint_check"]["violations"] == []
    assert result["self_correction"]["iterations"] == 1
