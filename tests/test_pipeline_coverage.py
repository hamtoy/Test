from __future__ import annotations

import types
from src import integrated_qa_pipeline as iqap
from src import real_time_constraint_enforcer as rtce


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
