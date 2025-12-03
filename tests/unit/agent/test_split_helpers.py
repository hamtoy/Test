import logging
from types import TracebackType
from typing import Any, Callable, Dict, List, Tuple, cast

import pytest

from src.agent.client import GeminiClient
from src.agent.retry_handler import RetryHandler


class DummyAsyncContext:
    def __init__(self) -> None:
        self.entered = 0

    async def __aenter__(self) -> "DummyAsyncContext":
        self.entered += 1
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        return False


class _GoogleExceptions:
    class ResourceExhausted(Exception):
        pass

    class ServiceUnavailable(Exception):
        pass

    class DeadlineExceeded(Exception):
        pass

    class Cancelled(Exception):
        pass


class FakeClient:
    def __init__(self, side_effects: List[str | Exception]) -> None:
        self.side_effects = side_effects
        self.calls = 0

    async def execute(self, model: Any, prompt: str) -> str:
        self.calls += 1
        outcome: str | Exception = self.side_effects.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeAgentForRetry:
    def __init__(self, side_effects: List[str | Exception]) -> None:
        self.logger = logging.getLogger("test-retry")
        self._rate_limiter = DummyAsyncContext()
        self._semaphore = DummyAsyncContext()
        self.api_retries = 0
        self.api_failures = 0
        self.client = FakeClient(side_effects)

    def _google_exceptions(self) -> Any:
        return _GoogleExceptions

    def _is_rate_limit_error(self, exc: Exception) -> bool:
        return False


class StubCostTracker:
    def __init__(self) -> None:
        self.calls: List[Tuple[int, int]] = []

    def add_tokens(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.calls.append((prompt_tokens, completion_tokens))


class FakeLLMResult:
    def __init__(self) -> None:
        self.finish_reason = "STOP"
        self.content = "hello-response"
        self.usage = {"prompt_tokens": 1, "completion_tokens": 2}
        self.safety_ratings: Dict[str, str] = {}


class FakeLLMProvider:
    def __init__(self) -> None:
        self.calls: List[Tuple[str, Any, Any]] = []

    async def generate_content_async(
        self,
        prompt_text: str,
        *,
        system_instruction: Any = None,
        temperature: float = 0.0,
        max_output_tokens: int = 0,
        response_schema: Any = None,
        request_options: Dict[str, Any] | None = None,
    ) -> FakeLLMResult:
        self.calls.append((prompt_text, system_instruction, response_schema))
        return FakeLLMResult()


class FakeAgentForClient:
    def __init__(self, log_fn: Callable[..., None]) -> None:
        class _Config:
            temperature = 0.1
            max_output_tokens = 10
            timeout = 5
            model_name = "test-model"

        self.config = _Config()
        self.llm_provider = FakeLLMProvider()
        self._cost_tracker = StubCostTracker()
        self.logger = logging.getLogger("test-client")
        self.cache_hits = 0
        self.cache_misses = 0
        self.api_retries = 0
        self.api_failures = 0
        self._log_metrics = log_fn


@pytest.mark.asyncio
async def test_retry_handler_retries_and_succeeds() -> None:
    side_effects: List[str | Exception] = [TimeoutError("boom"), "ok"]
    agent = FakeAgentForRetry(side_effects)
    handler = RetryHandler(cast(Any, agent))

    result = await handler.call(object(), "prompt")

    assert result == "ok"
    assert agent.client.calls == 2
    assert agent.api_retries >= 1
    assert agent.api_failures == 0
    assert agent._rate_limiter.entered >= 1
    assert agent._semaphore.entered >= 1


@pytest.mark.asyncio
async def test_gemini_client_executes_with_llm_provider() -> None:
    log_calls = []

    def _log_fn(*args: Any, **kwargs: Any) -> None:
        log_calls.append(kwargs)

    agent = FakeAgentForClient(_log_fn)
    client = GeminiClient(cast(Any, agent), _log_fn)

    result = await client.execute(object(), "hello")

    assert result == "hello-response"
    assert agent._cost_tracker.calls == [(1, 2)]
    assert log_calls[-1]["prompt_tokens"] == 1
    # ensure provider was called with prompt
    assert agent.llm_provider.calls[0][0] == "hello"
