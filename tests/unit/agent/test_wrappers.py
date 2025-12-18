"""Tests for src/agent/wrappers.py - GenAIModelAdapter."""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from google.genai import types
from pydantic import BaseModel

from src.agent.wrappers import GenAIModelAdapter


class SampleResponseSchema(BaseModel):
    """Sample response schema."""

    result: str


class TestGenAIModelAdapterInit:
    """Tests for GenAIModelAdapter initialization."""

    def test_init_basic(self) -> None:
        """Test basic initialization with required parameters."""
        mock_client = MagicMock()
        adapter = GenAIModelAdapter(
            client=mock_client,
            model_name="gemini-2.0-flash",
        )

        assert adapter.client == mock_client
        assert adapter.model_name == "gemini-2.0-flash"
        assert adapter.system_instruction is None
        assert adapter.generation_config == {}
        assert adapter.safety_settings is None
        assert adapter.cached_content is None

    def test_init_with_system_instruction(self) -> None:
        """Test initialization with system instruction."""
        mock_client = MagicMock()
        adapter = GenAIModelAdapter(
            client=mock_client,
            model_name="gemini-2.0-flash",
            system_instruction="Be helpful",
        )

        assert adapter.system_instruction == "Be helpful"

    def test_init_with_generation_config(self) -> None:
        """Test initialization with generation config."""
        mock_client = MagicMock()
        gen_config = {"temperature": 0.7, "top_p": 0.9}
        adapter = GenAIModelAdapter(
            client=mock_client,
            model_name="gemini-2.0-flash",
            generation_config=gen_config,
        )

        assert adapter.generation_config == gen_config

    def test_init_with_safety_settings(self) -> None:
        """Test initialization with safety settings."""
        mock_client = MagicMock()
        safety = cast(list[types.SafetySetting], [MagicMock(spec=types.SafetySetting)])
        adapter = GenAIModelAdapter(
            client=mock_client,
            model_name="gemini-2.0-flash",
            safety_settings=safety,
        )

        assert adapter.safety_settings == safety

    def test_init_with_cached_content(self) -> None:
        """Test initialization with cached content."""
        mock_client = MagicMock()
        adapter = GenAIModelAdapter(
            client=mock_client,
            model_name="gemini-2.0-flash",
            cached_content="cache-name",
        )

        assert adapter.cached_content == "cache-name"

    def test_init_with_agent_specific_properties(self) -> None:
        """Test initialization with agent-specific properties."""
        mock_client = MagicMock()
        adapter = GenAIModelAdapter(
            client=mock_client,
            model_name="gemini-2.0-flash",
            agent_system_instruction="Agent instruction",
            agent_response_schema=SampleResponseSchema,
            agent_max_output_tokens=500,
        )

        assert adapter._agent_system_instruction == "Agent instruction"
        assert adapter._agent_response_schema == SampleResponseSchema
        assert adapter._agent_max_output_tokens == 500


