import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.core.interfaces import GenerationResult, SafetyBlockedError
from src.core.adapters import GeminiProvider
from src.core.factory import get_llm_provider, get_graph_provider
from src.config import AppConfig


@pytest.fixture
def mock_genai_model():
    with patch("google.generativeai.GenerativeModel") as mock:
        yield mock


@pytest.fixture
def valid_api_key():
    return "AIza" + "X" * 35


@pytest.fixture
def app_config(valid_api_key, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", valid_api_key)
    return AppConfig()


@pytest.mark.asyncio
async def test_gemini_provider_generate_success(mock_genai_model):
    # Setup mock response
    mock_response = MagicMock()
    mock_response.text = "Test content"
    mock_response.usage_metadata.prompt_token_count = 10
    mock_response.usage_metadata.candidates_token_count = 20
    mock_response.usage_metadata.total_token_count = 30

    mock_candidate = MagicMock()
    mock_candidate.finish_reason.name = "STOP"
    mock_response.candidates = [mock_candidate]

    mock_model_instance = mock_genai_model.return_value
    mock_model_instance.generate_content_async = AsyncMock(return_value=mock_response)

    # Initialize provider
    provider = GeminiProvider(api_key="test_key")

    # Execute
    result = await provider.generate_content_async("Test prompt")

    # Verify
    assert isinstance(result, GenerationResult)
    assert result.content == "Test content"
    assert result.usage["prompt_tokens"] == 10
    assert result.finish_reason == "STOP"


@pytest.mark.asyncio
async def test_gemini_provider_safety_block(mock_genai_model):
    # Setup mock response with safety block
    mock_response = MagicMock()

    mock_candidate = MagicMock()
    mock_candidate.finish_reason.name = "SAFETY"
    mock_response.candidates = [mock_candidate]

    mock_response.prompt_feedback = "Blocked"

    mock_model_instance = mock_genai_model.return_value
    mock_model_instance.generate_content_async = AsyncMock(return_value=mock_response)

    provider = GeminiProvider(api_key="test_key")

    # Execute & Verify
    with pytest.raises(SafetyBlockedError):
        await provider.generate_content_async("Unsafe prompt")


def test_factory_get_llm_provider(app_config):
    with patch("src.core.adapters.genai.configure"):
        provider = get_llm_provider(app_config)
        assert isinstance(provider, GeminiProvider)


def test_factory_invalid_provider(valid_api_key, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", valid_api_key)
    config = AppConfig(llm_provider_type="invalid")
    with pytest.raises(ValueError, match="Unsupported LLM provider type"):
        get_llm_provider(config)


def test_get_graph_provider_missing():
    class _Cfg:
        graph_provider_type = "neo4j"
        neo4j_uri = None
        neo4j_user = None
        neo4j_password = None

    assert get_graph_provider(_Cfg()) is None  # type: ignore[arg-type]


def test_get_graph_provider_valid():
    class _Cfg:
        graph_provider_type = "neo4j"
        neo4j_uri = "bolt://localhost:7687"
        neo4j_user = "u"
        neo4j_password = "p"

    provider = get_graph_provider(_Cfg())  # type: ignore[arg-type]
    assert provider is not None
