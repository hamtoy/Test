from __future__ import annotations

# ruff: noqa: E402

import sys
import types
from typing import Any, cast

import pytest
from jinja2 import DictLoader, Environment

# Minimal langchain stubs for modules that are not installed in CI.
lc_base_module = sys.modules.setdefault(
    "langchain.callbacks.base", types.ModuleType("langchain.callbacks.base")
)
cast(Any, lc_base_module).BaseCallbackHandler = type("BaseCallbackHandler", (), {})

callbacks_module = sys.modules.setdefault(
    "langchain.callbacks", types.ModuleType("langchain.callbacks")
)
cast(Any, callbacks_module).base = lc_base_module

langchain_module = sys.modules.setdefault("langchain", types.ModuleType("langchain"))
cast(Any, langchain_module).callbacks = callbacks_module

from src import caching_layer
from src import compare_documents
from src import dynamic_template_generator as dtg
from src import gemini_model_client as gmc
from src import integrated_qa_pipeline as iqap
from src import real_time_constraint_enforcer as rtce
from src import advanced_context_augmentation as aca
from src import graph_schema_builder as gsb
from src import health_check
from src import cross_validation
from src import graph_enhanced_router
from src import custom_callback
from src import lcel_optimized_chain
from src import memory_augmented_qa
from src import multi_agent_qa_system
from src import semantic_analysis
from src import smart_autocomplete
from src import dynamic_example_selector
from src import adaptive_difficulty


class _QueueSession:
    """Session stub that pops pre-baked responses per run call."""

    def __init__(self, responses):
        self._responses = list(responses)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, *_args, **_kwargs):
        if self._responses:
            result = self._responses.pop(0)
            return result if isinstance(result, list) else [result]
        return []


class _QueueDriver:
    """Driver stub that yields a queue-backed session."""

    def __init__(self, responses):
        self._responses = list(responses)

    def session(self):
        return _QueueSession(self._responses)

    def close(self):
        return None


def test_dynamic_template_generator_fallback_and_checklist(monkeypatch):
    driver = _QueueDriver(
        [
            [
                {
                    "type_name": "설명",
                    "rules": ["r1"],
                    "constraints": ["c1"],
                    "best_practices": ["bp1"],
                    "examples": [{"text": "ex1", "type": "positive"}],
                }
            ],
            [{"item": "규칙을 따를 것", "category": "rule"}],
        ]
    )

    class _GraphDB:
        @staticmethod
        def driver(*_args, **_kwargs):
            return driver

    monkeypatch.setattr(dtg, "GraphDatabase", _GraphDB)

    env = Environment(
        loader=DictLoader(
            {"templates/base_system.j2": "{{query_type_korean}}|{{rules|length}}"}
        )
    )
    generator = dtg.DynamicTemplateGenerator("uri", "user", "pw")
    generator.jinja_env = env  # use in-memory template to trigger fallback

    prompt = generator.generate_prompt_for_query_type(
        "explanation", {"calc_allowed": False}
    )
    assert "설명" in prompt
    generator._run = lambda _cypher, _params=None: [  # noqa: SLF001
        {"item": "규칙을 따를 것", "category": "rule"}
    ]
    checklist = generator.generate_validation_checklist(
        {"turns": [{"type": "explanation"}]}
    )
    assert checklist == [
        {"item": "규칙을 따를 것", "category": "rule", "query_type": "explanation"}
    ]
    generator.close()


def test_caching_layer_prefers_cache_and_invalidates(monkeypatch):
    class _FakeSession:
        def __init__(self):
            self.calls = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            self.calls += 1
            return [{"id": "r1", "text": "T", "section": "S"}]

    class _FakeGraph:
        def __init__(self):
            self.session_obj = _FakeSession()

        def session(self):
            return self.session_obj

    kg = types.SimpleNamespace(_graph=_FakeGraph())

    class _FakeRedis:
        def __init__(self):
            self.store = {}

        def get(self, key):
            return self.store.get(key)

        def setex(self, key, ttl, value):
            self.store[key] = value

        def keys(self, pattern):
            return list(self.store.keys())

        def delete(self, *keys):
            removed = 0
            for k in keys:
                if k in self.store:
                    removed += 1
                    self.store.pop(k, None)
            return removed

    monkeypatch.setattr(caching_layer, "redis", object())
    fake_redis = _FakeRedis()
    layer = caching_layer.CachingLayer(kg, redis_client=fake_redis)

    first = layer.get_rules_cached("summary")
    second = layer.get_rules_cached("summary")
    assert first == second == [{"id": "r1", "text": "T", "section": "S"}]
    assert kg._graph.session_obj.calls == 1  # cache hit skips graph
    assert layer.invalidate_cache() == 1


