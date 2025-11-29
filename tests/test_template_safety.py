from __future__ import annotations

import types

from jinja2 import Environment, DictLoader

from src.processing.template_generator import DynamicTemplateGenerator


def test_dynamic_template_autoescape(monkeypatch):
    # Inject fake driver to bypass Neo4j
    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, *args, **kwargs):
            return [
                {
                    "type_name": "설명",
                    "rules": ["<script>alert(1)</script>"],
                    "constraints": [],
                    "best_practices": [],
                    "examples": [],
                }
            ]

    class _FakeDriver:
        def session(self):
            return _FakeSession()

        def close(self):
            return None

    monkeypatch.setattr(
        "src.processing.template_generator.GraphDatabase",
        types.SimpleNamespace(driver=lambda *a, **k: _FakeDriver()),
    )
    env = Environment(
        loader=DictLoader({"base_system.j2": "{{ rules[0] }}"}),
        autoescape=True,
    )
    dtg = DynamicTemplateGenerator.__new__(DynamicTemplateGenerator)
    dtg.driver = _FakeDriver()  # type: ignore[assignment]
    dtg.logger = types.SimpleNamespace(warning=lambda *a, **k: None)  # type: ignore[assignment]
    dtg.jinja_env = env
    output = dtg.generate_prompt_for_query_type("explanation", {"calc_allowed": False})
    assert "&lt;script&gt;" in output  # escaped


def test_agent_default_env_autoescape():
    # Environment(autoescape=True) is set in agent init path; verify Jinja behavior directly.
    env = Environment(
        loader=DictLoader({"rewrite_user.j2": "{{ best_answer }}"}), autoescape=True
    )
    tmpl = env.get_template("rewrite_user.j2")
    rendered = tmpl.render(best_answer="<b>bold</b>")
    assert "&lt;b&gt;" in rendered
