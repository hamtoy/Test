"""Tests for QAGenerator class in generator.py."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def fake_api_key() -> str:
    """Provide a valid format API key for testing."""
    return "AIza" + "x" * 35


@pytest.fixture
def mock_model() -> MagicMock:
    """Create a mock Gemini model."""
    mock = MagicMock()
    mock_response = MagicMock()
    mock_response.text = (
        "1. 첫 번째 질문\n2. 두 번째 질문\n3. 세 번째 질문\n4. 네 번째 질문"
    )
    mock.generate_content.return_value = mock_response
    return mock


class TestQAGenerator:
    """Tests for QAGenerator class."""

    @pytest.fixture
    def mock_config(self, fake_api_key: str, monkeypatch: pytest.MonkeyPatch) -> Any:
        """Create a mock AppConfig."""
        monkeypatch.setenv("GEMINI_API_KEY", fake_api_key)
        monkeypatch.setenv("ENABLE_RAG", "false")
        from src.config.settings import AppConfig

        return AppConfig(
            enable_rag=False,
            neo4j_uri=None,
            neo4j_user=None,
            neo4j_password=None,
            _env_file=None,
        )

    def test_init_with_mock_model(
        self, mock_config: Any, mock_model: MagicMock
    ) -> None:
        """Test QAGenerator initialization with injected model."""
        from src.qa.generator import QAGenerator

        generator = QAGenerator(mock_config, model=mock_model)

        assert generator.config is mock_config
        assert generator.model is mock_model

    def test_generate_questions_with_4_questions(
        self, mock_config: Any, mock_model: MagicMock
    ) -> None:
        """Test generating 4 questions."""
        from src.qa.generator import QAGenerator

        generator = QAGenerator(mock_config, model=mock_model)
        questions = generator.generate_questions("테스트 OCR 텍스트", query_count=4)

        assert len(questions) == 4
        assert mock_model.generate_content.called

    def test_generate_questions_with_3_questions(
        self, mock_config: Any, mock_model: MagicMock
    ) -> None:
        """Test generating 3 questions."""
        from src.qa.generator import QAGenerator

        mock_model.generate_content.return_value.text = (
            "1. 첫 번째 질문\n2. 두 번째 질문\n3. 세 번째 질문"
        )

        generator = QAGenerator(mock_config, model=mock_model)
        questions = generator.generate_questions("테스트 OCR 텍스트", query_count=3)

        assert len(questions) == 3

    def test_generate_questions_invalid_count(
        self, mock_config: Any, mock_model: MagicMock
    ) -> None:
        """Test that invalid query_count raises ValueError."""
        from src.qa.generator import QAGenerator

        generator = QAGenerator(mock_config, model=mock_model)

        with pytest.raises(ValueError, match="query_count must be 3 or 4"):
            generator.generate_questions("테스트", query_count=5)

    def test_generate_questions_empty_response(
        self, mock_config: Any, mock_model: MagicMock
    ) -> None:
        """Test that empty LLM response raises RuntimeError."""
        from src.qa.generator import QAGenerator

        mock_model.generate_content.return_value.text = ""

        generator = QAGenerator(mock_config, model=mock_model)

        with pytest.raises(RuntimeError, match="질의 생성 실패"):
            generator.generate_questions("테스트", query_count=4)

    def test_generate_answers(self, mock_config: Any, mock_model: MagicMock) -> None:
        """Test generating answers for questions."""
        from src.qa.generator import QAGenerator

        mock_model.generate_content.return_value.text = "이것은 답변입니다."

        generator = QAGenerator(mock_config, model=mock_model)
        questions = ["질문1", "질문2"]
        answers = generator.generate_answers("OCR 텍스트", questions)

        assert len(answers) == 2
        assert answers[0]["id"] == 1
        assert answers[0]["question"] == "질문1"
        assert answers[0]["answer"] == "이것은 답변입니다."

    def test_generate_qa(self, mock_config: Any, mock_model: MagicMock) -> None:
        """Test full QA generation pipeline."""
        from src.qa.generator import QAGenerator

        mock_model.generate_content.return_value.text = (
            "1. 첫 번째 질문\n2. 두 번째 질문\n3. 세 번째 질문\n4. 네 번째 질문"
        )

        generator = QAGenerator(mock_config, model=mock_model)
        qa_pairs = generator.generate_qa("OCR 텍스트", query_count=4)

        assert len(qa_pairs) == 4
        # generate_content called: 1 for questions + 4 for answers = 5 times
        assert mock_model.generate_content.call_count == 5

    def test_save_results_json_only(
        self, mock_config: Any, mock_model: MagicMock
    ) -> None:
        """Test saving results to JSON only."""
        from src.qa.generator import QAGenerator

        generator = QAGenerator(mock_config, model=mock_model)

        qa_pairs = [
            {"id": 1, "question": "Q1", "answer": "A1"},
            {"id": 2, "question": "Q2", "answer": "A2"},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "output.json"
            generator.save_results(qa_pairs, json_path=json_path)

            assert json_path.exists()
            with open(json_path, encoding="utf-8") as f:
                saved = json.load(f)
            assert len(saved) == 2

    def test_save_results_with_markdown(
        self, mock_config: Any, mock_model: MagicMock
    ) -> None:
        """Test saving results to both JSON and Markdown."""
        from src.qa.generator import QAGenerator

        generator = QAGenerator(mock_config, model=mock_model)

        qa_pairs = [
            {"id": 1, "question": "Q1", "answer": "A1"},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "output.json"
            md_path = Path(tmpdir) / "output.md"
            generator.save_results(qa_pairs, json_path=json_path, markdown_path=md_path)

            assert json_path.exists()
            assert md_path.exists()

            md_content = md_path.read_text(encoding="utf-8")
            assert "QA Results" in md_content
            assert "Q1" in md_content

    def test_load_prompt_file_not_found(
        self, mock_config: Any, mock_model: MagicMock
    ) -> None:
        """Test that missing prompt file raises FileNotFoundError."""
        from src.qa.generator import QAGenerator

        with pytest.raises(FileNotFoundError, match="Prompt file not found"):
            QAGenerator(
                mock_config,
                model=mock_model,
                query_prompt_path="/nonexistent/path.txt",
            )


class TestParseQuestions:
    """Tests for _parse_questions static method."""

    def test_parse_questions_filters_special_lines(self) -> None:
        """Test that _parse_questions filters out special lines."""
        from src.qa.generator import QAGenerator

        raw = """
# Header
```code```
<tag>
1. 실제 질문1
2. 실제 질문2

"""
        questions = QAGenerator._parse_questions(raw)

        assert len(questions) == 2
        assert "실제 질문1" in questions[0]
        assert "실제 질문2" in questions[1]

    def test_parse_questions_removes_numbering(self) -> None:
        """Test that _parse_questions removes number prefixes."""
        from src.qa.generator import QAGenerator

        raw = "1. 첫 번째\n2. 두 번째\n3. 세 번째"
        questions = QAGenerator._parse_questions(raw)

        assert questions[0] == "첫 번째"
        assert questions[1] == "두 번째"
        assert questions[2] == "세 번째"


class TestGeneratorModuleFunctions:
    """Tests for module-level functions."""

    def test_load_default_ocr_text_fallback(self) -> None:
        """Test _load_default_ocr_text returns fallback when file doesn't exist."""
        from src.qa.generator import _load_default_ocr_text

        result = _load_default_ocr_text()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_should_autorun_returns_false(self) -> None:
        """Test _should_autorun returns False when not __main__."""
        from src.qa.generator import _should_autorun

        assert _should_autorun() is False
