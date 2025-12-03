import types
from unittest.mock import AsyncMock

import pytest

from src.agent import GeminiAgent
from src.config import AppConfig
from src.config.exceptions import APIRateLimitError

VALID_API_KEY = "AIza" + "D" * 35


def _stub_agent(monkeypatch: pytest.MonkeyPatch) -> GeminiAgent:
    """Create a GeminiAgent with a minimal Jinja stub and valid config."""
    monkeypatch.setenv("GEMINI_API_KEY", VALID_API_KEY)
    jinja_env = types.SimpleNamespace(
        get_template=lambda name: types.SimpleNamespace(render=lambda **_k: "x")
    )
    agent = GeminiAgent(AppConfig(), jinja_env=jinja_env)  # type: ignore[arg-type]
    agent._rate_limiter = None  # ensure retry path does not rely on aiolimiter
    return agent


@pytest.mark.asyncio
async def test_generate_query_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _stub_agent(monkeypatch)

    class ResourceExhausted(Exception):
        pass

    agent.client.execute = AsyncMock(side_effect=ResourceExhausted("quota"))  # type: ignore[method-assign]
    agent.llm_provider = None

    with pytest.raises(APIRateLimitError):
        await agent.generate_query("ocr")


@pytest.mark.asyncio
async def test_generate_query_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _stub_agent(monkeypatch)
    agent.client.execute = AsyncMock(return_value="")  # type: ignore[method-assign]
    agent.llm_provider = None

    result = await agent.generate_query("ocr text")
    assert result == []


@pytest.mark.asyncio
async def test_generate_query_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _stub_agent(monkeypatch)
    agent.client.execute = AsyncMock(return_value="{bad")  # type: ignore[method-assign]
    agent.llm_provider = None

    result = await agent.generate_query("ocr text")
    assert result == []
