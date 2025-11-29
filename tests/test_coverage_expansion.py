import builtins
import importlib
import logging
import sys
import types

from neo4j.exceptions import Neo4jError

import src.features.difficulty as adaptive_difficulty
import src.caching.layer as caching_layer
import src.analysis.cross_validation as cross_validation
import src.processing.example_selector as dynamic_example_selector
import src.infra.health as health_check
import src.infra.logging as logging_setup
import src.infra.constraints as rtce
import src.features.autocomplete as smart_autocomplete


def test_smart_autocomplete_handles_missing_graph():
    sa = smart_autocomplete.SmartAutocomplete(types.SimpleNamespace())  # type: ignore[arg-type]
    assert sa.suggest_next_query_type([]) == []


def test_smart_autocomplete_session_none(monkeypatch):
    class _KG:
        def graph_session(self):
            class _Ctx:
                def __enter__(self):
                    return None

                def __exit__(self, exc_type, exc, tb):
                    return False

            return _Ctx()

    sa = smart_autocomplete.SmartAutocomplete(_KG())  # type: ignore[arg-type]
    assert sa.suggest_next_query_type([{"type": "summary"}]) == []


def test_smart_autocomplete_filters_by_limit():
    class _Sess:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, _cypher):
            return [
                {"name": "summary", "korean": "요약", "limit": 1, "priority": 1},
                {"name": "explore", "korean": "탐색", "limit": None, "priority": 0},
            ]

    kg = types.SimpleNamespace(_graph=types.SimpleNamespace(session=lambda: _Sess()))
    sa = smart_autocomplete.SmartAutocomplete(kg)  # type: ignore[arg-type]
    suggestions = sa.suggest_next_query_type([{"type": "summary"}])
    assert all(s["name"] != "summary" for s in suggestions)


def test_smart_autocomplete_constraint_missing_graph(monkeypatch):
    monkeypatch.setattr(smart_autocomplete, "find_violations", lambda text: [])
    sa = smart_autocomplete.SmartAutocomplete(types.SimpleNamespace())  # type: ignore[arg-type]
    res = sa.suggest_constraint_compliance("draft", "summary")
    assert res == {"violations": [], "suggestions": []}


def test_smart_autocomplete_constraint_session_none(monkeypatch):
    monkeypatch.setattr(smart_autocomplete, "find_violations", lambda text: [])

    class _KG:
        def graph_session(self):
            class _Ctx:
                def __enter__(self):
                    return None

                def __exit__(self, exc_type, exc, tb):
                    return False

            return _Ctx()

    sa = smart_autocomplete.SmartAutocomplete(_KG())  # type: ignore[arg-type]
    res = sa.suggest_constraint_compliance("draft", "summary")
    assert res["violations"] == []
    assert res["suggestions"] == []


def test_real_time_constraint_stream_final_validation(monkeypatch):
    class _KG:
        def get_constraints_for_query_type(self, _qt):
            return []

    enforcer = rtce.RealTimeConstraintEnforcer(_KG())  # type: ignore[arg-type]
    monkeypatch.setattr(enforcer, "_get_original_blocks", lambda: [])

    events = list(enforcer.stream_with_validation(iter(["ok", " text"]), "summary"))
    types_seen = [e["type"] for e in events]
    assert types_seen[:2] == ["content", "content"]
    assert events[-1]["type"] == "final_validation"


def test_real_time_constraint_get_original_blocks_no_session():
    class _KG:
        def graph_session(self):
            class _Ctx:
                def __enter__(self):
                    return None

                def __exit__(self, exc_type, exc, tb):
                    return False

            return _Ctx()

    enforcer = rtce.RealTimeConstraintEnforcer(_KG())  # type: ignore[arg-type]
    assert enforcer._get_original_blocks() == []


def test_real_time_constraint_get_original_blocks_exception():
    class _KG:
        def graph_session(self):
            class _Ctx:
                def __enter__(self):
                    raise RuntimeError("boom")

                def __exit__(self, exc_type, exc, tb):
                    return False

            return _Ctx()

    enforcer = rtce.RealTimeConstraintEnforcer(_KG())  # type: ignore[arg-type]
    assert enforcer._get_original_blocks() == []


