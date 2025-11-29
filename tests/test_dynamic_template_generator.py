from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest
from jinja2 import TemplateNotFound

from src.processing.template_generator import DynamicTemplateGenerator


class _FakeSession:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def __enter__(self) -> "_FakeSession":
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any
    ) -> None:
        return None

    def run(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return self.rows


class _FakeDriver:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def session(self) -> _FakeSession:
        return _FakeSession(self._rows)

    def close(self) -> None:
        return None


class _FakeTemplate:
    def __init__(self, name: str) -> None:
        self.name = name
        self.last_kwargs: dict[str, object] | None = None

    def render(self, **kwargs: Any) -> str:
        self.last_kwargs = kwargs
        return f"{self.name}-rendered-calc-{kwargs.get('calc_allowed')}"


class _FakeEnv:
    def __init__(self, fallback_template: _FakeTemplate) -> None:
        self.calls = 0
        self.fallback_template = fallback_template

    def get_template(self, name: str) -> _FakeTemplate:
        self.calls += 1
        if self.calls == 1:
            raise TemplateNotFound(name)
        return self.fallback_template


def _make_dtg(rows: list[dict[str, Any]], env: _FakeEnv) -> DynamicTemplateGenerator:
    dtg = object.__new__(DynamicTemplateGenerator)
    dtg.driver = _FakeDriver(rows)  # type: ignore[assignment]
    dtg.logger = logging.getLogger("test")
    dtg.jinja_env = env  # type: ignore[assignment]
    return dtg


def test_generate_prompt_uses_fallback_and_calc_flag() -> None:
    tmpl = _FakeTemplate("fallback")
    env = _FakeEnv(tmpl)
    rows: list[dict[str, Any]] = [
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
    assert tmpl.last_kwargs is not None
    assert (
        tmpl.last_kwargs["calc_allowed"] is False
    )  # derived from used_calc_query_count


def test_generate_prompt_missing_query_type() -> None:
    dtg = _make_dtg([], _FakeEnv(_FakeTemplate("fallback")))
    with pytest.raises(ValueError):
        dtg.generate_prompt_for_query_type("unknown", {})


def test_generate_validation_checklist() -> None:
    rows: list[dict[str, Any]] = [{"item": "i1", "category": "cat"}]
    dtg = _make_dtg(rows, _FakeEnv(_FakeTemplate("fallback")))
    session: dict[str, Any] = {"turns": [{"type": "summary"}, {"type": "explanation"}]}
    checklist = dtg.generate_validation_checklist(session)
    # One item per query type; duplicates allowed since we provide same rows
    assert len(checklist) == 2
    assert checklist[0]["item"] == "i1"
    assert checklist[0]["query_type"] in {"summary", "explanation"}


def test_main_shows_error_on_missing_env(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("os.getenv", lambda *_a, **_k: None)
    import runpy

    runpy.run_module("src.processing.template_generator", run_name="__main__")
    out = capsys.readouterr().out
    assert "실패" in out or "환경 변수" in out
