import types

from neo4j.exceptions import Neo4jError

from src.routing.graph_router import GraphEnhancedRouter


class _FakeLLM:
    def __init__(self, reply: str) -> None:
        self.reply = reply

    def generate(self, prompt: str, role: str | None = None) -> str:  # noqa: ARG002
        return self.reply


def test_route_and_generate_match(monkeypatch) -> None:
    router = GraphEnhancedRouter(kg=types.SimpleNamespace(), llm=_FakeLLM("summary"))  # type: ignore[arg-type]
    monkeypatch.setattr(
        router,
        "_fetch_query_types",
        lambda: [
            {"name": "explanation", "korean": "설명"},
            {"name": "summary", "korean": "요약"},
        ],
    )
    monkeypatch.setattr(router, "_log_routing", lambda input_text, chosen: None)

    handlers = {"summary": lambda text: f"handled:{text}"}
    result = router.route_and_generate("hello", handlers)
    assert result["choice"] == "summary"
    assert result["output"] == "handled:hello"


def test_route_and_generate_fallback_first(monkeypatch) -> None:
    router = GraphEnhancedRouter(kg=types.SimpleNamespace(), llm=_FakeLLM("unknown"))  # type: ignore[arg-type]
    monkeypatch.setattr(
        router,
        "_fetch_query_types",
        lambda: [
            {"name": "explanation", "korean": "설명"},
            {"name": "summary", "korean": "요약"},
        ],
    )
    monkeypatch.setattr(router, "_log_routing", lambda input_text, chosen: None)

    handlers = {"explanation": lambda text: f"exp:{text}"}
    result = router.route_and_generate("world", handlers)
    assert result["choice"] == "explanation"
    assert result["output"] == "exp:world"


def test_build_router_prompt_no_qtypes() -> None:
    router = GraphEnhancedRouter(kg=types.SimpleNamespace(), llm=_FakeLLM("any"))  # type: ignore[arg-type]
    prompt = router._build_router_prompt("input text", [])  # noqa: SLF001
    assert "등록된 QueryType 없음" in prompt
    assert "input text" in prompt


def test_fetch_query_types_error(monkeypatch) -> None:
    class _BadGraph:
        def session(self) -> None:
            raise Neo4jError("boom")

    router = GraphEnhancedRouter(
        kg=types.SimpleNamespace(_graph=_BadGraph()),  # type: ignore[arg-type]
        llm=_FakeLLM("any"),  # type: ignore[arg-type]
    )
    qtypes = router._fetch_query_types()
    assert qtypes == []
