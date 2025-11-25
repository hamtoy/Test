from __future__ import annotations

import types
from src import graph_schema_builder as gsb
from src import graph_enhanced_router
from src import custom_callback


def test_graph_schema_builder_runs_with_stubbed_driver(monkeypatch):
    class _Result(list):
        def data(self):
            return list(self)

        def single(self):
            return self[0] if self else {"links": 0}

    class _BuilderSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, query, **_kwargs):
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
        def __init__(self):
            self.session_obj = _BuilderSession()

        def session(self):
            return self.session_obj

        def close(self):
            return None

    class _GraphDB:
        @staticmethod
        def driver(*_args, **_kwargs):
            return _BuilderDriver()

    monkeypatch.setattr(gsb, "GraphDatabase", _GraphDB)

    builder = gsb.QAGraphBuilder("uri", "user", "pw")
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


def test_graph_enhanced_router(monkeypatch):
    class _RouterSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            return [
                {"name": "summary", "korean": "요약", "limit": 1},
                {"name": "explanation", "korean": "설명", "limit": 2},
            ]

    class _FakeKG:
        def __init__(self):
            self._graph = types.SimpleNamespace(session=lambda: _RouterSession())

    class _FakeLLM:
        def generate(self, prompt, role="router"):
            return "summary"

    chosen = {}

    def _handler(user_input):
        chosen["value"] = user_input
        return "ok"

    router = graph_enhanced_router.GraphEnhancedRouter(_FakeKG(), _FakeLLM())
    result = router.route_and_generate("hello", {"summary": _handler})
    assert result["choice"] == "summary"
    assert result["output"] == "ok"
    prompt_text = router._build_router_prompt(
        "hello", [{"name": "summary", "korean": "요약", "limit": 1}]
    )
    assert "요약" in prompt_text


def test_custom_callback_logs(monkeypatch):
    monkeypatch.setenv("NEO4J_URI", "bolt://fake")
    monkeypatch.setenv("NEO4J_USER", "u")
    monkeypatch.setenv("NEO4J_PASSWORD", "p")

    class _CBSession:
        def __init__(self, store):
            self.store = store

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, query, **params):
            self.store.append((query, params))

    class _CBDriver:
        def __init__(self, store):
            self.store = store

        def session(self):
            return _CBSession(self.store)

        def close(self):
            return None

    store: list = []

    class _GraphDB:
        @staticmethod
        def driver(*_args, **_kwargs):
            return _CBDriver(store)

    monkeypatch.setattr(custom_callback, "GraphDatabase", _GraphDB)
    cb = custom_callback.Neo4jLoggingCallback()
    cb.on_llm_start({}, ["prompt"])
    cb.on_llm_end("response")
    cb.on_chain_error(Exception("boom"))
    assert len(store) == 3
    cb.close()
