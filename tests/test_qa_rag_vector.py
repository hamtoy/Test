from src.qa.rag_system import QAKnowledgeGraph
from typing import Any


class FakeDoc:
    def __init__(self, content: str) -> None:
        self.page_content = content


class FakeVectorStore:
    def __init__(self, contents: Any) -> None:
        self._contents = contents

    def similarity_search(self, query: str, k: int = 5) -> Any:
        # Return up to k docs regardless of query; enough to test plumbing.
        return [FakeDoc(c) for c in self._contents[:k]]


def _make_kg_with_vector(contents: Any) -> Any:
    kg = object.__new__(QAKnowledgeGraph)
    kg._vector_store = FakeVectorStore(contents)
    kg._graph = None  # not used in these tests
    return kg


def test_find_relevant_rules_returns_page_content() -> None:
    kg = _make_kg_with_vector(["rule A", "rule B"])
    results = kg.find_relevant_rules("query", k=1)
    assert results == ["rule A"]


def test_find_relevant_rules_empty_when_no_vector_store() -> None:
    kg = object.__new__(QAKnowledgeGraph)
    kg._vector_store = None
    kg._graph = None
    assert kg.find_relevant_rules("query") == []
