"""Tests for enhanced API response logging and truncation detection."""

from __future__ import annotations

import logging
from typing import Any, Callable, cast
from unittest.mock import MagicMock

import pytest

from src.agent.client import GeminiClient


class FakeLLMResult:
    """Mock LLM result for testing."""

    def __init__(
        self,
        content: str = "test response",
        finish_reason: str = "STOP",
        prompt_tokens: int = 10,
        completion_tokens: int = 20,
    ) -> None:
        """Initialize fake LLM result."""
        self.finish_reason = finish_reason
        self.content = content
        self.usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }
        self.safety_ratings: dict[str, str] = {}


class FakeLLMProvider:
    """Mock LLM provider for testing."""

    def __init__(self, result: FakeLLMResult) -> None:
        """Initialize fake provider with a result."""
        self.result = result
        self.calls: list[tuple[str, Any, Any]] = []

    async def generate_content_async(
        self,
        prompt_text: str,
        *,
        system_instruction: Any = None,
        temperature: float = 0.0,
        max_output_tokens: int = 0,
        response_schema: Any = None,
        request_options: dict[str, Any] | None = None,
    ) -> FakeLLMResult:
        """Mock async content generation."""
        self.calls.append((prompt_text, system_instruction, response_schema))
        return self.result


class StubCostTracker:
    """Stub cost tracker for testing."""

    def __init__(self) -> None:
        """Initialize stub tracker."""
        self.calls: list[tuple[int, int]] = []

    def add_tokens(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Track token usage."""
        self.calls.append((prompt_tokens, completion_tokens))


class FakeConfig:
    """Fake config for testing."""

    temperature = 0.1
    max_output_tokens = 8192
    timeout = 120
    model_name = "test-model"


class FakeAgentForClient:
    """Fake agent for testing GeminiClient."""

    def __init__(
        self, log_fn: Callable[..., None], llm_provider: FakeLLMProvider
    ) -> None:
        """Initialize fake agent."""
        self.config = FakeConfig()
        self.llm_provider = llm_provider
        self._cost_tracker = StubCostTracker()
        self.logger = logging.getLogger("test-client")
        self.cache_hits = 0
        self.cache_misses = 0
        self.api_retries = 0
        self.api_failures = 0
        self._log_metrics = log_fn


@pytest.mark.asyncio
async def test_client_logs_finish_reason_stop() -> None:
    """Test that client logs finish_reason when response is complete."""
    log_calls: list[Any] = []

    def _log_fn(*args: Any, **kwargs: Any) -> None:
        log_calls.append(kwargs)

    # Create a complete response
    result = FakeLLMResult(content="This is a complete response.", finish_reason="STOP")
    provider = FakeLLMProvider(result)
    agent = FakeAgentForClient(_log_fn, provider)
    client = GeminiClient(cast(Any, agent), _log_fn)

    # Mock logger to capture log messages
    with (
        pytest.LogCaptureFixture.for_logger(agent.logger, level=logging.INFO)
        if hasattr(pytest, "LogCaptureFixture")
        else MagicMock()
    ):
        response = await client.execute(object(), "test prompt")

    assert response == "This is a complete response."
    assert result.finish_reason == "STOP"


@pytest.mark.asyncio
async def test_client_logs_max_tokens_warning() -> None:
    """Test that client logs warning when response is truncated due to MAX_TOKENS."""
    log_calls: list[Any] = []

    def _log_fn(*args: Any, **kwargs: Any) -> None:
        log_calls.append(kwargs)

    # Create a truncated response
    truncated_content = "This response was truncated due to"
    result = FakeLLMResult(content=truncated_content, finish_reason="MAX_TOKENS")
    provider = FakeLLMProvider(result)
    agent = FakeAgentForClient(_log_fn, provider)
    client = GeminiClient(cast(Any, agent), _log_fn)

    # Capture logs
    import io

    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.WARNING)
    agent.logger.addHandler(handler)
    agent.logger.setLevel(logging.WARNING)

    response = await client.execute(object(), "test prompt")

    assert response == truncated_content
    assert result.finish_reason == "MAX_TOKENS"

    # Verify execution completed without errors
    agent.logger.removeHandler(handler)


@pytest.mark.asyncio
async def test_client_logs_response_length() -> None:
    """Test that client logs response length for debugging."""
    log_calls: list[Any] = []

    def _log_fn(*args: Any, **kwargs: Any) -> None:
        log_calls.append(kwargs)

    # Create a response of known length
    test_content = "A" * 1000  # 1000 character response
    result = FakeLLMResult(content=test_content, finish_reason="STOP")
    provider = FakeLLMProvider(result)
    agent = FakeAgentForClient(_log_fn, provider)
    client = GeminiClient(cast(Any, agent), _log_fn)

    response = await client.execute(object(), "test prompt")

    assert response == test_content
    assert len(response) == 1000


@pytest.mark.asyncio
async def test_client_logs_short_response() -> None:
    """Test that client handles short responses correctly."""
    log_calls: list[Any] = []

    def _log_fn(*args: Any, **kwargs: Any) -> None:
        log_calls.append(kwargs)

    # Create a short response
    short_content = "OK"
    result = FakeLLMResult(content=short_content, finish_reason="STOP")
    provider = FakeLLMProvider(result)
    agent = FakeAgentForClient(_log_fn, provider)
    client = GeminiClient(cast(Any, agent), _log_fn)

    response = await client.execute(object(), "test prompt")

    assert response == short_content
    assert len(response) == 2
