"""Adapters for google-genai SDK to maintain compatibility with legacy GenerativeModel interface."""

from __future__ import annotations

from typing import Any

from google import genai
from google.genai import types
from pydantic import BaseModel


class GenAIModelAdapter:
    """Legacy GenerativeModel adapter using new google-genai SDK Client.

    This acts as a bridge between the old 'GenerativeModel' interface expected by
    GeminiClient and the new 'genai.Client' from google-genai SDK.
    """

    def __init__(
        self,
        client: genai.Client,
        model_name: str,
        system_instruction: str | None = None,
        generation_config: dict[str, Any] | None = None,
        safety_settings: list[genai.types.SafetySetting] | None = None,
        cached_content: str | None = None,
        agent_system_instruction: str | None = None,
        agent_response_schema: type[BaseModel] | None = None,
        agent_max_output_tokens: int | None = None,
    ) -> None:
        """Initialize the GenAIModelAdapter.

        Args:
            client: The google-genai Client instance.
            model_name: The name of the model to use.
            system_instruction: Global system instruction.
            generation_config: Configuration for generation (temp, top_p, etc).
            safety_settings: Safety settings for the model.
            cached_content: Name of cached content to reuse.
            agent_system_instruction: Agent-specific system instruction override.
            agent_response_schema: Function calling/Structured output schema.
            agent_max_output_tokens: Max tokens override.
        """
        self.client = client
        self.model_name = model_name
        self.system_instruction = system_instruction
        self.generation_config = generation_config or {}
        self.safety_settings = safety_settings
        self.cached_content = cached_content

        # Agent specific properties that were monkey-patched on the old model
        self._agent_system_instruction = agent_system_instruction
        self._agent_response_schema = agent_response_schema
        self._agent_max_output_tokens = agent_max_output_tokens

    async def generate_content_async(
        self,
        contents: str | list[Any],
        request_options: dict[str, Any] | None = None,
    ) -> Any:
        """Mimics GenerativeModel.generate_content_async."""
        config_kwargs = self.generation_config.copy()

        if self.system_instruction:
            config_kwargs["system_instruction"] = self.system_instruction

        if self.safety_settings:
            config_kwargs["safety_settings"] = self.safety_settings

        if self.cached_content:
            config_kwargs["cached_content"] = self.cached_content

        # Handle max_output_tokens override from agent
        if self._agent_max_output_tokens is not None:
            config_kwargs["max_output_tokens"] = self._agent_max_output_tokens

        # Handle response schema override from agent
        if self._agent_response_schema:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = self._agent_response_schema

        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=types.GenerateContentConfig(**config_kwargs),
        )
        return response
