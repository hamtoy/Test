from __future__ import annotations

from types import SimpleNamespace

from src.qa_rag_system import QAKnowledgeGraph


class _FakeVectorStore:
    def __init__(self, contents):
        self._contents = contents

    def similarity_search(self, query: str, k: int = 5):
        # Return Fake docs with page_content attribute.
        return [SimpleNamespace(page_content=c) for c in self._contents[:k]]


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows

    def run(self, _cypher, **_kwargs):
        return self._rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class _FakeGraph:
    def __init__(self, rows):
        self._rows = rows

    def session(self):
        return _FakeSession(self._rows)


def test_find_relevant_rules_returns_page_content():
    kg = object.__new__(QAKnowledgeGraph)
    kg._vector_store = _FakeVectorStore(["rule A", "rule B"])
    assert kg.find_relevant_rules("query", k=1) == ["rule A"]


def test_get_constraints_for_query_type_maps_records():
    fake_rows = [
        {"id": "c1", "description": "desc", "type": "prohibition", "pattern": "x"}
    ]
    kg = object.__new__(QAKnowledgeGraph)
    kg._graph = _FakeGraph(fake_rows)
    constraints = kg.get_constraints_for_query_type("any")
    assert constraints == fake_rows


def test_validate_session_empty_turns():
    kg = object.__new__(QAKnowledgeGraph)
    assert kg.validate_session({"turns": []}) == {
        "ok": False,
        "issues": ["turns가 비어있습니다."],
    }
