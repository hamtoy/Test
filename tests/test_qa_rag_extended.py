from __future__ import annotations

import types
import sys
from src.qa import rag_system as qrs


def test_qa_rag_system_embeddings_and_rules(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(qrs.genai, "configure", lambda api_key: calls.append("config"))
    monkeypatch.setattr(
        qrs.genai, "embed_content", lambda **kwargs: {"embedding": [1.0, 2.0]}
    )

    emb = qrs.CustomGeminiEmbeddings(api_key="k")
    assert emb.embed_query("hi") == [1.0, 2.0]
    assert emb.embed_documents(["a", "b"]) == [[1.0, 2.0], [1.0, 2.0]]

    kg = qrs.QAKnowledgeGraph.__new__(qrs.QAKnowledgeGraph)
    kg._vector_store = types.SimpleNamespace(
        similarity_search=lambda query, k=5: [
            types.SimpleNamespace(page_content="rule")
        ]
    )
    result = kg.find_relevant_rules("q", k=1)
    assert result == ["rule"]


def test_qa_rag_vector_store_init(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")

    class _FakeNeo4jVector:
        @classmethod
        def from_existing_graph(cls, *args, **kwargs):
            return "vector"

    # stub import module
    sys.modules["langchain_neo4j"] = types.SimpleNamespace(Neo4jVector=_FakeNeo4jVector)

    kg = qrs.QAKnowledgeGraph.__new__(qrs.QAKnowledgeGraph)
    kg.neo4j_uri = "uri"
    kg.neo4j_user = "user"
    kg.neo4j_password = "pw"
    kg._graph = None
    kg._init_vector_store()
    assert kg._vector_store == "vector"


def test_qa_rag_vector_store_handles_errors(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")

    class _FakeNeo4jVector:
        @classmethod
        def from_existing_graph(cls, *args, **kwargs):
            raise ValueError("bad config")

    sys.modules["langchain_neo4j"] = types.SimpleNamespace(Neo4jVector=_FakeNeo4jVector)

    kg = qrs.QAKnowledgeGraph.__new__(qrs.QAKnowledgeGraph)
    kg.neo4j_uri = "uri"
    kg.neo4j_user = "user"
    kg.neo4j_password = "pw"
    kg._graph = None
    kg._init_vector_store()
    assert kg._vector_store is None


def test_qa_rag_find_relevant_rules(monkeypatch):
    kg = qrs.QAKnowledgeGraph.__new__(qrs.QAKnowledgeGraph)
    kg._vector_store = None
    assert kg.find_relevant_rules("q") == []

    class _Doc:
        def __init__(self, text):
            self.page_content = text

    kg._vector_store = types.SimpleNamespace(
        similarity_search=lambda query, k=5: [_Doc("r1")]
    )
    assert kg.find_relevant_rules("q", k=1) == ["r1"]


def test_qa_rag_validate_session(monkeypatch):
    class _SessionContext:
        def __init__(self, **kwargs):
            if kwargs.get("fail"):
                raise TypeError("boom")

    sys.modules["scripts.build_session"] = types.SimpleNamespace(
        SessionContext=_SessionContext
    )
    monkeypatch.setattr(qrs, "validate_turns", lambda turns, ctx: {"ok": True})

    kg = qrs.QAKnowledgeGraph.__new__(qrs.QAKnowledgeGraph)

    # empty turns
    res = kg.validate_session({"turns": []})
    assert res["ok"] is False

    # TypeError path
    res2 = kg.validate_session({"turns": [{}], "context": {"fail": True}})
    assert res2["ok"] is False


def test_qa_rag_vector_store_skips_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    kg = qrs.QAKnowledgeGraph.__new__(qrs.QAKnowledgeGraph)
    kg.neo4j_uri = "uri"
    kg.neo4j_user = "user"
    kg.neo4j_password = "pw"
    kg._graph = None
    kg._init_vector_store()
    assert getattr(kg, "_vector_store", None) is None