def test_real_time_constraint_similarity_issue(monkeypatch):
    enforcer = rtce.RealTimeConstraintEnforcer(types.SimpleNamespace())  # type: ignore[arg-type]
    monkeypatch.setattr(
        enforcer, "_get_original_blocks", lambda: [{"content": "repeat me"}]
    )
    result = enforcer.validate_complete_output("repeat me", "explanation")
    issues = result.get("issues", [])
    assert isinstance(issues, list)
    found_similarity = any("너무 유사" in str(issue) for issue in issues)
    assert found_similarity, "Expected similarity issue not found"


def test_health_check_graph_missing():
    kg = types.SimpleNamespace(_graph=None)
    assert health_check.check_neo4j_connection(kg) is False  # type: ignore[arg-type]


def test_health_check_unknown_exception(monkeypatch):
    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            raise ValueError("boom")

        def single(self):
            return None

    kg = types.SimpleNamespace(_graph=types.SimpleNamespace(session=lambda: _Session()))
    assert health_check.check_neo4j_connection(kg) is False  # type: ignore[arg-type]


def test_sensitive_filter_handles_non_string_args():
    filt = logging_setup.SensitiveDataFilter()
    raw_key = "AIza" + "1" * 35
    record = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Key %s %s",
        args=(raw_key, 123),
        exc_info=None,
        func=None,
        sinfo=None,
    )
    assert filt.filter(record)
    assert "[FILTERED_API_KEY]" in record.msg
    args = record.args
    assert args is not None
    assert isinstance(args, tuple) and args[-1] == 123


