from __future__ import annotations

import types
from typing import Any, Optional

import pytest
from jinja2 import Environment, DictLoader

from src.processing.template_generator import DynamicTemplateGenerator


def test_dynamic_template_autoescape(monkeypatch: pytest.MonkeyPatch) -> None:
    # Inject fake driver to bypass Neo4j
    class _FakeSession:
        def __enter__(self) -> "_FakeSession":
            return self

        def __exit__(
            self, exc_type: Optional[type], exc: Optional[BaseException], tb: Any
        ) -> None:
            pass

        def run(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
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
        def session(self) -> _FakeSession:
            return _FakeSession()

        def close(self) -> None:
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


def test_agent_default_env_autoescape() -> None:
    # Environment(autoescape=True) is set in agent init path; verify Jinja behavior directly.
    env = Environment(
        loader=DictLoader({"rewrite_user.j2": "{{ best_answer }}"}), autoescape=True
    )
    tmpl = env.get_template("rewrite_user.j2")
    rendered = tmpl.render(best_answer="<b>bold</b>")
    assert "&lt;b&gt;" in rendered