def test_compare_documents_helpers(monkeypatch):
    monkeypatch.delenv("MISSING_ENV", raising=False)
    with pytest.raises(EnvironmentError):
        compare_documents.require_env("MISSING_ENV")

    class _CompareSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, query, **_kwargs):
            if "ORDER BY total_blocks" in query:
                return [
                    {
                        "title": "Doc A",
                        "total_blocks": 2,
                        "types": ["heading", "paragraph"],
                    },
                    {"title": "Doc B", "total_blocks": 1, "types": ["paragraph"]},
                ]
            return [{"content": "공통 내용", "pages": ["Doc A", "Doc B"]}]

    driver = types.SimpleNamespace(session=lambda: _CompareSession())
    structures = compare_documents.compare_structure(driver)
    commons = compare_documents.find_common_content(driver, limit=1)
    assert structures[0]["title"] == "Doc A"
    assert commons[0][1] == ["Doc A", "Doc B"]


def test_integrated_qa_pipeline_create_and_validate(monkeypatch):
    monkeypatch.setenv("NEO4J_URI", "bolt://fake")
    monkeypatch.setenv("NEO4J_USER", "u")
    monkeypatch.setenv("NEO4J_PASSWORD", "p")

    class _FakeKG:
        def __init__(self, *_args, **_kwargs):
            self.closed = False

        def close(self):
            self.closed = True

    class _TemplateSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, cypher, **_kwargs):
            if "ErrorPattern" in cypher:
                return [{"pattern": "forbidden", "desc": "error"}]
            if "Rule" in cypher:
                return [{"text": "RULE_SNIPPET"}]
            return []

    class _FakeTemplateGen:
        def __init__(self, *_args, **_kwargs):
            self.driver = types.SimpleNamespace(session=lambda: _TemplateSession())

        def generate_prompt_for_query_type(self, query_type, _ctx):
            return f"prompt-{query_type}"

        def close(self):
            return None

    def _fake_build_session(_ctx, validate=True):
        return [
            types.SimpleNamespace(type="explanation", prompt="p1"),
            types.SimpleNamespace(type="target", prompt="p2"),
        ]

    def _fake_find_violations(text):
        if "forbidden" in text:
            return [{"type": "forbidden_pattern", "match": "forbidden"}]
        return []

    monkeypatch.setattr(iqap, "QAKnowledgeGraph", _FakeKG)
    monkeypatch.setattr(iqap, "DynamicTemplateGenerator", _FakeTemplateGen)
    monkeypatch.setattr(iqap, "build_session", _fake_build_session)
    monkeypatch.setattr(iqap, "find_violations", _fake_find_violations)
    monkeypatch.setattr(iqap, "validate_turns", lambda *_args, **_kwargs: {"ok": True})

    pipeline = iqap.IntegratedQAPipeline()
    session = pipeline.create_session({"text_density": 0.8, "has_table_chart": False})
    assert session["turns"][0]["prompt"] == "prompt-explanation"

    validation = pipeline.validate_output("explanation", "forbidden text")
    assert validation["violations"]  # includes forbidden_pattern + error pattern
    assert validation["missing_rules_hint"]
    pipeline.close()


def test_real_time_constraint_enforcer_stream_and_validate():
    class _GraphSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            return [{"content": "duplicate text"}]

    class _FakeKG:
        def __init__(self):
            self._graph = types.SimpleNamespace(session=lambda: _GraphSession())

        def get_constraints_for_query_type(self, *_args, **_kwargs):
            return [
                {"type": "prohibition", "pattern": "bad", "description": "no bad words"}
            ]

    enforcer = rtce.RealTimeConstraintEnforcer(_FakeKG())

    chunks = list(
        enforcer.stream_with_validation(iter(["bad content", " more"]), "target")
    )
    assert chunks[0]["type"] == "violation"

    result = enforcer.validate_complete_output(
        "duplicate text 2023 - 2024", "explanation"
    )
    assert result["issues"]  # missing bold + similarity check


