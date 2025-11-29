from __future__ import annotations

import types
from typing import Any

import pytest

from src.graph import builder as graph
from src.routing import graph_router as graph_enhanced_router
from src.infra import callbacks as custom_callback


def test_graph_schema_builder_runs_with_stubbed_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Result(list[Any]):
        def data(self) -> Any:
            return list(self)

        def single(self) -> Any:
            return self[0] if self else {"links": 0}

    class _BuilderSession:
        def __enter__(self) -> Any:
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
            return False

        def run(self, query: Any, **_kwargs: Any) -> Any:
            if "heading_1" in query and "자주 틀리는" in query:
                return _Result([{"page_id": "p1", "start_order": 0, "section": "S"}])
            if "WHERE b.order >" in query:
                return _Result(
                    [
                        {
                            "id": "b1",
                            "content": "This is a useful rule text",
                            "type": "paragraph",
                        },
                        {"id": "b2", "content": "Stop", "type": "heading_1"},
                    ]
                )
            if "MATCH (b:Block {id:" in query:
                return _Result([{"content": "Child rule text is long enough"}])
            if "RETURN DISTINCT b.content AS text" in query:
                return _Result([{"text": "⭕ 좋은 예시 텍스트", "type": "positive"}])
            if "RETURN count(" in query:
                return _Result([{"links": 2}])
            return _Result([{}])

    class _BuilderDriver:
        def __init__(self) -> None:
            self.session_obj = _BuilderSession()

        def session(self) -> Any:
            return self.session_obj

        def close(self) -> Any:
            return None

    class _GraphDB:
        @staticmethod
        def driver(*_args: Any, **_kwargs: Any) -> Any:
            return _BuilderDriver()

    monkeypatch.setattr(graph, "GraphDatabase", _GraphDB)

    builder = graph.QAGraphBuilder("uri", "user", "pw")
    builder.create_schema_constraints()
    builder.extract_rules_from_notion()
    builder.extract_query_types()
    builder.extract_constraints()
    builder.create_templates()
    builder.link_rules_to_constraints()
    builder.link_rules_to_query_types()
    builder.extract_examples()
    builder.link_examples_to_rules()
    builder.create_error_patterns()
    builder.create_best_practices()
    builder.close()


def test_graph_enhanced_router(monkeypatch: pytest.MonkeyPatch) -> None:
    class _RouterSession:
        def __enter__(self) -> Any:
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
            return False

        def run(self, *_args: Any, **_kwargs: Any) -> Any:
            return [
                {"name": "summary", "korean": "요약", "limit": 1},
                {"name": "explanation", "korean": "설명", "limit": 2},
            ]

    class _FakeKG:
        def __init__(self) -> None:
            self._graph = types.SimpleNamespace(session=lambda: _RouterSession())

    class _FakeLLM:
        def generate(self, prompt: Any, role: Any = "router") -> Any:
            return "summary"

    chosen = {}

    def _handler(user_input: Any) -> Any:
        chosen["value"] = user_input
        return "ok"

    router = graph_enhanced_router.GraphEnhancedRouter(_FakeKG(), _FakeLLM())  # type: ignore[arg-type]
    result = router.route_and_generate("hello", {"summary": _handler})
    assert result["choice"] == "summary"
    assert result["output"] == "ok"
    prompt_text = router._build_router_prompt(
        "hello", [{"name": "summary", "korean": "요약", "limit": 1}]
    )
    assert "요약" in prompt_text


def test_custom_callback_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEO4J_URI", "bolt://fake")
    monkeypatch.setenv("NEO4J_USER", "u")
    monkeypatch.setenv("NEO4J_PASSWORD", "p")

    class _CBSession:
        def __init__(self, store: Any) -> None:
            self.store = store

        def __enter__(self) -> Any:
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
            return False

        def run(self, query: Any, **params: Any) -> None:
            self.store.append((query, params))

    class _CBDriver:
        def __init__(self, store: Any) -> None:
            self.store = store

        def session(self) -> Any:
            return _CBSession(self.store)

        def close(self) -> Any:
            return None

    store: list[Any] = []

    class _GraphDB:
        @staticmethod
        def driver(*_args: Any, **_kwargs: Any) -> Any:
            return _CBDriver(store)

    monkeypatch.setattr(custom_callback, "GraphDatabase", _GraphDB)
    cb = custom_callback.Neo4jLoggingCallback()
    cb.on_llm_start({}, ["prompt"])
    cb.on_llm_end("response")
    cb.on_chain_error(Exception("boom"))
    assert len(store) == 3
    cb.close()
