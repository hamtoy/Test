"""Retry/backoff handler for GeminiAgent."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Dict

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config.exceptions import APIRateLimitError

if TYPE_CHECKING:
    from src.agent import GeminiAgent


class RetryHandler:
    """Isolated retry/backoff logic extracted from `GeminiAgent`."""

    def __init__(self, agent: "GeminiAgent") -> None:
        self.agent = agent

    async def call(self, model: Any, prompt: str) -> str:
        """Execute an API call with retry/backoff."""
        exceptions = self.agent._google_exceptions()  # noqa: SLF001
        retry_exceptions = (
            exceptions.ResourceExhausted,
            exceptions.ServiceUnavailable,
            exceptions.DeadlineExceeded,
            exceptions.Cancelled,
            TimeoutError,
        )

        async def _adaptive_backoff(attempt: int) -> None:
            self.agent.api_retries += 1
            delay = min(10, 2 * attempt)
            self.agent.logger.warning(
                "Retrying API call (attempt=%s, delay=%ss)", attempt, delay
            )
            await asyncio.sleep(delay)

        @retry(  # type: ignore[misc]
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(retry_exceptions),
            reraise=True,
        )
        async def _execute_with_retry() -> str:
            def _get_retry_attempt() -> int:
                """Extract attempt number from tenacity retry statistics."""
                retry_obj = getattr(_execute_with_retry, "retry", None)
                stats_dict: Dict[str, Any] = {}
                if retry_obj is not None and hasattr(retry_obj, "statistics"):
                    stats_dict = retry_obj.statistics
                return stats_dict.get("attempt_number", 1) or 1

            limiter = self.agent._rate_limiter  # noqa: SLF001
            semaphore = self.agent._semaphore  # noqa: SLF001
            if limiter:
                async with limiter, semaphore:
                    try:
                        return await self.agent.client.execute(model, prompt)
                    except retry_exceptions:
                        attempt = _get_retry_attempt()
                        await _adaptive_backoff(attempt)
                        raise
            async with semaphore:
                try:
                    return await self.agent.client.execute(model, prompt)
                except retry_exceptions:
                    attempt = _get_retry_attempt()
                    await _adaptive_backoff(attempt)
                    raise

        try:
            result: str = await _execute_with_retry()
            return result
        except Exception as exc:  # noqa: BLE001
            self.agent.api_failures += 1
            self.agent.logger.error(
                "API call failed after retries",
                extra={
                    "model": self.agent.config.model_name,
                    "error_type": exc.__class__.__name__,
                    "has_llm_provider": bool(self.agent.llm_provider),
                },
                exc_info=True,
            )
            if self.agent._is_rate_limit_error(exc):  # noqa: SLF001
                raise APIRateLimitError(
                    "Rate limit exceeded during API call: %s" % exc
                ) from exc
            raise