def test_gemini_model_client_behaviors(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    class _FakeGenConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class _FakeModel:
        def __init__(self, _name):
            pass

        def generate_content(self, prompt, generation_config=None):
            return types.SimpleNamespace(text=f"LLM:{prompt[:10]}")

    fake_genai = types.SimpleNamespace(
        configure=lambda api_key: None,
        GenerativeModel=lambda name: _FakeModel(name),
        types=types.SimpleNamespace(GenerationConfig=_FakeGenConfig),
    )
    monkeypatch.setattr(gmc, "genai", fake_genai)

    client = gmc.GeminiModelClient()
    assert client.generate("hello").startswith("LLM:")

    empty_eval = client.evaluate("q", [])
    assert empty_eval["best_answer"] is None

    length_eval = client.evaluate("q", ["a", "bb"])
    assert length_eval["best_index"] == 1

    client.generate = (
        lambda prompt, role="default": "점수1: 2\n점수2: 4\n점수3: 1\n최고: 2"
    )
    parsed_eval = client.evaluate("q", ["a", "bb", "ccc"])
    assert parsed_eval["best_index"] == 1

    client.generate = lambda prompt, role="rewriter": "rewritten text"
    assert client.rewrite("orig").startswith("rewritten")

    # client.generate = lambda prompt, role="fact_checker": "PASS\n문제점: 없음"
    # fact = client.fact_check("answer", has_table_chart=False)
    # assert fact["verdict"] == "pass"


def test_advanced_context_augmentation_fallback(monkeypatch):
    record = {
        "blocks": [{"content": "block text"}],
        "rules": [{"rule": "R", "priority": 1, "examples": ["ex"]}],
    }

    class _ACASession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            class _Result:
                def single(self_inner):
                    return record

            return _Result()

    fake_graph = types.SimpleNamespace(
        _driver=types.SimpleNamespace(session=lambda: _ACASession())
    )
    aug = aca.AdvancedContextAugmentation.__new__(aca.AdvancedContextAugmentation)
    aug.vector_index = None
    aug.graph = fake_graph

    augmented = aug.augment_prompt_with_similar_cases("질문", "explanation")
    assert augmented["similar_cases"]
    prompt = aug.generate_with_augmentation("질문", "explanation", {"ctx": "v"})
    assert "질문" in prompt


def test_graph_schema_builder_runs_with_stubbed_driver(monkeypatch):
    class _Result(list):
        def data(self):
            return list(self)

        def single(self):
            return self[0] if self else {"links": 0}

    class _BuilderSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, query, **_kwargs):
            if "heading_1" in query and "자주 틀리는" in query:
                return _Result([{"page_id": "p1", "start_order": 0, "section": "S"}])
            if "WHERE b.order >" in query:
                return _Result(
                    [
                        {
                            "id": "b1",
                            "content": "This is a useful rule text",
                            "type": "paragraph",
                        },
                        {"id": "b2", "content": "Stop", "type": "heading_1"},
                    ]
                )
            if "MATCH (b:Block {id:" in query:
                return _Result([{"content": "Child rule text is long enough"}])
            if "RETURN DISTINCT b.content AS text" in query:
                return _Result([{"text": "⭕ 좋은 예시 텍스트", "type": "positive"}])
            if "RETURN count(" in query:
                return _Result([{"links": 2}])
            return _Result([{}])

    class _BuilderDriver:
        def __init__(self):
            self.session_obj = _BuilderSession()

        def session(self):
            return self.session_obj

        def close(self):
            return None

    class _GraphDB:
        @staticmethod
        def driver(*_args, **_kwargs):
            return _BuilderDriver()

    monkeypatch.setattr(gsb, "GraphDatabase", _GraphDB)

    builder = gsb.QAGraphBuilder("uri", "user", "pw")
    builder.create_schema_constraints()
    builder.extract_rules_from_notion()
    builder.extract_query_types()
    builder.extract_constraints()
    builder.create_templates()
    builder.link_rules_to_constraints()
    builder.link_rules_to_query_types()
    builder.extract_examples()
    builder.link_examples_to_rules()
    builder.create_error_patterns()
    builder.create_best_practices()
    builder.close()


def test_health_check_with_stub(monkeypatch):
    class _HealthSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            return types.SimpleNamespace(single=lambda: 1)

    fake_kg = types.SimpleNamespace(
        _graph=types.SimpleNamespace(session=lambda: _HealthSession())
    )
    assert health_check.check_neo4j_connection(fake_kg) is True

    monkeypatch.setattr(health_check, "check_neo4j_connection", lambda *_a, **_k: True)
    report = health_check.health_check()
    assert report["status"] == "healthy"


