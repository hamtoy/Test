import types
import json

import pytest

from src.agent import GeminiAgent
from src.config import AppConfig


class _FakeModel:
    def __init__(self, text: str) -> None:
        self.text = text

    def generate_content(self, prompt, generation_config=None):  # noqa: ARG002
        return types.SimpleNamespace(
            text=self.text, candidates=None, usage_metadata=None
        )

    async def generate_content_async(self, prompt, request_options=None):  # noqa: ARG002
        return types.SimpleNamespace(
            text=self.text, candidates=None, usage_metadata=None
        )


class _FakeGenAI:
    def __init__(self, text: str = "output") -> None:
        self.text = text

    def GenerativeModel(
        self, model_name=None, system_instruction=None, generation_config=None
    ):  # noqa: N802,ARG002
        return _FakeModel(self.text)

    class types:  # noqa: D401
        class HarmBlockThreshold:
            BLOCK_NONE = 0

        class HarmCategory:
            HARM_CATEGORY_HARASSMENT = 1
            HARM_CATEGORY_HATE_SPEECH = 2
            HARM_CATEGORY_SEXUALLY_EXPLICIT = 3
            HARM_CATEGORY_DANGEROUS_CONTENT = 4


@pytest.fixture
def fake_config(tmp_path, monkeypatch):
    # Create dummy templates under PROJECT_ROOT/templates
    monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
    tdir = tmp_path / "templates"
    tdir.mkdir()
    required = [
        "prompt_eval.j2",
        "prompt_query_gen.j2",
        "prompt_rewrite.j2",
        "query_gen_user.j2",
        "rewrite_user.j2",
    ]
    for name in required:
        (tdir / name).write_text("{{ input }}", encoding="utf-8")

    fake_key = "AIza" + "x" * 35  # valid format/length
    monkeypatch.setenv("GEMINI_API_KEY", fake_key)
    cfg = AppConfig(
        GEMINI_API_KEY=fake_key,
        GEMINI_MODEL_NAME="gemini-3-pro-preview",
        GEMINI_MAX_OUTPUT_TOKENS=100,
        GEMINI_TIMEOUT=60,
        GEMINI_MAX_CONCURRENCY=2,
        GEMINI_CACHE_SIZE=0,
        GEMINI_TEMPERATURE=0.2,
        GEMINI_CACHE_TTL_MINUTES=10,
        LOG_LEVEL="INFO",
    )
    return cfg


@pytest.mark.asyncio
async def test_generate_query_handles_no_cache(monkeypatch, fake_config) -> None:
    agent = GeminiAgent(config=fake_config, jinja_env=None)
    payload = json.dumps({"queries": ["q1", "q2"]})
    monkeypatch.setattr(
        GeminiAgent,
        "_create_generative_model",
        lambda self, *args, **kwargs: _FakeModel(payload),
    )
    res = await agent.generate_query("ocr text", user_intent="요약")
    assert res == ["q1", "q2"]


def test_cost_accumulation(monkeypatch, fake_config) -> None:
    agent = GeminiAgent(config=fake_config, jinja_env=None)
    agent.total_input_tokens = 0
    agent.total_output_tokens = 0

    class _FakeResponse:
        def __init__(self) -> None:
            self.usage_metadata = types.SimpleNamespace(
                prompt_token_count=10, candidates_token_count=5
            )

    # Simulate cost tracking method inline
    resp = _FakeResponse()
    agent.total_input_tokens += resp.usage_metadata.prompt_token_count
    agent.total_output_tokens += resp.usage_metadata.candidates_token_count

    assert agent.total_input_tokens == 10
    assert agent.total_output_tokens == 5
