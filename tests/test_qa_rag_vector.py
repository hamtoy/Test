from src.qa.rag_system import QAKnowledgeGraph


class FakeDoc:
    def __init__(self, content: str):
        self.page_content = content


class FakeVectorStore:
    def __init__(self, contents):
        self._contents = contents

    def similarity_search(self, query: str, k: int = 5):
        # Return up to k docs regardless of query; enough to test plumbing.
        return [FakeDoc(c) for c in self._contents[:k]]


def _make_kg_with_vector(contents):
    kg = object.__new__(QAKnowledgeGraph)
    kg._vector_store = FakeVectorStore(contents)
    kg._graph = None  # not used in these tests
    return kg


def test_find_relevant_rules_returns_page_content():
    kg = _make_kg_with_vector(["rule A", "rule B"])
    results = kg.find_relevant_rules("query", k=1)
    assert results == ["rule A"]


def test_find_relevant_rules_empty_when_no_vector_store():
    kg = object.__new__(QAKnowledgeGraph)
    kg._vector_store = None
    kg._graph = None
    assert kg.find_relevant_rules("query") == []