def test_cross_validation_scoring(monkeypatch):
    class _CVSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, query, **_kwargs):
            if "collect(b.content)" in query:
                return types.SimpleNamespace(
                    single=lambda: {"all_content": ["Alpha beta content"]}
                )
            if "ErrorPattern" in query:
                return [
                    {"pattern": "error", "description": "error desc"},
                ]
            return []

    class _FakeKG:
        def __init__(self):
            self._graph = types.SimpleNamespace(session=lambda: _CVSession())
            self._vector_store = None

        def get_constraints_for_query_type(self, _qt):
            return [
                {"type": "prohibition", "pattern": "forbidden", "description": "nope"}
            ]

    cvs = cross_validation.CrossValidationSystem(_FakeKG())
    result = cvs.cross_validate_qa_pair(
        "What is alpha?",
        "forbidden error response with alpha token",
        "explanation",
        {"page_id": "p1"},
    )
    assert 0 <= result["overall_score"] <= 1
    assert result["rule_compliance"]["violations"]


def test_graph_enhanced_router(monkeypatch):
    class _RouterSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            return [
                {"name": "summary", "korean": "요약", "limit": 1},
                {"name": "explanation", "korean": "설명", "limit": 2},
            ]

    class _FakeKG:
        def __init__(self):
            self._graph = types.SimpleNamespace(session=lambda: _RouterSession())

    class _FakeLLM:
        def generate(self, prompt, role="router"):
            return "summary"

    chosen = {}

    def _handler(user_input):
        chosen["value"] = user_input
        return "ok"

    router = graph_enhanced_router.GraphEnhancedRouter(_FakeKG(), _FakeLLM())
    result = router.route_and_generate("hello", {"summary": _handler})
    assert result["choice"] == "summary"
    assert result["output"] == "ok"
    prompt_text = router._build_router_prompt(
        "hello", [{"name": "summary", "korean": "요약", "limit": 1}]
    )
    assert "요약" in prompt_text


def test_custom_callback_logs(monkeypatch):
    monkeypatch.setenv("NEO4J_URI", "bolt://fake")
    monkeypatch.setenv("NEO4J_USER", "u")
    monkeypatch.setenv("NEO4J_PASSWORD", "p")

    class _CBSession:
        def __init__(self, store):
            self.store = store

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, query, **params):
            self.store.append((query, params))

    class _CBDriver:
        def __init__(self, store):
            self.store = store

        def session(self):
            return _CBSession(self.store)

        def close(self):
            return None

    store: list = []

    class _GraphDB:
        @staticmethod
        def driver(*_args, **_kwargs):
            return _CBDriver(store)

    monkeypatch.setattr(custom_callback, "GraphDatabase", _GraphDB)
    cb = custom_callback.Neo4jLoggingCallback()
    cb.on_llm_start({}, ["prompt"])
    cb.on_llm_end("response")
    cb.on_chain_error(Exception("boom"))
    assert len(store) == 3
    cb.close()


def test_lcel_optimized_chain(monkeypatch):
    class _LCELSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            return [{"text": "rule text"}]

    class _FakeKG:
        def __init__(self):
            self._graph = types.SimpleNamespace(session=lambda: _LCELSession())

        def get_examples(self, limit=3):
            return [{"text": f"ex{idx}"} for idx in range(limit)]

        def get_constraints_for_query_type(self, qt):
            return [{"description": f"constraint for {qt}"}]

    class _FakeLLM:
        def generate(self, prompt, role="lcel"):
            return f"generated:{role}"

    chain = lcel_optimized_chain.LCELOptimizedChain(_FakeKG(), _FakeLLM())
    merged = chain._merge_context(
        {"rules": ["r"], "examples": ["e"], "constraints": ["c"], "context": {"x": 1}}
    )
    formatted = chain._format_prompt(
        {
            "rules": ["r"],
            "examples": ["e"],
            "constraints": ["c"],
            "original_context": {},
        }
    )
    assert "- r" in formatted
    assert merged["rules"] == ["r"]
    assert chain._call_llm("prompt") == "generated:lcel"
    output = chain.invoke({"query_type": "explanation", "context": {"foo": "bar"}})
    assert isinstance(output, str)


