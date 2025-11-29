import pytest
from __future__ import annotations

import types
from src.features import self_correcting as self_correcting_chain
from src.llm import langchain_system as ulqa
from typing import Any


def test_self_correcting_chain_stops_on_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    class _KG:
        def get_constraints_for_query_type(self, _qt: Any) -> Any:
            return [{"description": "rule-1"}]

    class _LLM:
        def __init__(self) -> None:
            self.calls = []

        def generate(self, prompt: Any, role: Any="default") -> Any:
            self.calls.append(role)
            if role == "validator":
                return "yes, all good"
            return f"{role}-out"

    chain = self_correcting_chain.SelfCorrectingQAChain(_KG(), _LLM())  # type: ignore[arg-type]
    result = chain.generate_with_self_correction("explanation", {"ctx": 1})

    assert result["iterations"] == 1
    assert result["output"] == "correct-out"
    assert result["validation"]


def test_ultimate_langchain_qa_system_wires_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    class _KG:
        def __init__(self) -> None:
            self._graph = types.SimpleNamespace(session=lambda: None)

    class _Memory:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.logged = []

        def _log_interaction(self, q: Any, a: Any) -> None:
            self.logged.append((q, a))

    class _Agent:
        def __init__(self, kg: Any) -> None:
            self.kg = kg

        def collaborative_generate(self, qt: Any, ctx: Any) -> Any:
            return {"metadata": {"m": 1}, "output": "agent"}

    class _Correct:
        def __init__(self, kg: Any, llm: Any=None) -> None:
            self.kg = kg

        def generate_with_self_correction(self, qt: Any, meta: Any) -> Any:
            return {"output": "corrected", "iterations": 1, "validation": "ok"}

    class _Router:
        def __init__(self, kg: Any, llm: Any=None) -> None:
            self.kg = kg

        def route_and_generate(self, user_input: Any, handlers: Any) -> Any:
            return {"choice": "explanation"}

    class _LCEL:
        def __init__(self, kg: Any, llm: Any=None) -> None:
            self.kg = kg

    monkeypatch.setattr(ulqa, "QAKnowledgeGraph", _KG)
    monkeypatch.setattr(ulqa, "MemoryAugmentedQASystem", _Memory)
    monkeypatch.setattr(ulqa, "MultiAgentQASystem", _Agent)
    monkeypatch.setattr(ulqa, "SelfCorrectingQAChain", _Correct)
    monkeypatch.setattr(ulqa, "GraphEnhancedRouter", _Router)
    monkeypatch.setattr(ulqa, "LCELOptimizedChain", _LCEL)
    monkeypatch.setattr(ulqa, "GeminiModelClient", lambda: None)

    system = ulqa.UltimateLangChainQASystem()
    out = system.generate_ultimate_qa("img.png", user_query="hi")

    assert out["output"] == "corrected"
    assert out["metadata"]["iterations"] == 1