class TestGenAIModelAdapterGenerateContentAsync:
    """Tests for GenAIModelAdapter.generate_content_async method."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create a mock genai client."""
        client = MagicMock()
        client.aio.models.generate_content = AsyncMock(return_value=MagicMock())
        return client

    @pytest.mark.asyncio
    async def test_generate_content_basic(self, mock_client: MagicMock) -> None:
        """Test basic content generation."""
        adapter = GenAIModelAdapter(
            client=mock_client,
            model_name="gemini-2.0-flash",
        )

        _ = await adapter.generate_content_async("Hello world")

        mock_client.aio.models.generate_content.assert_called_once()
        call_args = mock_client.aio.models.generate_content.call_args
        assert call_args.kwargs["model"] == "gemini-2.0-flash"
        assert call_args.kwargs["contents"] == "Hello world"

    @pytest.mark.asyncio
    async def test_generate_content_with_system_instruction(
        self, mock_client: MagicMock
    ) -> None:
        """Test generation with system instruction."""
        adapter = GenAIModelAdapter(
            client=mock_client,
            model_name="gemini-2.0-flash",
            system_instruction="Be helpful",
        )

        await adapter.generate_content_async("Test prompt")

        call_args = mock_client.aio.models.generate_content.call_args
        config = call_args.kwargs["config"]
        assert config.system_instruction == "Be helpful"

    @pytest.mark.asyncio
    async def test_generate_content_with_safety_settings(
        self, mock_client: MagicMock
    ) -> None:
        """Test generation with safety settings."""
        safety = cast(list[types.SafetySetting], [MagicMock(spec=types.SafetySetting)])
        adapter = GenAIModelAdapter(
            client=mock_client,
            model_name="gemini-2.0-flash",
            safety_settings=safety,
        )

        await adapter.generate_content_async("Test prompt")

        call_args = mock_client.aio.models.generate_content.call_args
        config = call_args.kwargs["config"]
        assert config.safety_settings == safety

    @pytest.mark.asyncio
    async def test_generate_content_with_cached_content(
        self, mock_client: MagicMock
    ) -> None:
        """Test generation with cached content."""
        adapter = GenAIModelAdapter(
            client=mock_client,
            model_name="gemini-2.0-flash",
            cached_content="cache-name",
        )

        await adapter.generate_content_async("Test prompt")

        call_args = mock_client.aio.models.generate_content.call_args
        config = call_args.kwargs["config"]
        assert config.cached_content == "cache-name"

    @pytest.mark.asyncio
    async def test_generate_content_with_agent_max_tokens(
        self, mock_client: MagicMock
    ) -> None:
        """Test generation with agent max output tokens override."""
        adapter = GenAIModelAdapter(
            client=mock_client,
            model_name="gemini-2.0-flash",
            agent_max_output_tokens=1000,
        )

        await adapter.generate_content_async("Test prompt")

        call_args = mock_client.aio.models.generate_content.call_args
        config = call_args.kwargs["config"]
        assert config.max_output_tokens == 1000

    @pytest.mark.asyncio
    async def test_generate_content_with_agent_response_schema(
        self, mock_client: MagicMock
    ) -> None:
        """Test generation with agent response schema."""
        adapter = GenAIModelAdapter(
            client=mock_client,
            model_name="gemini-2.0-flash",
            agent_response_schema=SampleResponseSchema,
        )

        await adapter.generate_content_async("Test prompt")

        call_args = mock_client.aio.models.generate_content.call_args
        config = call_args.kwargs["config"]
        assert config.response_mime_type == "application/json"
        assert config.response_schema == SampleResponseSchema

    @pytest.mark.asyncio
    async def test_generate_content_inherits_generation_config(
        self, mock_client: MagicMock
    ) -> None:
        """Test generation inherits generation config."""
        gen_config = {"temperature": 0.5, "top_k": 40}
        adapter = GenAIModelAdapter(
            client=mock_client,
            model_name="gemini-2.0-flash",
            generation_config=gen_config,
        )

        await adapter.generate_content_async("Test prompt")

        call_args = mock_client.aio.models.generate_content.call_args
        config = call_args.kwargs["config"]
        assert config.temperature == 0.5
        assert config.top_k == 40

    @pytest.mark.asyncio
    async def test_generate_content_with_list_contents(
        self, mock_client: MagicMock
    ) -> None:
        """Test generation with list contents."""
        adapter = GenAIModelAdapter(
            client=mock_client,
            model_name="gemini-2.0-flash",
        )

        contents = ["Part 1", "Part 2"]
        await adapter.generate_content_async(contents)

        call_args = mock_client.aio.models.generate_content.call_args
        assert call_args.kwargs["contents"] == contents

    @pytest.mark.asyncio
    async def test_generate_content_ignores_request_options(
        self, mock_client: MagicMock
    ) -> None:
        """Test that _request_options is accepted but unused."""
        adapter = GenAIModelAdapter(
            client=mock_client,
            model_name="gemini-2.0-flash",
        )

        # Should not raise
        await adapter.generate_content_async(
            "Test prompt",
            _request_options={"timeout": 30},
        )

        mock_client.aio.models.generate_content.assert_called_once()
