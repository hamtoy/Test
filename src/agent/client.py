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
        self, agent: GeminiAgent, log_metrics_fn: Callable[..., None],
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
            start = time.perf_counter()
            system_instruction = getattr(model, "_agent_system_instruction", None)
            response_schema = getattr(model, "_agent_response_schema", None)
            result = await self.agent.llm_provider.generate_content_async(
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

            # 🔍 Enhanced logging for debugging truncated responses
            self.agent.logger.info(
                "🔍 API Response (LLM Provider) - Finish Reason: %s, Length: %d chars, "
                "Last 100 chars: ...%s",
                finish_reason,
                response_length,
                result.content[-100:] if response_length > 100 else result.content,
            )

            # Log warning if response might be truncated
            if finish_reason and finish_reason.upper() == "MAX_TOKENS":
                self.agent.logger.warning(
                    "⚠️ Response truncated due to MAX_TOKENS limit. "
                    "Response length: %d chars. Consider increasing max_output_tokens.",
                    response_length,
                )

            if finish_reason and finish_reason.upper() not in {"STOP", "MAX_TOKENS"}:
                safety_info = result.safety_ratings or ""
                self.agent.logger.error(
                    "❌ API Response incomplete! Finish Reason: %s, Safety: %s",
                    finish_reason,
                    safety_info,
                )
                raise SafetyFilterError(
                    "Blocked by safety filter or other reason: %s.%s"
                    % (finish_reason, safety_info),
                )
            return result.content

        protos = self.agent._protos()  # noqa: SLF001
        self.agent.logger.debug(
            "API Call - Model: %s, Prompt Length: %s, Timeout: %ss",
            self.agent.config.model_name,
            len(prompt_text),
            self.agent.config.timeout,
        )
        start = time.perf_counter()
        response = await model.generate_content_async(
            prompt_text, request_options={"timeout": self.agent.config.timeout},
        )
        latency_ms = (time.perf_counter() - start) * 1000
        latency_s = latency_ms / 1000

        self.agent.logger.info("API latency: %.2f ms (%.1f s)", latency_ms, latency_s)

        # Warn if request is taking close to timeout
        timeout_threshold = self.agent.config.timeout * 0.8  # 80% of timeout
        if latency_s > timeout_threshold:
            self.agent.logger.warning(
                "⚠️ API request took %.1f s, approaching timeout of %d s. "
                "Consider increasing GEMINI_TIMEOUT.",
                latency_s,
                self.agent.config.timeout,
            )

        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = response.usage_metadata
            self.agent._cost_tracker.add_tokens(  # noqa: SLF001
                usage.prompt_token_count, usage.candidates_token_count,
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

        if response.candidates:
            candidate = response.candidates[0]
            finish_reason = candidate.finish_reason

            # Get response text early for logging (may raise ValueError/AttributeError)
            # These exceptions are caught because response.text property can fail when:
            # - Safety filters block the response
            # - Response has no text content
            # - Response is still being processed
            # Note: We don't use hasattr() here because it calls the property getter,
            # and if the property raises ValueError (not AttributeError), hasattr() will
            # propagate the exception instead of returning False.
            response_text = ""
            try:
                response_text = str(response.text)
            except (ValueError, AttributeError):
                # Text unavailable - will be handled below in the main return logic
                response_text = ""

            response_length = len(response_text)

            # 🔍 Enhanced logging for debugging truncated responses
            self.agent.logger.info(
                "🔍 API Response (Gemini Native) - Finish Reason: %s, Length: %d chars, "
                "Last 100 chars: ...%s",
                finish_reason,
                response_length,
                response_text[-100:] if response_length > 100 else response_text,
            )

            # Log warning if response might be truncated
            if finish_reason == protos.Candidate.FinishReason.MAX_TOKENS:
                self.agent.logger.warning(
                    "⚠️ Response truncated due to MAX_TOKENS limit. "
                    "Response length: %d chars. Consider increasing max_output_tokens.",
                    response_length,
                )

            if finish_reason not in [
                protos.Candidate.FinishReason.STOP,
                protos.Candidate.FinishReason.MAX_TOKENS,
            ]:
                safety_info = ""
                if hasattr(response, "prompt_feedback") and response.prompt_feedback:
                    safety_info = " Safety Ratings: %s" % response.prompt_feedback

                self.agent.logger.error(
                    "❌ API Response incomplete! Finish Reason: %s, Safety: %s",
                    finish_reason,
                    safety_info,
                )
                raise SafetyFilterError(
                    "Blocked by safety filter or other reason: %s.%s"
                    % (finish_reason, safety_info),
                )

        try:
            return str(response.text)
        except ValueError:
            safety_info = ""
            if hasattr(response, "prompt_feedback") and response.prompt_feedback:
                safety_info = " Safety Filter: %s" % response.prompt_feedback

            error_msg = "No text content in response.%s" % safety_info
            self.agent.logger.error(error_msg)

            if response.candidates and response.candidates[0].content.parts:
                parts = response.candidates[0].content.parts
                if len(parts) > 0 and hasattr(parts[0], "text"):
                    return str(parts[0].text)

            raise SafetyFilterError(error_msg)

    async def parse_and_validate(self, response_text: str, key: str) -> Any:
        """Utility wrapper around safe_json_parse for callers that need it."""
        return safe_json_parse(response_text, key)