def test_memory_augmented_qa(monkeypatch):
    monkeypatch.setattr(memory_augmented_qa, "require_env", lambda _v: "val")
    monkeypatch.setattr(
        memory_augmented_qa, "CustomGeminiEmbeddings", lambda api_key: object()
    )

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            return None

    class _FakeDriver:
        def session(self):
            return _FakeSession()

        def close(self):
            return None

    class _GraphDB:
        @staticmethod
        def driver(*_args, **_kwargs):
            return _FakeDriver()

    class _FakeVector:
        def similarity_search(self, *_args, **_kwargs):
            return [types.SimpleNamespace(page_content="doc1")]

    class _FakeNeo4jVector:
        @staticmethod
        def from_existing_graph(*_args, **_kwargs):
            return _FakeVector()

    monkeypatch.setitem(
        sys.modules,
        "langchain_neo4j",
        types.SimpleNamespace(Neo4jVector=_FakeNeo4jVector),
    )
    monkeypatch.setattr(memory_augmented_qa, "GraphDatabase", _GraphDB)
    monkeypatch.setattr(
        memory_augmented_qa,
        "GeminiModelClient",
        lambda: types.SimpleNamespace(generate=lambda *_a, **_k: "answer"),
    )

    system = memory_augmented_qa.MemoryAugmentedQASystem()
    resp = system.ask_with_memory("무엇을 해야 하나요?")
    assert resp == "answer"
    assert system.history[-1]["q"] == "무엇을 해야 하나요?"
    system.close()


def test_multi_agent_qa_system(monkeypatch):
    class _FakeKG:
        def __init__(self):
            self._graph = types.SimpleNamespace(session=lambda: _FakeRuleSession())

        def get_constraints_for_query_type(self, _qt):
            return [{"description": "c1"}]

    class _FakeLLM:
        def generate(self, prompt, role="generator"):
            return f"output for {role}"

    class _FakeExampleSelector:
        def __init__(self, *_args, **_kwargs):
            pass

        def select_best_examples(self, *_args, **_kwargs):
            return [{"example": "ex"}]

    class _FakeValidator:
        def __init__(self, *_args, **_kwargs):
            pass

        def cross_validate_qa_pair(self, **_kwargs):
            return {"valid": True}

    class _FakeRuleSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            return [{"text": "rule text"}]

    fake_kg = _FakeKG()
    fake_kg._graph = types.SimpleNamespace(session=lambda: _FakeRuleSession())

    monkeypatch.setattr(multi_agent_qa_system, "GeminiModelClient", lambda: _FakeLLM())
    monkeypatch.setattr(
        multi_agent_qa_system,
        "DynamicExampleSelector",
        lambda kg: _FakeExampleSelector(),
    )
    monkeypatch.setattr(
        multi_agent_qa_system, "CrossValidationSystem", lambda kg: _FakeValidator()
    )

    system = multi_agent_qa_system.MultiAgentQASystem(fake_kg)
    result = system.collaborative_generate("explanation", {"page_id": "p1"})
    assert result["metadata"]["examples_used"]
    assert result["validation"]["valid"] is True


def test_semantic_analysis_utils(monkeypatch):
    monkeypatch.setattr(semantic_analysis, "MIN_FREQ", 1)
    tokens = semantic_analysis.tokenize("This is a Sample sample text with 숫자123")
    assert "sample" in tokens

    counter = semantic_analysis.count_keywords(["alpha beta alpha", "beta gamma"])
    assert counter["alpha"] >= 1

    store = []

    class _SATx:
        def __init__(self, store_ref):
            self.store_ref = store_ref

        def run(self, _query, topics=None, links=None):
            if topics is not None:
                self.store_ref.extend(topics)
            if links is not None:
                self.store_ref.extend(links)

    class _SASession:
        def __init__(self, store_ref):
            self.store_ref = store_ref

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute_write(self, func, items):
            func(_SATx(self.store_ref), items)

        def run(self, *_args, **_kwargs):
            return [{"id": "b1", "content": "alpha beta gamma"}]

    class _SADriver:
        def __init__(self):
            self.session_obj = _SASession(store)

        def session(self):
            return self.session_obj

    driver = _SADriver()
    semantic_analysis.create_topics(driver, [("alpha", 3)])
    semantic_analysis.link_blocks_to_topics(
        driver, [{"id": "b1", "content": "alpha beta"}], [("alpha", 3)]
    )
    assert store


def test_smart_autocomplete(monkeypatch):
    class _SmartSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, query, **_kwargs):
            if "ErrorPattern" in query:
                return [{"pattern": "bad", "desc": "bad pattern"}]
            if "Constraint" in query:
                return [{"pattern": "warn", "desc": "warn desc"}]
            return [
                {"name": "summary", "korean": "요약", "limit": 2, "priority": 1},
                {"name": "explanation", "korean": "설명", "limit": 1, "priority": 0},
            ]

    class _SmartKG:
        def __init__(self):
            self._graph = types.SimpleNamespace(session=lambda: _SmartSession())

    monkeypatch.setattr(
        smart_autocomplete,
        "find_violations",
        lambda text: [{"type": "local", "match": text}],
    )
    sa = smart_autocomplete.SmartAutocomplete(_SmartKG())
    suggestions = sa.suggest_next_query_type([{"type": "summary"}])
    assert any(s["name"] == "explanation" for s in suggestions)

    compliance = sa.suggest_constraint_compliance("bad output warn", "summary")
    assert compliance["violations"]


