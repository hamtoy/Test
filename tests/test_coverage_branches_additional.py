from __future__ import annotations

import builtins
import datetime
import types
from pathlib import Path
import json
import sys

import pytest
from jinja2 import DictLoader, Environment
from neo4j.exceptions import Neo4jError

from src import cross_validation
from src import dynamic_template_generator as dtg
from src import qa_rag_system
from src import semantic_analysis
from src.agent import GeminiAgent
from src.config import AppConfig

VALID_API_KEY = "AIza" + "A" * 35


# ----------------------------
# Dynamic template generator
# ----------------------------


def test_dynamic_template_require_env_missing(monkeypatch):
    monkeypatch.delenv("NEO4J_URI", raising=False)
    with pytest.raises(EnvironmentError):
        dtg.require_env("NEO4J_URI")


# ----------------------------
# Cross validation branches
# ----------------------------


def test_cross_validation_image_grounding_branches(monkeypatch):
    class _ErrorSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            raise Neo4jError("boom")

    class _EmptySession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            return types.SimpleNamespace(single=lambda: {"all_content": []})

    class _ShortTokenSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            return types.SimpleNamespace(single=lambda: {"all_content": ["aa"]})

    class _KG:
        def __init__(self, session):
            self._graph = types.SimpleNamespace(session=lambda: session)
            self._vector_store = None

        def get_constraints_for_query_type(self, _qt):
            return []

    cvs = cross_validation.CrossValidationSystem(_KG(_ErrorSession()))
    err_note = cvs._check_image_grounding("answer", {"page_id": "p"})
    assert err_note["note"] == "Neo4j 조회 실패"

    cvs = cross_validation.CrossValidationSystem(_KG(_EmptySession()))
    empty_note = cvs._check_image_grounding("answer", {"page_id": "p"})
    assert empty_note["note"] == "본문 콘텐츠 없음"

    cvs = cross_validation.CrossValidationSystem(_KG(_ShortTokenSession()))
    short_note = cvs._check_image_grounding("answer", {"page_id": "p"})
    assert short_note["note"] == "본문 키워드 부족"

    no_page = cvs._check_image_grounding("answer", {})  # page_id 없음 분기
    assert no_page["note"] == "page_id 없음"


def test_cross_validation_rule_and_novelty_exceptions(monkeypatch):
    class _BadSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            raise Neo4jError("patterns failed")

    class _KG:
        def __init__(self):
            self._graph = types.SimpleNamespace(session=lambda: _BadSession())
            self._vector_store = types.SimpleNamespace(
                similarity_search=lambda *_a, **_k: (_ for _ in ()).throw(
                    RuntimeError("vec fail")
                )
            )

        def get_constraints_for_query_type(self, _qt):
            return [{"type": "prohibition", "pattern": "bad", "description": "desc"}]

    cvs = cross_validation.CrossValidationSystem(_KG())
    compliance = cvs._check_rule_compliance("bad text", "summary")
    assert compliance["violations"]  # 금지 패턴 적발

    novelty = cvs._check_novelty("question")
    assert novelty["note"] == "유사도 조회 실패"


# ----------------------------
# QA RAG system branches
# ----------------------------


def test_qa_rag_init_uses_env_and_driver(monkeypatch, tmp_path):
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "pass")
    monkeypatch.setenv("GEMINI_API_KEY", VALID_API_KEY)
    called = {}

    class _Driver:
        def __init__(self, uri, auth):
            called["uri"] = uri
            called["auth"] = auth

        def close(self):
            return None

    class _GraphDB:
        @staticmethod
        def driver(uri, auth):
            return _Driver(uri, auth)

    monkeypatch.setattr(qa_rag_system, "GraphDatabase", _GraphDB)
    monkeypatch.setattr(
        qa_rag_system.QAKnowledgeGraph, "_init_vector_store", lambda self: None
    )

    kg = qa_rag_system.QAKnowledgeGraph()
    assert called["uri"] == "bolt://localhost"
    assert called["auth"][0] == "neo4j"
    kg.close()


def test_qa_rag_init_vector_store_error_paths(monkeypatch):
    # Ensure langchain_neo4j import succeeds with a stub
    class _Neo4jVector:
        @staticmethod
        def from_existing_graph(*_args, **_kwargs):
            raise Neo4jError("vector fail")

    neo4j_vector_module = types.ModuleType("langchain_neo4j")
    neo4j_vector_module.Neo4jVector = _Neo4jVector
    monkeypatch.setitem(sys.modules, "langchain_neo4j", neo4j_vector_module)
    monkeypatch.setenv("GEMINI_API_KEY", VALID_API_KEY)

    kg = object.__new__(qa_rag_system.QAKnowledgeGraph)
    kg.neo4j_uri = "uri"
    kg.neo4j_user = "user"
    kg.neo4j_password = "pwd"
    kg._vector_store = "sentinel"

    # Neo4jError branch
    kg._init_vector_store()
    assert kg._vector_store is None

    # GEMINI_API_KEY 누락 branch (returns early)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    kg._vector_store = "keep"
    kg._init_vector_store()
    assert kg._vector_store == "keep"


