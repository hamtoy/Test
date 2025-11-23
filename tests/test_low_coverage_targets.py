from __future__ import annotations

import sys
import types
from typing import Any

# Stub external deps before importing targets
_pil = types.ModuleType("PIL")
_pil_image = types.ModuleType("PIL.Image")
_pil_image.Image = object  # placeholder
sys.modules["PIL"] = _pil
sys.modules["PIL.Image"] = _pil_image

_pytesseract = types.ModuleType("pytesseract")
_pytesseract.image_to_string = lambda *a, **k: ""
sys.modules["pytesseract"] = _pytesseract

import pytest

from src import compare_documents
from src import multimodal_understanding as mmu
from src import qa_rag_system as qrs
from src import self_correcting_chain
from src import ultimate_langchain_qa_system as ulqa


def test_self_correcting_chain_stops_on_yes(monkeypatch):
    class _KG:
        def get_constraints_for_query_type(self, _qt):
            return [{"description": "rule-1"}]

    class _LLM:
        def __init__(self):
            self.calls = []

        def generate(self, prompt, role="default"):
            self.calls.append(role)
            if role == "validator":
                return "yes, all good"
            return f"{role}-out"

    chain = self_correcting_chain.SelfCorrectingQAChain(_KG(), _LLM())
    result = chain.generate_with_self_correction("explanation", {"ctx": 1})

    assert result["iterations"] == 1
    assert result["output"] == "correct-out"
    assert result["validation"]


def test_multimodal_understanding_uses_fakes(monkeypatch):
    fake_saved = {}

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, _query, **params):
            fake_saved.update(params)

    class _FakeGraph:
        def session(self):
            return _FakeSession()

    class _KG:
        def __init__(self):
            self._graph = _FakeGraph()

    class _FakeImg:
        width = 10
        height = 20

    monkeypatch.setattr(mmu, "Image", types.SimpleNamespace(open=lambda path: _FakeImg()))
    monkeypatch.setattr(mmu, "pytesseract", types.SimpleNamespace(image_to_string=lambda img, lang=None: "alpha beta beta"))

    analyzer = mmu.MultimodalUnderstanding(_KG())
    meta = analyzer.analyze_image_deep("fake.png")

    assert meta["has_table_chart"] is False
    assert sorted(meta["topics"]) == ["alpha", "beta"]
    assert fake_saved.get("path") == "fake.png"


def test_compare_documents_main_flow(monkeypatch, capsys):
    monkeypatch.setenv("NEO4J_URI", "bolt://fake")
    monkeypatch.setenv("NEO4J_USER", "user")
    monkeypatch.setenv("NEO4J_PASSWORD", "pass")

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, query, **kwargs):
            if "collect(DISTINCT b.type)" in query:
                return [
                    {"title": "Page A", "total_blocks": 2, "types": ["heading", "paragraph"]},
                    {"title": "Page B", "total_blocks": 1, "types": ["paragraph"]},
                ]
            return [{"content": "content text long enough", "pages": ["Page A", "Page B"]}]

    class _Driver:
        def session(self):
            return _Session()

        def close(self):
            return None

    monkeypatch.setattr(compare_documents, "GraphDatabase", types.SimpleNamespace(driver=lambda uri, auth: _Driver()))
    compare_documents.main()
    out = capsys.readouterr().out
    assert "Page A" in out
    assert "공통으로 등장하는 내용" in out


def test_qa_rag_system_embeddings_and_rules(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(qrs.genai, "configure", lambda api_key: calls.append("config"))
    monkeypatch.setattr(qrs.genai, "embed_content", lambda **kwargs: {"embedding": [1.0, 2.0]})

    emb = qrs.CustomGeminiEmbeddings(api_key="k")
    assert emb.embed_query("hi") == [1.0, 2.0]
    assert emb.embed_documents(["a", "b"]) == [[1.0, 2.0], [1.0, 2.0]]

    kg = qrs.QAKnowledgeGraph.__new__(qrs.QAKnowledgeGraph)
    kg._vector_store = types.SimpleNamespace(similarity_search=lambda query, k=5: [types.SimpleNamespace(page_content="rule")])
    result = kg.find_relevant_rules("q", k=1)
    assert result == ["rule"]


def test_ultimate_langchain_qa_system_wires_dependencies(monkeypatch):
    class _KG:
        def __init__(self):
            self._graph = types.SimpleNamespace(session=lambda: None)

    class _Memory:
        def __init__(self, *args, **kwargs):
            self.logged = []

        def _log_interaction(self, q, a):
            self.logged.append((q, a))

    class _Agent:
        def __init__(self, kg):
            self.kg = kg

        def collaborative_generate(self, qt, ctx):
            return {"metadata": {"m": 1}, "output": "agent"}

    class _Correct:
        def __init__(self, kg, llm=None):
            self.kg = kg

        def generate_with_self_correction(self, qt, meta):
            return {"output": "corrected", "iterations": 1, "validation": "ok"}

    class _Router:
        def __init__(self, kg, llm=None):
            self.kg = kg

        def route_and_generate(self, user_input, handlers):
            return {"choice": "explanation"}

    class _LCEL:
        def __init__(self, kg, llm=None):
            self.kg = kg

    monkeypatch.setattr(ulqa, "QAKnowledgeGraph", _KG)
    monkeypatch.setattr(ulqa, "MemoryAugmentedQASystem", _Memory)
    monkeypatch.setattr(ulqa, "MultiAgentQASystem", _Agent)
    monkeypatch.setattr(ulqa, "SelfCorrectingQAChain", _Correct)
    monkeypatch.setattr(ulqa, "GraphEnhancedRouter", _Router)
    monkeypatch.setattr(ulqa, "LCELOptimizedChain", _LCEL)
    monkeypatch.setattr(ulqa, "GeminiModelClient", lambda: None)

    system = ulqa.UltimateLangChainQASystem()
    out = system.generate_ultimate_qa("img.png", user_query="hi")

    assert out["output"] == "corrected"
    assert out["metadata"]["iterations"] == 1
