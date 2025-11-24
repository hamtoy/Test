from src.qa_rag_system import QAKnowledgeGraph


class _FakeSession:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, cypher, **params):  # noqa: ARG002
        for r in self.rows:
            yield r


class _FakeGraph:
    def __init__(self, rows):
        self.rows = rows

    def session(self):
        return _FakeSession(self.rows)

    def close(self):
        return None


def _make_kg(rows):
    kg = object.__new__(QAKnowledgeGraph)
    kg._graph = _FakeGraph(rows)
    kg._vector_store = None
    kg.neo4j_uri = "uri"
    kg.neo4j_user = "user"
    kg.neo4j_password = "pwd"
    return kg


def test_get_constraints_for_query_type():
    rows = [{"id": "1", "description": "desc", "type": "t", "pattern": None}]
    kg = _make_kg(rows)
    res = kg.get_constraints_for_query_type("explanation")
    assert res[0]["description"] == "desc"


def test_get_best_practices():
    rows = [{"id": "bp1", "text": "practice"}]
    kg = _make_kg(rows)
    res = kg.get_best_practices("summary")
    assert res[0]["text"] == "practice"


def test_get_examples():
    rows = [{"id": "ex1", "text": "example", "type": "positive"}]
    kg = _make_kg(rows)
    res = kg.get_examples(limit=1)
    assert res[0]["id"] == "ex1"


def test_find_relevant_rules_without_vector_store():
    kg = _make_kg([])
    assert kg.find_relevant_rules("q") == []