def test_list_models_exits_without_key(monkeypatch):
    import importlib
    import os

    original_getenv = os.getenv
    monkeypatch.setattr(
        os,
        "getenv",
        lambda key, default=None: None
        if key == "GEMINI_API_KEY"
        else original_getenv(key, default),
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    fake_genai = types.SimpleNamespace(
        configure=lambda api_key=None: None, list_models=lambda: []
    )
    monkeypatch.setitem(sys.modules, "google.generativeai", fake_genai)

    captured = []
    monkeypatch.setattr(
        builtins,
        "print",
        lambda *args, **kwargs: captured.append(" ".join(map(str, args))),
    )
    monkeypatch.setattr(
        builtins, "exit", lambda code=0: captured.append(f"exit:{code}")
    )

    sys.modules.pop("src.list_models", None)
    sys.modules.pop("src.llm.list_models", None)
    import src.llm.list_models as lm

    importlib.reload(lm)
    assert any("No API key" in msg for msg in captured)
    assert any(msg.endswith("exit:1") or msg == "exit:1" for msg in captured)


def test_dynamic_example_selector_no_graph_returns_empty(caplog):
    caplog.set_level(logging.DEBUG)
    selector = dynamic_example_selector.DynamicExampleSelector(types.SimpleNamespace())  # type: ignore[arg-type]
    assert selector.select_best_examples("qt", {}, k=1) == []


def test_dynamic_example_selector_session_none(monkeypatch):
    class _KG:
        def graph_session(self):
            class _Ctx:
                def __enter__(self):
                    return None

                def __exit__(self, exc_type, exc, tb):
                    return False

            return _Ctx()

    selector = dynamic_example_selector.DynamicExampleSelector(_KG())  # type: ignore[arg-type]
    assert selector.select_best_examples("qt", {}, k=1) == []


def test_dynamic_example_selector_handles_exception(monkeypatch):
    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            raise RuntimeError("query fail")

    class _KG:
        def graph_session(self):
            return _Session

    selector = dynamic_example_selector.DynamicExampleSelector(_KG())  # type: ignore[arg-type]
    assert selector.select_best_examples("qt", {}, k=1) == []


def test_caching_layer_import_fallback(monkeypatch):
    original_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "redis":
            raise ImportError("missing redis")
        return original_import(name, *args, **kwargs)

    # Remove all caching and redis modules from cache
    monkeypatch.delitem(sys.modules, "src.caching.layer", raising=False)
    monkeypatch.delitem(sys.modules, "src.caching", raising=False)
    monkeypatch.delitem(sys.modules, "redis", raising=False)
    monkeypatch.delitem(sys.modules, "redis.client", raising=False)
    monkeypatch.delitem(sys.modules, "redis.connection", raising=False)
    monkeypatch.setattr(builtins, "__import__", _fake_import)
    module = importlib.import_module("src.caching.layer")
    assert module.redis is None


def test_caching_layer_handles_bad_cache_and_write_error(monkeypatch):
    rows = [{"id": "1", "text": "t1", "section": "s1"}]

    class _Redis:
        def __init__(self):
            self.store = {"rules:qt": "not-json"}

        def get(self, key):
            return self.store.get(key)

        def setex(self, *_args, **_kwargs):
            raise RuntimeError("write fail")

    layer = caching_layer.CachingLayer(
        kg=types.SimpleNamespace(_graph=None),  # type: ignore[arg-type]
        redis_client=None,
    )
    layer.redis = _Redis()  # type: ignore[assignment]
    layer._fetch_rules_from_graph = lambda qt: rows  # type: ignore[method-assign, assignment]
    assert layer.get_rules_cached("qt") == rows


def test_caching_layer_invalidate_without_redis():
    layer = caching_layer.CachingLayer(kg=types.SimpleNamespace(_graph=None))  # type: ignore[arg-type]
    assert layer.invalidate_cache() == 0
    layer.redis = types.SimpleNamespace(keys=lambda pattern: [], delete=lambda *k: 0)
    assert layer.invalidate_cache() == 0


def test_caching_layer_fetch_without_graph():
    layer = caching_layer.CachingLayer(kg=types.SimpleNamespace())  # type: ignore[arg-type]
    assert layer._fetch_rules_from_graph("qt") == []


def test_adaptive_difficulty_missing_graph_logs(monkeypatch, caplog):
    caplog.set_level(logging.WARNING)
    adjuster = adaptive_difficulty.AdaptiveDifficultyAdjuster(types.SimpleNamespace())  # type: ignore[arg-type]
    result = adjuster.analyze_image_complexity({"text_density": 0.9})
    assert result["estimated_blocks"] == 0.0
    assert any("Failed to estimate blocks" in rec.message for rec in caplog.records)


def test_adaptive_difficulty_reasoning_requires_evidence():
    adjuster = adaptive_difficulty.AdaptiveDifficultyAdjuster(types.SimpleNamespace())  # type: ignore[arg-type]
    complexity = {"reasoning_possible": True, "level": "medium"}
    adjustments = adjuster.adjust_query_requirements(complexity, "reasoning")
    assert adjustments["evidence_required"] is True


def test_cross_validation_grounding_branches(monkeypatch):
    cvs = cross_validation.CrossValidationSystem(types.SimpleNamespace())  # type: ignore[arg-type]
    res = cvs._check_image_grounding("ans", {"page_id": "p"})
    assert res["note"] == "graph 없음"

    class _SessionNone:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    class _KG:
        def graph_session(self):
            return _SessionNone()

    cvs2 = cross_validation.CrossValidationSystem(_KG())  # type: ignore[arg-type]
    res2 = cvs2._check_image_grounding("ans", {"page_id": "p"})
    assert res2["note"] == "graph 없음"

    class _NeoSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *_args, **_kwargs):
            raise Neo4jError("neo boom")

    cvs3 = cross_validation.CrossValidationSystem(
        types.SimpleNamespace(  # type: ignore[arg-type]
            _graph=types.SimpleNamespace(session=lambda: _NeoSession())
        )
    )
    res3 = cvs3._check_image_grounding("ans", {"page_id": "p"})
    assert res3["note"] == "Neo4j 조회 실패"


def test_cross_validation_rule_compliance_graph_missing():
    class _KG:
        def get_constraints_for_query_type(self, *_args, **_kwargs):
            return []

    cvs = cross_validation.CrossValidationSystem(_KG())  # type: ignore[arg-type]
    res = cvs._check_rule_compliance("answer", "qt")
    assert res["violations"] == []


def test_cross_validation_novelty_store_paths():
    class _Similar:
        def __init__(self, sim):
            self.metadata = {"similarity": sim}

    class _StoreHigh:
        def similarity_search(self, *_args, **_kwargs):
            return [_Similar(0.99)]

    cvs_high = cross_validation.CrossValidationSystem(
        types.SimpleNamespace(_vector_store=_StoreHigh())  # type: ignore[arg-type]
    )
    res_high = cvs_high._check_novelty("q")
    assert res_high["too_similar"] is True

    class _StoreEmpty:
        def similarity_search(self, *_args, **_kwargs):
            return []

    cvs_empty = cross_validation.CrossValidationSystem(
        types.SimpleNamespace(_vector_store=_StoreEmpty())  # type: ignore[arg-type]
    )
    res_empty = cvs_empty._check_novelty("q")
    assert res_empty["novel"] is True
