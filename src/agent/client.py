"""Gemini API client wrapper (refactored from GeminiAgent)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from src.config.exceptions import SafetyFilterError
from src.infra.utils import safe_json_parse

if TYPE_CHECKING:
    from src.agent import GeminiAgent


class GeminiClient:
    """Thin wrapper facade for Gemini API calls.

    This class now owns the low-level API call execution logic that used to
    live inside `GeminiAgent._execute_api_call`. Public behaviour remains the
    same, but the responsibilities are separated for easier testing and future
    extension.
    """

    def __init__(
        self,
        agent: GeminiAgent,
        log_metrics_fn: Callable[..., None],
    ) -> None:
        """Initialize the Gemini client wrapper."""
        self.agent = agent
        self._log_metrics = log_metrics_fn

    async def execute(self, model: Any, prompt_text: str) -> str:
        """Execute a single Gemini API call.

        Args:
            model: Generative model instance (Gemini provider or LLM provider).
            prompt_text: User prompt text.

        Returns:
            Response text from the model.

        Raises:
            SafetyFilterError: If blocked by safety filters or unexpected finish reason.
        """
        if self.agent.llm_provider:
            return await self._execute_with_llm_provider(model, prompt_text)
        return await self._execute_with_native_model(model, prompt_text)

    async def _execute_with_llm_provider(self, model: Any, prompt_text: str) -> str:
        provider = self.agent.llm_provider
        if provider is None:
            raise SafetyFilterError("LLM provider not initialized")
        start = time.perf_counter()
        system_instruction = getattr(model, "_agent_system_instruction", None)
        response_schema = getattr(model, "_agent_response_schema", None)
        result = await provider.generate_content_async(
            prompt_text,
            system_instruction=system_instruction,
            temperature=self.agent.config.temperature,
            max_output_tokens=self.agent.config.max_output_tokens,
            response_schema=response_schema,
            request_options={"timeout": self.agent.config.timeout},
        )
        latency_ms = (time.perf_counter() - start) * 1000
        prompt_tokens = result.usage.get("prompt_tokens", 0)
        completion_tokens = result.usage.get("completion_tokens", 0)
        self.agent._cost_tracker.add_tokens(prompt_tokens, completion_tokens)  # noqa: SLF001
        self._log_metrics(
            self.agent.logger,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cache_hits=self.agent.cache_hits,
            cache_misses=self.agent.cache_misses,
            api_retries=self.agent.api_retries,
            api_failures=self.agent.api_failures,
        )
        finish_reason = result.finish_reason
        response_length = len(result.content) if result.content else 0
        self._log_finish_reason(finish_reason, response_length)
        self._warn_if_truncated(finish_reason, response_length)
        self._raise_if_unexpected_finish(finish_reason, result.safety_ratings or "")
        return result.content

    async def _execute_with_native_model(self, model: Any, prompt_text: str) -> str:
        protos = self.agent._protos()  # noqa: SLF001
        self.agent.logger.debug(
            "API Call - Model: %s, Prompt Length: %s, Timeout: %ss",
            self.agent.config.model_name,
            len(prompt_text),
            self.agent.config.timeout,
        )
        start = time.perf_counter()
        response = await model.generate_content_async(
            prompt_text,
            request_options={"timeout": self.agent.config.timeout},
        )
        latency_ms = (time.perf_counter() - start) * 1000
        self._log_latency_and_usage(response, latency_ms)
        self._validate_candidate_finish_reason(response, protos)
        return self._extract_text_or_raise(response)

    def _log_finish_reason(self, finish_reason: Any, response_length: int) -> None:
        self.agent.logger.info(
            "API Response - Finish: %s, Len: %d",
            finish_reason,
            response_length,
        )

    def _warn_if_truncated(self, finish_reason: Any, response_length: int) -> None:
        if finish_reason and str(finish_reason).upper() == "MAX_TOKENS":
            self.agent.logger.warning(
                "⚠️ Response truncated due to MAX_TOKENS limit. "
                "Response length: %d chars. Consider increasing max_output_tokens.",
                response_length,
            )

    def _raise_if_unexpected_finish(self, finish_reason: Any, safety_info: str) -> None:
        if finish_reason and str(finish_reason).upper() not in {"STOP", "MAX_TOKENS"}:
            self.agent.logger.error(
                "❌ API Response incomplete! Finish Reason: %s, Safety: %s",
                finish_reason,
                safety_info,
            )
            raise SafetyFilterError(
                "Blocked by safety filter or other reason: %s.%s"
                % (finish_reason, safety_info),
            )

    def _log_latency_and_usage(self, response: Any, latency_ms: float) -> None:
        latency_s = latency_ms / 1000
        self.agent.logger.info("API latency: %.2f ms (%.1f s)", latency_ms, latency_s)
        timeout_threshold = self.agent.config.timeout * 0.8
        if latency_s > timeout_threshold:
            self.agent.logger.warning(
                "⚠️ API request took %.1f s, approaching timeout of %d s. "
                "Consider increasing GEMINI_TIMEOUT.",
                latency_s,
                self.agent.config.timeout,
            )
        usage = getattr(response, "usage_metadata", None)
        if usage:
            self.agent._cost_tracker.add_tokens(  # noqa: SLF001
                usage.prompt_token_count,
                usage.candidates_token_count,
            )
            self.agent.logger.info(
                "Token Usage - Prompt: %s, Response: %s, Total: %s",
                usage.prompt_token_count,
                usage.candidates_token_count,
                usage.total_token_count,
            )
            self._log_metrics(
                self.agent.logger,
                latency_ms=latency_ms,
                prompt_tokens=usage.prompt_token_count,
                completion_tokens=usage.candidates_token_count,
                cache_hits=self.agent.cache_hits,
                cache_misses=self.agent.cache_misses,
                api_retries=self.agent.api_retries,
                api_failures=self.agent.api_failures,
            )

    def _validate_candidate_finish_reason(self, response: Any, protos: Any) -> None:
        if not getattr(response, "candidates", None):
            return
        candidate = response.candidates[0]
        finish_reason = candidate.finish_reason
        response_text = self._safe_response_text(response)
        response_length = len(response_text)
        self._log_finish_reason(finish_reason, response_length)
        if finish_reason == protos.Candidate.FinishReason.MAX_TOKENS:
            self._warn_if_truncated("MAX_TOKENS", response_length)
        if finish_reason not in {
            protos.Candidate.FinishReason.STOP,
            protos.Candidate.FinishReason.MAX_TOKENS,
        }:
            safety_info = ""
            prompt_feedback = getattr(response, "prompt_feedback", None)
            if prompt_feedback:
                safety_info = f" Safety Ratings: {prompt_feedback}"
            self._raise_if_unexpected_finish(finish_reason, safety_info)

    def _safe_response_text(self, response: Any) -> str:
        try:
            return str(response.text)
        except (ValueError, AttributeError):
            return ""

    def _extract_text_or_raise(self, response: Any) -> str:
        try:
            return str(response.text)
        except ValueError:
            safety_info = ""
            prompt_feedback = getattr(response, "prompt_feedback", None)
            if prompt_feedback:
                safety_info = f" Safety Filter: {prompt_feedback}"
            error_msg = f"No text content in response.{safety_info}"
            self.agent.logger.error(error_msg)
            candidates = getattr(response, "candidates", None) or []
            if candidates and candidates[0].content.parts:
                parts = candidates[0].content.parts
                if parts and hasattr(parts[0], "text"):
                    return str(parts[0].text)
            raise SafetyFilterError(error_msg)

    def parse_and_validate(self, response_text: str, key: str) -> Any:
        """Utility wrapper around safe_json_parse for callers that need it."""
        return safe_json_parse(response_text, key)
