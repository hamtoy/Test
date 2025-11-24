import logging
import pytest
from jinja2 import TemplateNotFound

from src.dynamic_template_generator import DynamicTemplateGenerator


class _FakeSession:
    def __init__(self, rows):
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, *args, **kwargs):
        return self.rows


class _FakeDriver:
    def __init__(self, rows):
        self._rows = rows

    def session(self):
        return _FakeSession(self._rows)

    def close(self):
        return None


class _FakeTemplate:
    def __init__(self, name):
        self.name = name
        self.last_kwargs = None

    def render(self, **kwargs):
        self.last_kwargs = kwargs
        return f"{self.name}-rendered-calc-{kwargs.get('calc_allowed')}"


class _FakeEnv:
    def __init__(self, fallback_template):
        self.calls = 0
        self.fallback_template = fallback_template

    def get_template(self, name):
        self.calls += 1
        if self.calls == 1:
            raise TemplateNotFound(name)
        return self.fallback_template


def _make_dtg(rows, env):
    dtg = object.__new__(DynamicTemplateGenerator)
    dtg.driver = _FakeDriver(rows)
    dtg.logger = logging.getLogger("test")
    dtg.jinja_env = env
    return dtg


def test_generate_prompt_uses_fallback_and_calc_flag():
    tmpl = _FakeTemplate("fallback")
    env = _FakeEnv(tmpl)
    rows = [
        {
            "type_name": "설명",
            "rules": ["r1"],
            "constraints": ["c1"],
            "best_practices": ["bp1"],
            "examples": [{"text": "ex", "type": "positive"}],
        }
    ]
    dtg = _make_dtg(rows, env)

    context = {"used_calc_query_count": 1}
    output = dtg.generate_prompt_for_query_type("explanation", context)

    assert "fallback-rendered" in output  # fallback template used
    assert (
        tmpl.last_kwargs["calc_allowed"] is False
    )  # derived from used_calc_query_count


def test_generate_prompt_missing_query_type():
    dtg = _make_dtg([], _FakeEnv(_FakeTemplate("fallback")))
    with pytest.raises(ValueError):
        dtg.generate_prompt_for_query_type("unknown", {})


def test_generate_validation_checklist():
    rows = [{"item": "i1", "category": "cat"}]
    dtg = _make_dtg(rows, _FakeEnv(_FakeTemplate("fallback")))
    session = {"turns": [{"type": "summary"}, {"type": "explanation"}]}
    checklist = dtg.generate_validation_checklist(session)
    # One item per query type; duplicates allowed since we provide same rows
    assert len(checklist) == 2
    assert checklist[0]["item"] == "i1"
    assert checklist[0]["query_type"] in {"summary", "explanation"}


def test_main_shows_error_on_missing_env(monkeypatch, capsys):
    monkeypatch.setattr("os.getenv", lambda *_a, **_k: None)
    import runpy

    runpy.run_module("src.dynamic_template_generator", run_name="__main__")
    out = capsys.readouterr().out
    assert "실패" in out or "환경 변수" in out
