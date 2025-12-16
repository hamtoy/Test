"""Tests for script coverage - QA generator and list models."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_qa_generator_class(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test QAGenerator class with mocked Gemini model."""
    # Set environment variable with valid format (AIza + 35 chars)
    fake_api_key = "AIza" + "x" * 35
    monkeypatch.setenv("GEMINI_API_KEY", fake_api_key)
    monkeypatch.setenv("ENABLE_RAG", "false")

    # Import after setting env
    from src.config.settings import AppConfig
    from src.qa.generator import QAGenerator

    # Create mock response
    mock_response = MagicMock()
    mock_response.text = (
        "1. 첫 번째 질문\n2. 두 번째 질문\n3. 세 번째 질문\n4. 네 번째 질문"
    )

    # Create mock model
    mock_model = MagicMock()
    mock_model.generate_content.return_value = mock_response

    # Create config (api_key is read from GEMINI_API_KEY env)
    config = AppConfig(
        enable_rag=False,
        neo4j_uri=None,
        neo4j_user=None,
        neo4j_password=None,
        _env_file=None,
    )

    # Create generator with mocked model
    generator = QAGenerator(config, model=mock_model)

    # Test generate_questions
    questions = generator.generate_questions("테스트 OCR 텍스트", query_count=4)

    # Verify
    assert mock_model.generate_content.called
    assert len(questions) == 4
    assert "첫 번째 질문" in questions[0]


def test_list_models_script(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test list_models script with mocked Gemini API."""
    import types

    # Set valid API key format
    fake_api_key = "AIza" + "x" * 35
    monkeypatch.setenv("GEMINI_API_KEY", fake_api_key)

    class _FakeModel:
        def __init__(self, name: str, methods: list[str] | None = None) -> None:
            self.name = name
            self.supported_generation_methods = methods or ["generateContent"]

    fake_genai = types.SimpleNamespace(
        configure=lambda api_key: None,
        list_models=lambda: [_FakeModel("m1"), _FakeModel("m2", ["other"])],
    )

    with patch("src.llm.list_models.genai", fake_genai):
        from src.llm import list_models

        # Module should complete without error
        assert hasattr(list_models, "logger")