def test_qa_rag_validate_session_failure(monkeypatch):
    kg = object.__new__(qa_rag_system.QAKnowledgeGraph)

    class _BadContext(Exception):
        pass

    def _bad_ctx(**_kwargs):
        raise ValueError("bad ctx")

    fake_mod = types.ModuleType("scripts.build_session")
    fake_mod.SessionContext = _bad_ctx
    monkeypatch.setitem(sys.modules, "scripts.build_session", fake_mod)
    result = kg.validate_session(
        {"turns": [{"type": "explanation"}], "context": {"foo": "bar"}}
    )
    assert result["issues"]


# ----------------------------
# Semantic analysis
# ----------------------------


def test_semantic_analysis_require_env(monkeypatch):
    monkeypatch.delenv("NEO4J_URI", raising=False)
    with pytest.raises(EnvironmentError):
        semantic_analysis.require_env("NEO4J_URI")


# ----------------------------
# Agent branches
# ----------------------------


def _minimal_jinja_env():
    return Environment(
        loader=DictLoader(
            {
                "prompt_eval.j2": "",
                "prompt_rewrite.j2": "",
                "rewrite_user.j2": "",
            }
        )
    )


def _make_config(tmp_path: Path):
    monkeypatch_env = {
        "GEMINI_API_KEY": VALID_API_KEY,
        "PROJECT_ROOT": str(tmp_path),
        "LOCAL_CACHE_DIR": str(tmp_path / ".cache"),
    }
    return monkeypatch_env


def test_agent_init_without_aiolimiter(monkeypatch, tmp_path):
    envs = _make_config(tmp_path)
    for k, v in envs.items():
        monkeypatch.setenv(k, v)

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "aiolimiter":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    agent = GeminiAgent(AppConfig(), jinja_env=_minimal_jinja_env())
    assert agent._rate_limiter is None


def test_agent_cleanup_expired_cache(monkeypatch, tmp_path):
    envs = _make_config(tmp_path)
    for k, v in envs.items():
        monkeypatch.setenv(k, v)

    agent = GeminiAgent(AppConfig(), jinja_env=_minimal_jinja_env())
    manifest = agent._local_cache_manifest_path()
    manifest.parent.mkdir(parents=True, exist_ok=True)

    expired_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        minutes=15
    )
    future_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=5
    )
    manifest.write_text(
        json.dumps(
            {
                "old": {"created": expired_time.isoformat(), "ttl_minutes": 10},
                "keep": {"created": future_time.isoformat(), "ttl_minutes": 20},
            }
        ),
        encoding="utf-8",
    )

    agent._cleanup_expired_cache(ttl_minutes=10)
    data = manifest.read_text(encoding="utf-8")
    assert "old" not in data and "keep" in data


@pytest.mark.asyncio
async def test_agent_create_context_cache_skips_when_small(monkeypatch, tmp_path):
    envs = _make_config(tmp_path)
    for k, v in envs.items():
        monkeypatch.setenv(k, v)

    agent = GeminiAgent(AppConfig(), jinja_env=_minimal_jinja_env())

    class _Model:
        @staticmethod
        def count_tokens(_text):
            return types.SimpleNamespace(total_tokens=1)

    stub_genai = types.SimpleNamespace(GenerativeModel=lambda *_a, **_k: _Model())
    monkeypatch.setattr(GeminiAgent, "_genai", property(lambda _self: stub_genai))
    stub_caching = types.SimpleNamespace()
    monkeypatch.setattr(GeminiAgent, "_caching", property(lambda _self: stub_caching))

    result = await agent.create_context_cache("tiny text")
    assert result is None


def test_agent_create_model_with_cached_content(monkeypatch, tmp_path):
    envs = _make_config(tmp_path)
    for k, v in envs.items():
        monkeypatch.setenv(k, v)

    agent = GeminiAgent(AppConfig(), jinja_env=_minimal_jinja_env())
    sentinel = object()

    class _GenModel:
        @staticmethod
        def from_cached_content(*_args, **_kwargs):
            return sentinel

    stub_genai = types.SimpleNamespace(GenerativeModel=_GenModel)
    monkeypatch.setattr(GeminiAgent, "_genai", property(lambda _self: stub_genai))
    model = agent._create_generative_model("sys", cached_content=sentinel)
    assert model is sentinel