def test_dynamic_example_selector(monkeypatch):
    class _DESession:
        def __init__(self):
            self.updated = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, query, **params):
            class _Result(list):
                def data(self_inner):
                    return list(self_inner)

            if "RETURN e.text AS example" in query:
                return _Result([{"example": "ex", "rate": 0.9, "usage": 0}])
            if "SET e.usage_count" in query:
                self.updated.append(params["text"])
                return _Result([])
            return _Result([])

    class _DEKG:
        def __init__(self):
            self._graph = types.SimpleNamespace(session=lambda: _DESession())

    selector = dynamic_example_selector.DynamicExampleSelector(_DEKG())
    examples = selector.select_best_examples(
        "explanation", {"text_density": 0.8, "has_table_chart": True}, k=1
    )
    assert examples


def test_adaptive_difficulty(monkeypatch):
    class _ADSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            class _Result:
                def single(self_inner):
                    return {"avg_blocks": 5}

            return _Result()

    fake_kg = types.SimpleNamespace(
        _graph=types.SimpleNamespace(session=lambda: _ADSession())
    )
    adjuster = adaptive_difficulty.AdaptiveDifficultyAdjuster(fake_kg)
    complexity = adjuster.analyze_image_complexity({"text_density": 0.8})
    assert complexity["estimated_blocks"] == 5
    adjustments = adjuster.adjust_query_requirements(complexity, "explanation")
    assert adjustments["min_length"] >= 300


def test_list_models_script(monkeypatch):
    import importlib
    import builtins

    monkeypatch.setenv("GEMINI_API_KEY", "key")

    class _FakeModel:
        def __init__(self, name, methods=None):
            self.name = name
            self.supported_generation_methods = methods or ["generateContent"]

    fake_genai = types.SimpleNamespace(
        configure=lambda api_key: None,
        list_models=lambda: [_FakeModel("m1"), _FakeModel("m2", ["other"])],
    )
    monkeypatch.setitem(sys.modules, "google.generativeai", fake_genai)

    captured = []
    monkeypatch.setattr(
        builtins,
        "print",
        lambda *args, **kwargs: captured.append(" ".join(str(a) for a in args)),
    )
    monkeypatch.setattr(
        builtins, "exit", lambda code=0: captured.append(f"exit:{code}")
    )

    import src.list_models as lm

    importlib.reload(lm)
    assert captured


def test_qa_generator_script(monkeypatch):
    import importlib
    import builtins
    import io

    monkeypatch.setenv("GEMINI_API_KEY", "key")

    class _FakeCompletions:
        def create(self, model, messages, temperature=0):
            content = (
                "1. 첫 번째 질문\n2. 두 번째 질문\n3. 세 번째 질문\n4. 네 번째 질문"
            )
            return types.SimpleNamespace(
                choices=[
                    types.SimpleNamespace(
                        message=types.SimpleNamespace(content=content)
                    )
                ]
            )

    class _FakeChat:
        def __init__(self):
            self.completions = _FakeCompletions()

    class _FakeOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = _FakeChat()

    fake_openai_module = types.SimpleNamespace(OpenAI=_FakeOpenAI)
    monkeypatch.setitem(sys.modules, "openai", fake_openai_module)

    files: dict = {}

    class _MemoBuffer(io.StringIO):
        def close(self):
            # Keep buffer accessible for assertions
            self.seek(0)
            return None

    def _fake_open(path, mode="r", encoding=None):
        if "r" in mode:
            return io.StringIO("prompt")
        buf = _MemoBuffer()
        files[path] = buf
        return buf

    monkeypatch.setattr(builtins, "open", _fake_open)
    monkeypatch.setattr(builtins, "exit", lambda code=0: None)
    captured = []
    monkeypatch.setattr(
        builtins,
        "print",
        lambda *args, **kwargs: captured.append(" ".join(str(a) for a in args)),
    )

    import src.qa_generator as qg

    importlib.reload(qg)
    assert "QA Results" in files.get("qa_result_4pairs.md", io.StringIO()).getvalue()
