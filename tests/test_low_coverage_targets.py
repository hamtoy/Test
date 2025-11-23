from __future__ import annotations

import sys
import types
from typing import Any
import tempfile
from pathlib import Path
import asyncio
import asyncio

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
from src import gemini_model_client as gmc
from src import agent as ag
from src import advanced_context_augmentation as aca


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


def test_gemini_model_client_errors(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key")

    class _FakeResponse:
        def __init__(self, text, usage=None, candidates=None):
            self.text = text
            self.usage_metadata = usage
            self.candidates = candidates

    class _FakeModel:
        def __init__(self):
            self.calls = []

        def generate_content(self, prompt, generation_config=None):
            self.calls.append(("gen", prompt))
            raise gmc.google_exceptions.GoogleAPIError("boom")

    fake_genai = types.SimpleNamespace(
        configure=lambda api_key: None,
        GenerativeModel=lambda name="m": _FakeModel(),
        types=types.SimpleNamespace(GenerationConfig=lambda **_: None),
    )
    monkeypatch.setattr(gmc, "genai", fake_genai)
    client = gmc.GeminiModelClient()

    # generate handles exceptions
    assert client.generate("hi").startswith("[생성 실패")

    # evaluate len-based fallback on parse failure
    client.generate = lambda prompt, role="evaluator": "not numbers"
    eval_res = client.evaluate("q", ["a", "bb", "ccc"])
    assert eval_res["best_index"] == 2

    # rewrite/fact_check exception paths
    client.generate = lambda prompt, role="rewriter": (_ for _ in ()).throw(
        gmc.google_exceptions.GoogleAPIError("rewriter error")
    )
    assert "재작성 실패" in client.rewrite("text")

    client.generate = lambda prompt, role="fact_checker": (_ for _ in ()).throw(
        ValueError("bad input")
    )
    fact_res = client.fact_check("ans", has_table_chart=True)
    assert fact_res["verdict"] == "error"


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


def test_agent_cache_budget_and_pricing(monkeypatch, tmp_path):
    # Minimal config stub
    class _Config:
        def __init__(self):
            self.max_concurrency = 1
            self.temperature = 0.1
            self.max_output_tokens = 16
            self.model_name = "tier-model"
            self.timeout = 1
            self.template_dir = tmp_path
            self.local_cache_dir = tmp_path / "cache"
            self.base_dir = tmp_path
            self.cache_ttl_minutes = 1
            self.budget_limit_usd = 1.0

    # pricing tiers stub
    monkeypatch.setattr(ag, "PRICING_TIERS", {"tier-model": [{"max_input_tokens": None, "input_rate": 1, "output_rate": 2}]})
    monkeypatch.setattr(ag, "DEFAULT_RPM_LIMIT", 10)
    monkeypatch.setattr(ag, "DEFAULT_RPM_WINDOW_SECONDS", 60)

    # templates required (empty content)
    for name in ["prompt_eval.j2", "prompt_query_gen.j2", "prompt_rewrite.j2", "query_gen_user.j2", "rewrite_user.j2"]:
        (tmp_path / name).write_text("{{ body }}", encoding="utf-8")

    agent = ag.GeminiAgent(_Config(), jinja_env=None)

    # cost calculations
    agent.total_input_tokens = 1_000_000
    agent.total_output_tokens = 1_000_000
    cost = agent.get_total_cost()
    assert cost == pytest.approx(3.0)
    assert agent.get_budget_usage_percent() == pytest.approx(300.0)

    # budget check raises
    with pytest.raises(ag.BudgetExceededError):
        agent.check_budget()


def test_agent_local_cache_load_and_store(monkeypatch, tmp_path):
    class _Config:
        def __init__(self):
            self.max_concurrency = 1
            self.temperature = 0.1
            self.max_output_tokens = 16
            self.model_name = "tier-model"
            self.timeout = 1
            self.template_dir = tmp_path
            self.local_cache_dir = tmp_path / "cache"
            self.base_dir = tmp_path
            self.cache_ttl_minutes = 1
            self.budget_limit_usd = None

    for name in ["prompt_eval.j2", "prompt_query_gen.j2", "prompt_rewrite.j2", "query_gen_user.j2", "rewrite_user.j2"]:
        (tmp_path / name).write_text("{{ body }}", encoding="utf-8")

    agent = ag.GeminiAgent(_Config(), jinja_env=None)
    fp = "abc"
    # Avoid calling CachedContent.get in _load_local_cache
    monkeypatch.setattr(ag.caching.CachedContent, "get", lambda name: types.SimpleNamespace(name=name))
    agent._store_local_cache(fp, "name1", ttl_minutes=1)
    cached = agent._load_local_cache(fp, ttl_minutes=1)
    # _load_local_cache returns None unless CachedContent.get is patched; just ensure manifest exists and no crash
    assert (tmp_path / "cache" / "context_cache.json").exists()
    assert cached is not None


def test_agent_get_total_cost_invalid_model(monkeypatch):
    class _Config:
        def __init__(self):
            self.model_name = "unknown-model"
            self.max_concurrency = 1
            self.temperature = 0.1
            self.max_output_tokens = 16
            self.timeout = 1
            self.template_dir = tmp_path
            self.local_cache_dir = tmp_path / "cache"
            self.base_dir = tmp_path
            self.cache_ttl_minutes = 1
            self.budget_limit_usd = None

    tmp_path = Path(tempfile.mkdtemp(prefix="agent_cost_invalid_"))
    for name in ["prompt_eval.j2", "prompt_query_gen.j2", "prompt_rewrite.j2", "query_gen_user.j2", "rewrite_user.j2"]:
        (tmp_path / name).write_text("{{ body }}", encoding="utf-8")

    agent = ag.GeminiAgent(_Config(), jinja_env=None)
    agent.total_input_tokens = 10
    agent.total_output_tokens = 10
    with pytest.raises(ValueError):
        agent.get_total_cost()


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

    sys.modules["scripts.build_session"] = types.SimpleNamespace(SessionContext=_SessionContext)
    monkeypatch.setattr(qrs, "validate_turns", lambda turns, ctx: {"ok": True})

    kg = qrs.QAKnowledgeGraph.__new__(qrs.QAKnowledgeGraph)

    # empty turns
    res = kg.validate_session({"turns": []})
    assert res["ok"] is False

    # TypeError path
    res2 = kg.validate_session({"turns": [{}], "context": {"fail": True}})
    assert res2["ok"] is False


@pytest.mark.asyncio
async def test_agent_execute_api_call_safety_error(monkeypatch, tmp_path):
    class _Config:
        def __init__(self):
            self.model_name = "tier-model"
            self.max_concurrency = 1
            self.temperature = 0.1
            self.max_output_tokens = 16
            self.timeout = 1
            self.template_dir = tmp_path
            self.local_cache_dir = tmp_path / "cache"
            self.base_dir = tmp_path
            self.cache_ttl_minutes = 1
            self.budget_limit_usd = None

    for name in ["prompt_eval.j2", "prompt_query_gen.j2", "prompt_rewrite.j2", "query_gen_user.j2", "rewrite_user.j2"]:
        (tmp_path / name).write_text("{{ body }}", encoding="utf-8")

    monkeypatch.setattr(ag, "DEFAULT_RPM_LIMIT", 1)
    monkeypatch.setattr(ag, "DEFAULT_RPM_WINDOW_SECONDS", 60)

    agent = ag.GeminiAgent(_Config(), jinja_env=None)
    agent._rate_limiter = None
    agent._semaphore = type(
        "Sem",
        (),
        {
            "__aenter__": lambda self: asyncio.sleep(0, result=None),
            "__aexit__": lambda self, exc_type, exc, tb: asyncio.sleep(0, result=None),
        },
    )()

    class _Resp:
        def __init__(self):
            self.candidates = [type("C", (), {"finish_reason": "BLOCK", "content": type("P", (), {"parts": []})})()]
            self.usage_metadata = None

    class _Model:
        async def generate_content_async(self, prompt_text, request_options=None):
            return _Resp()

    with pytest.raises(ag.SafetyFilterError):
        await agent._execute_api_call(_Model(), "prompt")


def test_gemini_model_client_type_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key")

    class _FakeModel:
        def generate_content(self, *args, **kwargs):
            raise TypeError("bad")

    fake_genai = types.SimpleNamespace(
        configure=lambda api_key: None,
        GenerativeModel=lambda name: _FakeModel(),
        types=types.SimpleNamespace(GenerationConfig=lambda **_: None),
    )
    monkeypatch.setattr(gmc, "genai", fake_genai)

    client = gmc.GeminiModelClient()
    assert "[생성 실패(입력 오류" in client.generate("prompt")


def test_qa_rag_vector_store_skips_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    kg = qrs.QAKnowledgeGraph.__new__(qrs.QAKnowledgeGraph)
    kg.neo4j_uri = "uri"
    kg.neo4j_user = "user"
    kg.neo4j_password = "pw"
    kg._graph = None
    kg._init_vector_store()
    assert getattr(kg, "_vector_store", None) is None


@pytest.mark.asyncio
async def test_agent_execute_api_call_safety_error(monkeypatch, tmp_path):
    class _Config:
        def __init__(self):
            self.model_name = "tier-model"
            self.max_concurrency = 1
            self.temperature = 0.1
            self.max_output_tokens = 16
            self.timeout = 1
            self.template_dir = tmp_path
            self.local_cache_dir = tmp_path / "cache"
            self.base_dir = tmp_path
            self.cache_ttl_minutes = 1
            self.budget_limit_usd = None

    for name in ["prompt_eval.j2", "prompt_query_gen.j2", "prompt_rewrite.j2", "query_gen_user.j2", "rewrite_user.j2"]:
        (tmp_path / name).write_text("{{ body }}", encoding="utf-8")

    monkeypatch.setattr(ag, "DEFAULT_RPM_LIMIT", 1)
    monkeypatch.setattr(ag, "DEFAULT_RPM_WINDOW_SECONDS", 60)

    agent = ag.GeminiAgent(_Config(), jinja_env=None)
    agent._rate_limiter = None
    agent._semaphore = type(
        "Sem",
        (),
        {
            "__aenter__": lambda self: asyncio.sleep(0),
            "__aexit__": lambda self, exc_type, exc, tb: asyncio.sleep(0),
        },
    )()

    class _Resp:
        def __init__(self):
            self.candidates = [type("C", (), {"finish_reason": "BLOCK", "content": type("P", (), {"parts": []})})()]
            self.usage_metadata = None

    class _Model:
        async def generate_content_async(self, prompt_text, request_options=None):
            return _Resp()

    with pytest.raises(ag.SafetyFilterError):
        await agent._execute_api_call(_Model(), "prompt")


def test_gemini_model_client_type_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "key")

    class _FakeModel:
        def generate_content(self, *args, **kwargs):
            raise TypeError("bad")

    fake_genai = types.SimpleNamespace(
        configure=lambda api_key: None,
        GenerativeModel=lambda name: _FakeModel(),
        types=types.SimpleNamespace(GenerationConfig=lambda **_: None),
    )
    monkeypatch.setattr(gmc, "genai", fake_genai)

    client = gmc.GeminiModelClient()
    assert "[생성 실패(입력 오류" in client.generate("prompt")


