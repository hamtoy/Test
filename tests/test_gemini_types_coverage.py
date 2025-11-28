"""Tests for src/llm/gemini_types.py to improve coverage."""

import pytest
from unittest.mock import MagicMock, patch


class TestGeminiTypes:
    """Test Gemini type wrappers and helper functions."""

    def test_generation_config_typed_dict(self):
        """Test GenerationConfig TypedDict."""
        from src.llm.gemini_types import GenerationConfig

        config: GenerationConfig = {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 1024,
        }
        assert config["temperature"] == 0.7
        assert config["max_output_tokens"] == 1024

    def test_safety_settings_typed_dict(self):
        """Test SafetySettings TypedDict."""
        from src.llm.gemini_types import SafetySettings

        settings: SafetySettings = {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE",
        }
        assert settings["category"] == "HARM_CATEGORY_HARASSMENT"

    def test_generate_content_response_class(self):
        """Test GenerateContentResponse is a valid class."""
        from src.llm.gemini_types import GenerateContentResponse

        # Verify it's a class
        assert isinstance(GenerateContentResponse, type)
        # Verify it can be used as a reference class
        assert GenerateContentResponse.__name__ == "GenerateContentResponse"


class TestConfigureGenai:
    """Test configure_genai wrapper function."""

    @patch("google.generativeai.configure")
    def test_configure_genai(self, mock_configure):
        """Test configure_genai calls genai.configure."""
        from src.llm.gemini_types import configure_genai

        configure_genai(api_key="test-api-key")

        mock_configure.assert_called_once_with(api_key="test-api-key")


class TestCreateGenerativeModel:
    """Test create_generative_model wrapper function."""

    @patch("google.generativeai.GenerativeModel")
    def test_create_model_basic(self, mock_model_class):
        """Test creating model with just name."""
        from src.llm.gemini_types import create_generative_model

        mock_model_class.return_value = MagicMock()

        result = create_generative_model("gemini-1.5-pro")

        mock_model_class.assert_called_once_with("gemini-1.5-pro")
        assert result is not None

    @patch("google.generativeai.GenerativeModel")
    def test_create_model_with_config(self, mock_model_class):
        """Test creating model with generation config."""
        from src.llm.gemini_types import create_generative_model, GenerationConfig

        mock_model_class.return_value = MagicMock()
        config: GenerationConfig = {"temperature": 0.5}

        result = create_generative_model("gemini-1.5-pro", generation_config=config)

        mock_model_class.assert_called_once_with(
            "gemini-1.5-pro", generation_config=config
        )
        assert result is not None

    @patch("google.generativeai.GenerativeModel")
    def test_create_model_with_safety_settings(self, mock_model_class):
        """Test creating model with safety settings."""
        from src.llm.gemini_types import create_generative_model, SafetySettings

        mock_model_class.return_value = MagicMock()
        settings: list[SafetySettings] = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}
        ]

        result = create_generative_model("gemini-1.5-pro", safety_settings=settings)

        mock_model_class.assert_called_once_with(
            "gemini-1.5-pro", safety_settings=settings
        )
        assert result is not None

    @patch("google.generativeai.GenerativeModel")
    def test_create_model_with_all_options(self, mock_model_class):
        """Test creating model with all options."""
        from src.llm.gemini_types import (
            create_generative_model,
            GenerationConfig,
            SafetySettings,
        )

        mock_model_class.return_value = MagicMock()
        config: GenerationConfig = {"temperature": 0.7}
        settings: list[SafetySettings] = [
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]

        result = create_generative_model(
            "gemini-1.5-flash",
            generation_config=config,
            safety_settings=settings,
        )

        mock_model_class.assert_called_once_with(
            "gemini-1.5-flash",
            generation_config=config,
            safety_settings=settings,
        )
        assert result is not None


class TestListAvailableModels:
    """Test list_available_models wrapper function."""

    @patch("google.generativeai.list_models")
    def test_list_models(self, mock_list_models):
        """Test listing available models."""
        from src.llm.gemini_types import list_available_models

        mock_model = MagicMock()
        mock_model.name = "models/gemini-1.5-pro"
        mock_list_models.return_value = iter([mock_model])

        result = list_available_models()

        assert len(result) == 1
        assert result[0].name == "models/gemini-1.5-pro"


class TestEmbedContent:
    """Test embed_content wrapper function."""

    @patch("google.generativeai.embed_content")
    def test_embed_content_dict_like_result(self, mock_embed):
        """Test embed_content with dict-like result."""
        from src.llm.gemini_types import embed_content

        mock_result = MagicMock()
        mock_result.keys.return_value = ["embedding"]
        mock_result.__iter__ = MagicMock(return_value=iter(["embedding"]))
        mock_result.__getitem__ = MagicMock(return_value=[0.1, 0.2, 0.3])
        mock_embed.return_value = mock_result

        result = embed_content(
            model="models/embedding-001",
            content="Test content",
            task_type="retrieval_query",
        )

        assert isinstance(result, dict)
        mock_embed.assert_called_once_with(
            model="models/embedding-001",
            content="Test content",
            task_type="retrieval_query",
        )

    @patch("google.generativeai.embed_content")
    def test_embed_content_raw_result(self, mock_embed):
        """Test embed_content with raw embedding result."""
        from src.llm.gemini_types import embed_content

        # Result without keys method (raw embedding)
        mock_embed.return_value = [0.1, 0.2, 0.3]

        result = embed_content(
            model="models/embedding-001",
            content="Test content",
        )

        assert result == {"embedding": [0.1, 0.2, 0.3]}

    @patch("google.generativeai.embed_content")
    def test_embed_content_default_task_type(self, mock_embed):
        """Test embed_content uses default task_type."""
        from src.llm.gemini_types import embed_content

        mock_result = MagicMock()
        mock_result.keys.return_value = ["embedding"]
        mock_embed.return_value = mock_result

        embed_content(model="models/embedding-001", content="Test")

        mock_embed.assert_called_once_with(
            model="models/embedding-001",
            content="Test",
            task_type="retrieval_query",
        )


class TestAllExports:
    """Test __all__ exports."""

    def test_all_contains_expected_names(self):
        """Test __all__ contains expected exports."""
        from src.llm import gemini_types

        assert "GenerationConfig" in gemini_types.__all__
        assert "SafetySettings" in gemini_types.__all__
        assert "GenerateContentResponse" in gemini_types.__all__
        assert "configure_genai" in gemini_types.__all__
        assert "create_generative_model" in gemini_types.__all__
        assert "list_available_models" in gemini_types.__all__
        assert "embed_content" in gemini_types.__all__
