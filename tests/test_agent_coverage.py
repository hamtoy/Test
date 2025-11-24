import pytest
from unittest.mock import MagicMock, patch, mock_open, PropertyMock
from src.agent import GeminiAgent
from src.config import AppConfig
from src.exceptions import (
    CacheCreationError,
    APIRateLimitError,
    ValidationFailedError,
    BudgetExceededError,
)


@pytest.fixture
def mock_config(tmp_path):
    config = MagicMock(spec=AppConfig)
    config.template_dir = tmp_path / "templates"
    config.template_dir.mkdir()
    # Create dummy templates with content
    for name in [
        "prompt_eval.j2",
        "prompt_query_gen.j2",
        "prompt_rewrite.j2",
        "query_gen_user.j2",
        "rewrite_user.j2",
    ]:
        p = config.template_dir / name
        p.write_text(
            "dummy template content {{ ocr_text }} {{ user_intent }} {{ best_answer }}"
        )

    config.max_concurrency = 1
    config.model_name = "gemini-1.5-flash"
    config.temperature = 0.0
    config.max_output_tokens = 100
    config.local_cache_dir = tmp_path / "cache"
    config.base_dir = tmp_path
    config.cache_ttl_minutes = 60
    config.timeout = 10
    config.budget_limit_usd = 10.0
    return config


@pytest.mark.asyncio
async def test_init_missing_template(mock_config):
    # Remove a template
    (mock_config.template_dir / "prompt_eval.j2").unlink()
    with pytest.raises(FileNotFoundError):
        GeminiAgent(mock_config)


def test_lazy_imports(mock_config):
    agent = GeminiAgent(mock_config)
    assert agent._genai is not None
    assert agent._caching is not None

    # Test module level getattr
    from src.agent import caching

    assert caching is not None


@pytest.mark.asyncio
async def test_cache_cleanup_read_error(mock_config):
    agent = GeminiAgent(mock_config)
    with patch("builtins.open", side_effect=OSError("Read error")):
        agent._cleanup_expired_cache(60)
    # Should not raise


@pytest.mark.asyncio
async def test_cache_cleanup_write_error(mock_config):
    agent = GeminiAgent(mock_config)
    # Mock read success, write fail
    with (
        patch(
            "builtins.open",
            mock_open(
                read_data='{"hash": {"created": "2023-01-01T00:00:00", "ttl_minutes": 1}}'
            ),
        ),
        patch("json.dump", side_effect=OSError("Write error")),
    ):
        agent._cleanup_expired_cache(60)
    # Should not raise


@pytest.mark.asyncio
async def test_create_context_cache_resource_exhausted(mock_config):
    agent = GeminiAgent(mock_config)
    agent.jinja_env = MagicMock()
    agent.jinja_env.get_template.return_value.render.return_value = "system prompt"

    # Mock token count > MIN_CACHE_TOKENS
    with (
        patch("src.agent.MIN_CACHE_TOKENS", 0),
        patch(
            "src.agent.GeminiAgent._genai", new_callable=PropertyMock
        ) as mock_genai_prop,
        patch(
            "src.agent.GeminiAgent._caching", new_callable=PropertyMock
        ) as mock_caching_prop,
        patch("src.agent.GeminiAgent._google_exceptions") as mock_exceptions_method,
    ):
        mock_genai = MagicMock()
        mock_genai_prop.return_value = mock_genai
        mock_genai.GenerativeModel.return_value.count_tokens.return_value.total_tokens = 100

        mock_caching = MagicMock()
        mock_caching_prop.return_value = mock_caching

        class ResourceExhausted(Exception):
            pass

        mock_caching.CachedContent.create.side_effect = ResourceExhausted(
            "Quota exceeded"
        )
        mock_exceptions = MagicMock()
        mock_exceptions.ResourceExhausted = ResourceExhausted
        mock_exceptions_method.return_value = mock_exceptions

        with pytest.raises(CacheCreationError, match="Rate limit exceeded"):
            await agent.create_context_cache("ocr text")


@pytest.mark.asyncio
async def test_generate_query_rate_limit(mock_config):
    agent = GeminiAgent(mock_config)

    class ResourceExhausted(Exception):
        pass

    with patch("src.agent.GeminiAgent._google_exceptions") as mock_exceptions_method:
        mock_exceptions = MagicMock()
        mock_exceptions.ResourceExhausted = ResourceExhausted
        mock_exceptions_method.return_value = mock_exceptions

    with (
        patch.object(
            agent, "_call_api_with_retry", side_effect=ResourceExhausted("Quota")
        ),
        pytest.raises(APIRateLimitError),
    ):
        await agent.generate_query("ocr")


@pytest.mark.asyncio
async def test_generate_query_validation_error(mock_config):
    agent = GeminiAgent(mock_config)
    # Return invalid JSON
    with patch.object(agent, "_call_api_with_retry", return_value="invalid json"):
        queries = await agent.generate_query("ocr")
        assert queries == []


@pytest.mark.asyncio
async def test_evaluate_responses_empty_query(mock_config):
    agent = GeminiAgent(mock_config)
    result = await agent.evaluate_responses("ocr", "", {})
    assert result is None


@pytest.mark.asyncio
async def test_evaluate_responses_validation_failed(mock_config):
    agent = GeminiAgent(mock_config)
    with (
        patch.object(agent, "_call_api_with_retry", return_value="invalid json"),
        pytest.raises(ValidationFailedError),
    ):
        await agent.evaluate_responses("ocr", "query", {"a": "b"})


@pytest.mark.asyncio
async def test_rewrite_best_answer_rate_limit(mock_config):
    agent = GeminiAgent(mock_config)

    class ResourceExhausted(Exception):
        pass

    with patch("src.agent.GeminiAgent._google_exceptions") as mock_exceptions_method:
        mock_exceptions = MagicMock()
        mock_exceptions.ResourceExhausted = ResourceExhausted
        mock_exceptions_method.return_value = mock_exceptions

    with (
        patch.object(
            agent, "_call_api_with_retry", side_effect=ResourceExhausted("Quota")
        ),
        pytest.raises(APIRateLimitError),
    ):
        await agent.rewrite_best_answer("ocr", "ans")


def test_get_total_cost_unknown_model(mock_config):
    mock_config.model_name = "unknown-model"
    agent = GeminiAgent(mock_config)
    with pytest.raises(ValueError, match="Unsupported model"):
        agent.get_total_cost()


def test_budget_check(mock_config):
    agent = GeminiAgent(mock_config)
    mock_config.budget_limit_usd = 0.0001
    agent.total_input_tokens = 10000000  # High cost

    # Mock pricing tier
    with (
        patch(
            "src.agent.PRICING_TIERS",
            {
                "gemini-1.5-flash": [
                    {"max_input_tokens": None, "input_rate": 1.0, "output_rate": 1.0}
                ]
            },
        ),
        pytest.raises(BudgetExceededError),
    ):
        agent.check_budget()
