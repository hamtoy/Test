from __future__ import annotations

from types import SimpleNamespace

from src.qa.rag_system import QAKnowledgeGraph
from typing import Any


class _FakeVectorStore:
    def __init__(self, contents: Any) -> None:
        self._contents = contents

    def similarity_search(self, query: str, k: int = 5) -> Any:
        # Return Fake docs with page_content attribute.
        return [SimpleNamespace(page_content=c) for c in self._contents[:k]]


class _FakeSession:
    def __init__(self, rows: Any) -> None:
        self._rows = rows

    def run(self, _cypher: Any, **_kwargs: Any) -> Any:
        return self._rows

    def __enter__(self) -> Any:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Any:
        return False


class _FakeGraph:
    def __init__(self, rows: Any) -> None:
        self._rows = rows

    def session(self) -> Any:
        return _FakeSession(self._rows)


def test_find_relevant_rules_returns_page_content() -> None:
    kg = object.__new__(QAKnowledgeGraph)
    kg._vector_store = _FakeVectorStore(["rule A", "rule B"])
    assert kg.find_relevant_rules("query", k=1) == ["rule A"]


def test_get_constraints_for_query_type_maps_records() -> None:
    fake_rows = [
        {"id": "c1", "description": "desc", "type": "prohibition", "pattern": "x"}
    ]
    kg = object.__new__(QAKnowledgeGraph)
    kg._graph = _FakeGraph(fake_rows)  # type: ignore[assignment]
    constraints = kg.get_constraints_for_query_type("any")
    assert constraints == fake_rows


def test_validate_session_empty_turns() -> None:
    kg = object.__new__(QAKnowledgeGraph)
    assert kg.validate_session({"turns": []}) == {
        "ok": False,
        "issues": ["turns가 비어있습니다."],
    }


def test_del_closes_graph() -> None:
    class _Graph:
        def __init__(self) -> None:
            self.closed = 0

        def close(self) -> None:
            self.closed += 1

    kg = object.__new__(QAKnowledgeGraph)
    graph = _Graph()
    kg._graph = graph  # type: ignore[assignment]
    kg._graph_provider = None
    kg._graph_finalizer = None

    kg.__del__()  # 직접 호출해 close 동작 확인
    assert graph.closed == 1
