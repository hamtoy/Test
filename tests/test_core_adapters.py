"""Tests for the core adapters module."""

from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.interfaces import (
    ContextWindowExceededError,
    GenerationResult,
    ProviderError,
    RateLimitError,
    SafetyBlockedError,
    TimeoutError,
)


class TestGeminiProvider:
    """Tests for GeminiProvider class."""

    @pytest.fixture
    def mock_genai(self) -> Generator[MagicMock, None, None]:
        """Create a mock genai module."""
        with patch("src.core.adapters.genai") as mock:
            mock.GenerativeModel = MagicMock()
            mock.configure = MagicMock()
            yield mock

    @pytest.fixture
    def provider(self, mock_genai: MagicMock) -> Any:
        """Create a GeminiProvider instance."""
        from src.core.adapters import GeminiProvider

        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model

        return GeminiProvider(api_key="test-api-key", model_name="gemini-1.5-pro")

    def test_init(self, mock_genai: MagicMock) -> None:
        """Test GeminiProvider initialization."""
        from src.core.adapters import GeminiProvider

        provider = GeminiProvider(api_key="test-key", model_name="gemini-1.5-pro")

        mock_genai.configure.assert_called_once_with(api_key="test-key")
        mock_genai.GenerativeModel.assert_called_once_with("gemini-1.5-pro")
        assert provider.model_name == "gemini-1.5-pro"

    @pytest.mark.asyncio
    async def test_generate_content_basic(
        self, provider: Any, mock_genai: MagicMock
    ) -> None:
        """Test basic content generation."""
        # Create finish_reason mock properly
        finish_reason = MagicMock()
        finish_reason.name = "STOP"

        candidate = MagicMock()
        candidate.finish_reason = finish_reason

        mock_response = MagicMock()
        mock_response.text = "Generated text"
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=10,
            candidates_token_count=20,
            total_token_count=30,
        )
        mock_response.candidates = [candidate]

        provider._model.generate_content_async = AsyncMock(return_value=mock_response)

        result = await provider.generate_content_async("Test prompt")

        assert isinstance(result, GenerationResult)
        assert result.content == "Generated text"
        assert result.usage["prompt_tokens"] == 10
        assert result.finish_reason == "STOP"

    @pytest.mark.asyncio
    async def test_generate_content_with_system_instruction(
        self, provider: Any, mock_genai: MagicMock
    ) -> None:
        """Test content generation with system instruction."""
        # Create finish_reason mock properly
        finish_reason = MagicMock()
        finish_reason.name = "STOP"

        candidate = MagicMock()
        candidate.finish_reason = finish_reason

        mock_response = MagicMock()
        mock_response.text = "Generated text"
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=10,
            candidates_token_count=20,
            total_token_count=30,
        )
        mock_response.candidates = [candidate]

        # Create a new model with system instruction
        mock_model_with_system = MagicMock()
        mock_model_with_system.generate_content_async = AsyncMock(
            return_value=mock_response
        )
        mock_genai.GenerativeModel.return_value = mock_model_with_system

        result = await provider.generate_content_async(
            "Test prompt",
            system_instruction="Be helpful",
        )

        assert result.content == "Generated text"
        # Verify new model was created with system instruction
        mock_genai.GenerativeModel.assert_called_with(
            provider.model_name, system_instruction="Be helpful"
        )

    @pytest.mark.asyncio
    async def test_generate_content_with_config(
        self, provider: Any, mock_genai: MagicMock
    ) -> None:
        """Test content generation with configuration options."""
        # Create finish_reason mock properly
        finish_reason = MagicMock()
        finish_reason.name = "STOP"

        candidate = MagicMock()
        candidate.finish_reason = finish_reason

        mock_response = MagicMock()
        mock_response.text = "Generated text"
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=10,
            candidates_token_count=20,
            total_token_count=30,
        )
        mock_response.candidates = [candidate]

        provider._model.generate_content_async = AsyncMock(return_value=mock_response)

        result = await provider.generate_content_async(
            "Test prompt",
            temperature=0.7,
            max_output_tokens=1000,
        )

        assert result.content == "Generated text"
        # Verify config was passed
        call_args = provider._model.generate_content_async.call_args
        assert call_args.kwargs["generation_config"]["temperature"] == 0.7
        assert call_args.kwargs["generation_config"]["max_output_tokens"] == 1000

    @pytest.mark.asyncio
    async def test_generate_content_with_response_schema(
        self, provider: Any, mock_genai: MagicMock
    ) -> None:
        """Test content generation with response schema."""
        # Create finish_reason mock properly
        finish_reason = MagicMock()
        finish_reason.name = "STOP"

        candidate = MagicMock()
        candidate.finish_reason = finish_reason

        mock_response = MagicMock()
        mock_response.text = '{"key": "value"}'
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=10,
            candidates_token_count=20,
            total_token_count=30,
        )
        mock_response.candidates = [candidate]

        provider._model.generate_content_async = AsyncMock(return_value=mock_response)

        schema = {"type": "object", "properties": {"key": {"type": "string"}}}
        await provider.generate_content_async("Test", response_schema=schema)

        call_args = provider._model.generate_content_async.call_args
        assert (
            call_args.kwargs["generation_config"]["response_mime_type"]
            == "application/json"
        )
        assert call_args.kwargs["generation_config"]["response_schema"] == schema

    @pytest.mark.asyncio
    async def test_generate_content_safety_blocked(self, provider: Any) -> None:
        """Test handling of safety blocked responses."""
        mock_response = MagicMock()
        mock_response.text = ""
        mock_response.candidates = [MagicMock(finish_reason=MagicMock(name="SAFETY"))]
        mock_response.prompt_feedback = "Blocked due to safety"

        provider._model.generate_content_async = AsyncMock(return_value=mock_response)

        with pytest.raises(SafetyBlockedError):
            await provider.generate_content_async("Test prompt")

    @pytest.mark.asyncio
    async def test_generate_content_rate_limit(self, provider: Any) -> None:
        """Test handling of rate limit errors."""
        from google.api_core import exceptions as google_exceptions

        provider._model.generate_content_async = AsyncMock(
            side_effect=google_exceptions.ResourceExhausted("Rate limited")  # type: ignore[no-untyped-call]
        )

        with pytest.raises(RateLimitError):
            await provider.generate_content_async("Test prompt")

    @pytest.mark.asyncio
    async def test_generate_content_context_exceeded(self, provider: Any) -> None:
        """Test handling of context window exceeded errors."""
        from google.api_core import exceptions as google_exceptions

        provider._model.generate_content_async = AsyncMock(
            side_effect=google_exceptions.InvalidArgument("token limit exceeded")  # type: ignore[no-untyped-call]
        )

        with pytest.raises(ContextWindowExceededError):
            await provider.generate_content_async("Test prompt")

    @pytest.mark.asyncio
    async def test_generate_content_invalid_argument(self, provider: Any) -> None:
        """Test handling of other invalid argument errors."""
        from google.api_core import exceptions as google_exceptions

        provider._model.generate_content_async = AsyncMock(
            side_effect=google_exceptions.InvalidArgument("Invalid parameter")  # type: ignore[no-untyped-call]
        )

        with pytest.raises(ProviderError):
            await provider.generate_content_async("Test prompt")

    @pytest.mark.asyncio
    async def test_generate_content_timeout(self, provider: Any) -> None:
        """Test handling of timeout errors."""
        from google.api_core import exceptions as google_exceptions

        provider._model.generate_content_async = AsyncMock(
            side_effect=google_exceptions.DeadlineExceeded("Timeout")  # type: ignore[no-untyped-call]
        )

        with pytest.raises(TimeoutError):
            await provider.generate_content_async("Test prompt")

    @pytest.mark.asyncio
    async def test_generate_content_generic_error(self, provider: Any) -> None:
        """Test handling of generic errors."""
        provider._model.generate_content_async = AsyncMock(
            side_effect=Exception("Unknown error")
        )

        with pytest.raises(ProviderError):
            await provider.generate_content_async("Test prompt")

    @pytest.mark.asyncio
    async def test_count_tokens(self, provider: Any) -> None:
        """Test token counting."""
        mock_count = MagicMock()
        mock_count.total_tokens = 100
        provider._model.count_tokens = MagicMock(return_value=mock_count)

        result = await provider.count_tokens("Test text")

        assert result == 100
        provider._model.count_tokens.assert_called_once_with("Test text")

    @pytest.mark.asyncio
    async def test_count_tokens_error(self, provider: Any) -> None:
        """Test token counting error handling."""
        provider._model.count_tokens = MagicMock(side_effect=Exception("Count failed"))

        with pytest.raises(ProviderError):
            await provider.count_tokens("Test text")