def test_advanced_context_augmentation_vector_index(monkeypatch):
    class _Doc:
        def __init__(self, text):
            self.page_content = text
            self.metadata = {"id": 1}

    class _Result:
        def data(self_inner):
            return [{"rule": "R", "priority": 1, "examples": ["ex1"]}]

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            return _Result()

    class _Driver:
        def session(self):
            return _Session()

    aug = aca.AdvancedContextAugmentation.__new__(aca.AdvancedContextAugmentation)
    aug.vector_index = types.SimpleNamespace(similarity_search=lambda q, k=5: [_Doc("doc")])
    aug.graph = types.SimpleNamespace(_driver=_Driver())

    out = aug.augment_prompt_with_similar_cases("q", "explanation")
    assert out["similar_cases"] == ["doc"]
    assert out["relevant_rules"]


def test_advanced_context_augmentation_fallback_graph():
    record = {"blocks": [{"content": "b"}], "rules": [{"rule": "r", "priority": 1, "examples": ["e"]}]}

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            class _Res:
                def single(self_inner):
                    return record

            return _Res()

    aug = aca.AdvancedContextAugmentation.__new__(aca.AdvancedContextAugmentation)
    aug.vector_index = None
    aug.graph = types.SimpleNamespace(_driver=types.SimpleNamespace(session=lambda: _Session()))

    out = aug.augment_prompt_with_similar_cases("q", "explanation")
    assert out["similar_cases"]
    assert out["relevant_rules"]


def test_generate_with_augmentation_formats(monkeypatch):
    aug = aca.AdvancedContextAugmentation.__new__(aca.AdvancedContextAugmentation)
    monkeypatch.setattr(
        aug,
        "augment_prompt_with_similar_cases",
        lambda uq, qt: {
            "similar_cases": ["case"],
            "relevant_rules": [{"rule": "R", "priority": 1, "examples": ["ex"]}],
            "query_type": qt,
        },
    )
    prompt = aug.generate_with_augmentation("u", "explanation", {"ctx": 1})
    assert "Similar Successful Cases" in prompt
