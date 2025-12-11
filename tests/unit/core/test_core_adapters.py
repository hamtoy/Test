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
    def graph_provider(self) -> Generator[tuple[MagicMock, MagicMock], None, None]:
        """Patch Neo4jGraphProvider and provide a mock instance."""
        with patch("src.core.adapters.Neo4jGraphProvider") as provider_cls:
            delegate = MagicMock()
            delegate.close = AsyncMock()
            delegate.verify_connectivity = AsyncMock()
            delegate.create_nodes = AsyncMock(return_value=0)
            delegate.create_relationships = AsyncMock(return_value=0)
            delegate.session = MagicMock(return_value="session_ctx")
            provider_cls.return_value = delegate
            yield provider_cls, delegate

    def test_init_uses_infra_provider(
        self, graph_provider: tuple[MagicMock, MagicMock]
    ) -> None:
        """Neo4jProvider wires credentials into Neo4jGraphProvider."""
        provider_cls, _ = graph_provider
        from src.core.adapters import Neo4jProvider

        Neo4jProvider(
            uri="bolt://localhost:7687",
            auth=("neo4j", "password"),
            batch_size=50,
        )

        provider_cls.assert_called_once_with(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password",
            batch_size=50,
        )

    def test_session_delegates(
        self, graph_provider: tuple[MagicMock, MagicMock]
    ) -> None:
        """Session delegates to the underlying provider."""
        provider_cls, delegate = graph_provider
        from src.core.adapters import Neo4jProvider

        provider = Neo4jProvider(uri="bolt://localhost:7687", auth=("neo4j", "pw"))
        result = provider.session()

        assert result == "session_ctx"
        delegate.session.assert_called_once()
        provider_cls.assert_called_once()

    @pytest.mark.asyncio
    async def test_close(self, graph_provider: tuple[MagicMock, MagicMock]) -> None:
        """Close delegates to the underlying provider."""
        provider_cls, delegate = graph_provider
        from src.core.adapters import Neo4jProvider

        provider = Neo4jProvider(uri="bolt://localhost:7687", auth=("neo4j", "pw"))
        await provider.close()

        delegate.close.assert_called_once()
        provider_cls.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_connectivity_success(
        self, graph_provider: tuple[MagicMock, MagicMock]
    ) -> None:
        """Successful verify_connectivity passes through."""
        provider_cls, delegate = graph_provider
        from src.core.adapters import Neo4jProvider

        provider = Neo4jProvider(uri="bolt://localhost:7687", auth=("neo4j", "pw"))
        await provider.verify_connectivity()

        delegate.verify_connectivity.assert_called_once()
        provider_cls.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_connectivity_failure(
        self, graph_provider: tuple[MagicMock, MagicMock]
    ) -> None:
        """Connectivity errors are wrapped in ProviderError."""
        provider_cls, delegate = graph_provider
        delegate.verify_connectivity = AsyncMock(
            side_effect=Exception("Connection failed")
        )
        from src.core.adapters import Neo4jProvider

        provider = Neo4jProvider(uri="bolt://localhost:7687", auth=("neo4j", "pw"))

        with pytest.raises(ProviderError):
            await provider.verify_connectivity()

        delegate.verify_connectivity.assert_called_once()
        provider_cls.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_nodes_delegates(
        self, graph_provider: tuple[MagicMock, MagicMock]
    ) -> None:
        """create_nodes delegates to shared provider."""
        provider_cls, delegate = graph_provider
        delegate.create_nodes = AsyncMock(return_value=3)
        from src.core.adapters import Neo4jProvider

        provider = Neo4jProvider(uri="bolt://localhost:7687", auth=("neo4j", "pw"))
        nodes = [{"id": "1"}]

        result = await provider.create_nodes(
            nodes, "TestLabel", merge_on="id", merge_keys=["email"]
        )

        assert result == 3
        delegate.create_nodes.assert_called_once_with(
            nodes, "TestLabel", "id", ["email"]
        )
        provider_cls.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_relationships_delegates(
        self, graph_provider: tuple[MagicMock, MagicMock]
    ) -> None:
        """create_relationships delegates to shared provider."""
        provider_cls, delegate = graph_provider
        delegate.create_relationships = AsyncMock(return_value=2)
        from src.core.adapters import Neo4jProvider

        provider = Neo4jProvider(uri="bolt://localhost:7687", auth=("neo4j", "pw"))
        rels = [{"from_id": "1", "to_id": "2"}]

        result = await provider.create_relationships(
            rels,
            "CONNECTS",
            "From",
            "To",
            from_key="id",
            to_key="id",
        )

        assert result == 2
        delegate.create_relationships.assert_called_once_with(
            rels, "CONNECTS", "From", "To", "id", "id"
        )
        provider_cls.assert_called_once()
