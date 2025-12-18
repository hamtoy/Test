"""Tests for src/llm/genai_client.py - GenAIClient wrapper."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.genai import types
from pydantic import BaseModel

from src.llm.genai_client import GenAIClient, get_genai_client

if TYPE_CHECKING:
    pass


class SampleResponseSchema(BaseModel):
    """Sample Pydantic model for testing response schema."""

    content: str
    score: int


class TestGenAIClientInit:
    """Tests for GenAIClient initialization."""

    def test_init_with_config(self) -> None:
        """Test initialization with config."""
        mock_config = MagicMock()
        mock_config.api_key = "test-api-key"

        with patch("src.llm.genai_client.genai.Client") as mock_client_class:
            client = GenAIClient(config=mock_config)
            mock_client_class.assert_called_once_with(api_key="test-api-key")
            assert client.config == mock_config

    def test_init_without_config_uses_env(self) -> None:
        """Test initialization without config uses environment variable."""
        with (
            patch("src.llm.genai_client.genai.Client") as mock_client_class,
            patch.dict("os.environ", {"GEMINI_API_KEY": "env-api-key"}),
        ):
            client = GenAIClient(config=None)
            mock_client_class.assert_called_once_with(api_key="env-api-key")
            assert client.config is None


class TestGenAIClientGenerateContent:
    """Tests for GenAIClient.generate_content method."""

    @pytest.fixture
    def mock_client(self) -> GenAIClient:
        """Create a GenAIClient with mocked dependencies."""
        with patch("src.llm.genai_client.genai.Client"):
            mock_config = MagicMock()
            mock_config.api_key = "test-key"
            return GenAIClient(config=mock_config)

    @pytest.mark.asyncio
    async def test_generate_content_basic(self, mock_client: GenAIClient) -> None:
        """Test basic content generation."""
        mock_response = MagicMock(spec=types.GenerateContentResponse)
        mock_client.client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        response = await mock_client.generate_content(
            model="gemini-2.0-flash",
            contents="Hello, world!",
        )

        assert response == mock_response
        mock_client.client.aio.models.generate_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_content_with_system_instruction(
        self, mock_client: GenAIClient
    ) -> None:
        """Test content generation with system instruction."""
        mock_response = MagicMock(spec=types.GenerateContentResponse)
        mock_client.client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        await mock_client.generate_content(
            model="gemini-2.0-flash",
            contents="Test prompt",
            system_instruction="You are a helpful assistant",
        )

        call_args = mock_client.client.aio.models.generate_content.call_args
        config = call_args.kwargs["config"]
        assert config.system_instruction == "You are a helpful assistant"

    @pytest.mark.asyncio
    async def test_generate_content_with_response_schema(
        self, mock_client: GenAIClient
    ) -> None:
        """Test content generation with response schema."""
        mock_response = MagicMock(spec=types.GenerateContentResponse)
        mock_client.client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        await mock_client.generate_content(
            model="gemini-2.0-flash",
            contents="Test prompt",
            response_schema=SampleResponseSchema,
        )

        call_args = mock_client.client.aio.models.generate_content.call_args
        config = call_args.kwargs["config"]
        assert config.response_mime_type == "application/json"
        assert config.response_schema == SampleResponseSchema

    @pytest.mark.asyncio
    async def test_generate_content_with_thinking_config(
        self, mock_client: GenAIClient
    ) -> None:
        """Test content generation with thinking config."""
        mock_response = MagicMock(spec=types.GenerateContentResponse)
        mock_client.client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        # Create thinking config using the client's helper method
        thinking_config = mock_client.create_thinking_config(thinking_level="MEDIUM")
        await mock_client.generate_content(
            model="gemini-2.5-flash",
            contents="Test prompt",
            thinking_config=thinking_config,
        )

        call_args = mock_client.client.aio.models.generate_content.call_args
        config = call_args.kwargs["config"]
        assert config.thinking_config == thinking_config

    @pytest.mark.asyncio
    async def test_generate_content_with_safety_settings(
        self, mock_client: GenAIClient
    ) -> None:
        """Test content generation with safety settings."""
        mock_response = MagicMock(spec=types.GenerateContentResponse)
        mock_client.client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        safety_settings = [
            types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"
            )
        ]
        await mock_client.generate_content(
            model="gemini-2.0-flash",
            contents="Test prompt",
            safety_settings=safety_settings,
        )

        call_args = mock_client.client.aio.models.generate_content.call_args
        config = call_args.kwargs["config"]
        assert config.safety_settings == safety_settings

    @pytest.mark.asyncio
    async def test_generate_content_with_cached_content(
        self, mock_client: GenAIClient
    ) -> None:
        """Test content generation with cached content."""
        mock_response = MagicMock(spec=types.GenerateContentResponse)
        mock_client.client.aio.models.generate_content = AsyncMock(
            return_value=mock_response
        )

        await mock_client.generate_content(
            model="gemini-2.0-flash",
            contents="Test prompt",
            cached_content="cached-content-name",
        )

        call_args = mock_client.client.aio.models.generate_content.call_args
        config = call_args.kwargs["config"]
        assert config.cached_content == "cached-content-name"


class TestGenAIClientGenerateContentStream:
    """Tests for GenAIClient.generate_content_stream method."""

    @pytest.fixture
    def mock_client(self) -> GenAIClient:
        """Create a GenAIClient with mocked dependencies."""
        with patch("src.llm.genai_client.genai.Client"):
            mock_config = MagicMock()
            mock_config.api_key = "test-key"
            return GenAIClient(config=mock_config)

    @pytest.mark.asyncio
    async def test_generate_content_stream_basic(
        self, mock_client: GenAIClient
    ) -> None:
        """Test basic streaming content generation."""
        mock_chunks = [MagicMock(), MagicMock(), MagicMock()]

        async def mock_stream(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[MagicMock, None]:
            for chunk in mock_chunks:
                yield chunk

        mock_client.client.aio.models.generate_content_stream = mock_stream

        chunks = [
            chunk
            async for chunk in mock_client.generate_content_stream(
                model="gemini-2.0-flash",
                contents="Hello, world!",
            )
        ]

        assert len(chunks) == 3

    @pytest.mark.asyncio
    async def test_generate_content_stream_with_system_instruction(
        self, mock_client: GenAIClient
    ) -> None:
        """Test streaming with system instruction."""
        call_kwargs: dict[str, Any] = {}

        async def mock_stream(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[MagicMock, None]:
            call_kwargs.update(kwargs)
            yield MagicMock()

        mock_client.client.aio.models.generate_content_stream = mock_stream

        async for _ in mock_client.generate_content_stream(
            model="gemini-2.0-flash",
            contents="Test prompt",
            system_instruction="Be helpful",
        ):
            pass

        assert call_kwargs["config"].system_instruction == "Be helpful"


class TestGenAIClientThinkingConfig:
    """Tests for GenAIClient.create_thinking_config method."""

    def test_create_thinking_config_medium(self) -> None:
        """Test creating thinking config with medium level."""
        with patch("src.llm.genai_client.genai.Client"):
            client = GenAIClient(config=None)
            config = client.create_thinking_config(thinking_level="MEDIUM")
            assert hasattr(config, "thinking_level")

    def test_create_thinking_config_high(self) -> None:
        """Test creating thinking config with high level."""
        with patch("src.llm.genai_client.genai.Client"):
            client = GenAIClient(config=None)
            config = client.create_thinking_config(thinking_level="HIGH")
            assert hasattr(config, "thinking_level")

    def test_create_thinking_config_default(self) -> None:
        """Test default thinking config level."""
        with patch("src.llm.genai_client.genai.Client"):
            client = GenAIClient(config=None)
            config = client.create_thinking_config()
            assert hasattr(config, "thinking_level")

    def test_create_thinking_config_invalid_level(self) -> None:
        """Test creating thinking config with invalid level falls back."""
        with patch("src.llm.genai_client.genai.Client"):
            client = GenAIClient(config=None)
            config = client.create_thinking_config(thinking_level="INVALID")
            assert hasattr(config, "thinking_level")


class TestGenAIClientSafetySettings:
    """Tests for GenAIClient.create_safety_settings method."""

    def test_create_safety_settings(self) -> None:
        """Test creating default safety settings."""
        with patch("src.llm.genai_client.genai.Client"):
            client = GenAIClient(config=None)
            settings = client.create_safety_settings()

            assert len(settings) == 4
            categories = [s.category for s in settings]
            assert "HARM_CATEGORY_HARASSMENT" in categories
            assert "HARM_CATEGORY_HATE_SPEECH" in categories
            assert "HARM_CATEGORY_SEXUALLY_EXPLICIT" in categories
            assert "HARM_CATEGORY_DANGEROUS_CONTENT" in categories

            for setting in settings:
                assert setting.threshold == "BLOCK_NONE"


class TestGetGenAIClientSingleton:
    """Tests for get_genai_client singleton function."""

    def test_get_genai_client_singleton(self) -> None:
        """Test that get_genai_client returns singleton."""
        import src.llm.genai_client as module

        # Reset singleton
        module._client = None

        with patch("src.llm.genai_client.genai.Client"):
            client1 = get_genai_client()
            client2 = get_genai_client()
            assert client1 is client2

        # Cleanup
        module._client = None

    def test_get_genai_client_with_config(self) -> None:
        """Test get_genai_client with config argument."""
        import src.llm.genai_client as module

        # Reset singleton
        module._client = None

        mock_config = MagicMock()
        mock_config.api_key = "test-key"

        with patch("src.llm.genai_client.genai.Client"):
            client = get_genai_client(config=mock_config)
            assert client.config == mock_config

        # Cleanup
        module._client = None
