from __future__ import annotations

import types
import sys
from typing import Any

import pytest

from src.analysis import cross_validation
from src.llm import lcel_chain as lcel_optimized_chain
from src.qa import memory_augmented as memory_augmented_qa
from src.qa import multi_agent as multi_agent_qa_system
from src.qa import memory_augmented


def test_cross_validation_scoring(monkeypatch: pytest.MonkeyPatch) -> None:
    class _CVSession:
        def __enter__(self) -> "_CVSession":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

        def run(self, query: str, **_kwargs: Any) -> Any:
            if "collect(b.content)" in query:
                return types.SimpleNamespace(
                    single=lambda: {"all_content": ["Alpha beta content"]}
                )
            if "ErrorPattern" in query:
                return [
                    {"pattern": "error", "description": "error desc"},
                ]
            return []

    class _FakeKG:
        def __init__(self) -> None:
            self._graph = types.SimpleNamespace(session=lambda: _CVSession())
            self._vector_store = None

        def get_constraints_for_query_type(self, _qt: str) -> list[dict[str, str]]:
            return [
                {"type": "prohibition", "pattern": "forbidden", "description": "nope"}
            ]

    cvs = cross_validation.CrossValidationSystem(_FakeKG())  # type: ignore[arg-type]
    result = cvs.cross_validate_qa_pair(
        "What is alpha?",
        "forbidden error response with alpha token",
        "explanation",
        {"page_id": "p1"},
    )
    assert 0 <= result["overall_score"] <= 1
    assert result["rule_compliance"]["violations"]


def test_lcel_optimized_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    class _LCELSession:
        def __enter__(self) -> "_LCELSession":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

        def run(self, *_args: Any, **_kwargs: Any) -> list[dict[str, str]]:
            return [{"text": "rule text"}]

    class _FakeKG:
        def __init__(self) -> None:
            self._graph = types.SimpleNamespace(session=lambda: _LCELSession())

        def get_examples(self, limit: int = 3) -> list[dict[str, str]]:
            return [{"text": f"ex{idx}"} for idx in range(limit)]

        def get_constraints_for_query_type(self, qt: str) -> list[dict[str, str]]:
            return [{"description": f"constraint for {qt}"}]

    class _FakeLLM:
        def generate(self, prompt: str, role: str = "lcel") -> str:
            return f"generated:{role}"

    chain = lcel_optimized_chain.LCELOptimizedChain(_FakeKG(), _FakeLLM())  # type: ignore[arg-type]
    merged = chain._merge_context(
        {"rules": ["r"], "examples": ["e"], "constraints": ["c"], "context": {"x": 1}}
    )
    formatted = chain._format_prompt(
        {
            "rules": ["r"],
            "examples": ["e"],
            "constraints": ["c"],
            "original_context": {},
        }
    )
    assert "- r" in formatted
    assert merged["rules"] == ["r"]
    assert chain._call_llm("prompt") == "generated:lcel"
    output = chain.invoke({"query_type": "explanation", "context": {"foo": "bar"}})
    assert isinstance(output, str)


def test_memory_augmented_qa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(memory_augmented_qa, "require_env", lambda _v: "val")
    monkeypatch.setattr(
        memory_augmented_qa, "CustomGeminiEmbeddings", lambda api_key: object()
    )

    class _FakeSession:
        def __enter__(self) -> "_FakeSession":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

        def run(self, *_args: Any, **_kwargs: Any) -> None:
            return None

    class _FakeDriver:
        def session(self) -> _FakeSession:
            return _FakeSession()

        def close(self) -> None:
            return None

    class _FakeSafeDriver:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self._driver = _FakeDriver()

        def session(self) -> _FakeSession:
            return _FakeSession()

        def close(self) -> None:
            return None

    class _GraphDB:
        @staticmethod
        def driver(*_args: Any, **_kwargs: Any) -> _FakeDriver:
            return _FakeDriver()

    class _FakeVector:
        def similarity_search(
            self, *_args: Any, **_kwargs: Any
        ) -> list[types.SimpleNamespace]:
            return [types.SimpleNamespace(page_content="doc1")]

    class _FakeNeo4jVector:
        @staticmethod
        def from_existing_graph(*_args: Any, **_kwargs: Any) -> _FakeVector:
            return _FakeVector()

    monkeypatch.setitem(
        sys.modules,
        "langchain_neo4j",
        types.SimpleNamespace(Neo4jVector=_FakeNeo4jVector),
    )
    monkeypatch.setattr(memory_augmented, "GraphDatabase", _GraphDB)
    monkeypatch.setattr(
        memory_augmented,
        "GeminiModelClient",
        lambda: types.SimpleNamespace(generate=lambda *_a, **_k: "answer"),
    )
    monkeypatch.setattr(
        memory_augmented,
        "create_sync_driver",
        lambda *args, **kwargs: _FakeSafeDriver(),
    )
    monkeypatch.setattr(
        memory_augmented,
        "CustomGeminiEmbeddings",
        lambda **kwargs: types.SimpleNamespace(),
    )
    monkeypatch.setattr(
        memory_augmented,
        "require_env",
        lambda key: "fake-key",
    )

    system = memory_augmented_qa.MemoryAugmentedQASystem(
        neo4j_uri="bolt://fake", user="user", password="pass"
    )
    resp = system.ask_with_memory("무엇을 해야 하나요?")
    assert resp == "answer"
    assert system.history[-1]["q"] == "무엇을 해야 하나요?"
    system.close()


def test_multi_agent_qa_system(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeRuleSession:
        def __enter__(self) -> "_FakeRuleSession":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

        def run(self, *_args: Any, **_kwargs: Any) -> list[dict[str, str]]:
            return [{"text": "rule text"}]

    class _FakeKG:
        def __init__(self) -> None:
            self._graph = types.SimpleNamespace(session=lambda: _FakeRuleSession())

        def get_constraints_for_query_type(self, _qt: str) -> list[dict[str, str]]:
            return [{"description": "c1"}]

    class _FakeLLM:
        def generate(self, prompt: str, role: str = "generator") -> str:
            return f"output for {role}"

    class _FakeExampleSelector:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def select_best_examples(
            self, *_args: Any, **_kwargs: Any
        ) -> list[dict[str, str]]:
            return [{"example": "ex"}]

    class _FakeValidator:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def cross_validate_qa_pair(self, **_kwargs: Any) -> dict[str, bool]:
            return {"valid": True}

    fake_kg = _FakeKG()
    fake_kg._graph = types.SimpleNamespace(session=lambda: _FakeRuleSession())

    # Import the actual module (not the shim) so we can patch it before it's used.
    # This must be done here, not at the top, to ensure the monkeypatch takes effect
    # before MultiAgentQASystem imports GeminiModelClient from this module.
    from src.qa import multi_agent as multi_agent_module

    monkeypatch.setattr(multi_agent_module, "GeminiModelClient", lambda: _FakeLLM())
    monkeypatch.setattr(
        multi_agent_module,
        "DynamicExampleSelector",
        lambda kg: _FakeExampleSelector(),
    )
    monkeypatch.setattr(
        multi_agent_module, "CrossValidationSystem", lambda kg: _FakeValidator()
    )

    system = multi_agent_qa_system.MultiAgentQASystem(fake_kg)  # type: ignore[arg-type]
    result = system.collaborative_generate("explanation", {"page_id": "p1"})
    assert result["metadata"]["examples_used"]
    assert result["validation"]["valid"] is True
