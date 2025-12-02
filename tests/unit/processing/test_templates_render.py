import pytest
from jinja2 import Environment, FileSystemLoader

from src.config import AppConfig

VALID_API_KEY = "AIza" + "E" * 35
REQUIRED_TEMPLATES = [
    "system/eval.j2",
    "system/query_gen.j2",
    "system/rewrite.j2",
    "user/query_gen.j2",
    "user/rewrite.j2",
]


@pytest.fixture
def jinja_env(monkeypatch: pytest.MonkeyPatch) -> Environment:
    monkeypatch.setenv("GEMINI_API_KEY", VALID_API_KEY)
    config = AppConfig()
    env = Environment(
        loader=FileSystemLoader(config.template_dir),
        autoescape=True,
    )
    return env


def test_required_templates_render(jinja_env: Environment) -> None:
    context = {
        "ocr_text": "sample ocr",
        "user_intent": "intent",
        "best_answer": "best",
        "response_schema": "{}",
    }
    for name in REQUIRED_TEMPLATES:
        template = jinja_env.get_template(name)
        rendered = template.render(**context)
        assert rendered
        assert isinstance(rendered, str)