class TestNeo4jProvider:
    """Tests for Neo4jProvider class."""

    @pytest.fixture
    def mock_driver(self) -> Generator[MagicMock, None, None]:
        """Create a mock Neo4j driver."""
        with patch("src.core.adapters.AsyncGraphDatabase") as mock_db:
            mock_driver = MagicMock()
            mock_db.driver.return_value = mock_driver
            yield mock_driver

    @pytest.fixture
    def provider(self, mock_driver: Any) -> Any:
        """Create a Neo4jProvider instance."""
        from src.core.adapters import Neo4jProvider

        return Neo4jProvider(
            uri="bolt://localhost:7687",
            auth=("neo4j", "password"),
        )

    @pytest.mark.asyncio
    async def test_close(self, provider: Any, mock_driver: Any) -> None:
        """Test closing the driver."""
        mock_driver.close = AsyncMock()

        await provider.close()

        mock_driver.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_connectivity_success(
        self, provider: Any, mock_driver: Any
    ) -> None:
        """Test successful connectivity verification."""
        mock_driver.verify_connectivity = AsyncMock()

        await provider.verify_connectivity()

        mock_driver.verify_connectivity.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_connectivity_failure(
        self, provider: Any, mock_driver: Any
    ) -> None:
        """Test connectivity verification failure."""
        mock_driver.verify_connectivity = AsyncMock(
            side_effect=Exception("Connection failed")
        )

        with pytest.raises(ProviderError):
            await provider.verify_connectivity()

    @pytest.mark.asyncio
    async def test_create_nodes_empty_list(self, provider: Any) -> None:
        """Test creating nodes with empty list."""
        result = await provider.create_nodes([], "TestLabel")
        assert result == 0

    @pytest.mark.asyncio
    async def test_create_nodes_batch(self, provider: Any, mock_driver: Any) -> None:
        """Test creating nodes in batches."""
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value={"count": 3})
        mock_session.run = AsyncMock(return_value=mock_result)

        async_context = AsyncMock()
        async_context.__aenter__ = AsyncMock(return_value=mock_session)
        async_context.__aexit__ = AsyncMock(return_value=None)
        mock_driver.session.return_value = async_context

        nodes = [
            {"id": "1", "name": "Node1", "value": 10},
            {"id": "2", "name": "Node2", "value": 20},
            {"id": "3", "name": "Node3", "value": 30},
        ]

        result = await provider.create_nodes(nodes, "TestLabel")

        assert result == 3
        mock_session.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_relationships_empty_list(self, provider: Any) -> None:
        """Test creating relationships with empty list."""
        result = await provider.create_relationships([], "RELATES_TO", "From", "To")
        assert result == 0

    @pytest.mark.asyncio
    async def test_create_relationships_batch(
        self, provider: Any, mock_driver: Any
    ) -> None:
        """Test creating relationships in batches."""
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value={"count": 2})
        mock_session.run = AsyncMock(return_value=mock_result)

        async_context = AsyncMock()
        async_context.__aenter__ = AsyncMock(return_value=mock_session)
        async_context.__aexit__ = AsyncMock(return_value=None)
        mock_driver.session.return_value = async_context

        rels = [
            {"from_id": "1", "to_id": "2", "weight": 0.5},
            {"from_id": "2", "to_id": "3", "weight": 0.7},
        ]

        result = await provider.create_relationships(rels, "CONNECTS", "Node", "Node")

        assert result == 2
        mock_session.run.assert_called_once()
