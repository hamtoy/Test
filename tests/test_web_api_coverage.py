"""Tests for web API module to improve coverage."""

import io
import json
import os
import sys
import types
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set up environment before imports
os.environ.setdefault("GEMINI_API_KEY", "AIza" + "0" * 35)
os.environ.setdefault("GEMINI_MODEL_NAME", "gemini-3-pro-preview")

# Mock pytesseract before importing web.api
pytesseract_mock = types.ModuleType("pytesseract")
pytesseract_mock.image_to_string: Any = MagicMock(return_value="")
sys.modules["pytesseract"] = pytesseract_mock

from fastapi.testclient import TestClient  # noqa: E402

from src.web.api import (  # noqa: E402
    app,
    generate_single_qa,
    init_resources,
    load_ocr_text,
    log_review_session,
    save_ocr_text,
)


@pytest.fixture
def client():
    """Create test client for the API."""
    return TestClient(app)


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_load_ocr_text_success(self, tmp_path):
        """Test load_ocr_text with existing file."""
        inputs_dir = tmp_path / "inputs"
        inputs_dir.mkdir()
        ocr_file = inputs_dir / "input_ocr.txt"
        ocr_file.write_text("테스트 OCR 내용", encoding="utf-8")

        with patch("src.web.api.config") as mock_config:
            mock_config.input_dir = inputs_dir
            result = load_ocr_text()
            assert result == "테스트 OCR 내용"

    def test_load_ocr_text_whitespace_stripped(self, tmp_path):
        """Test load_ocr_text strips whitespace."""
        inputs_dir = tmp_path / "inputs"
        inputs_dir.mkdir()
        ocr_file = inputs_dir / "input_ocr.txt"
        ocr_file.write_text("  테스트 내용  \n", encoding="utf-8")

        with patch("src.web.api.config") as mock_config:
            mock_config.input_dir = inputs_dir
            result = load_ocr_text()
            assert result == "테스트 내용"

    def test_save_ocr_text_creates_directory(self, tmp_path):
        """Test save_ocr_text creates directory if not exists."""
        inputs_dir = tmp_path / "inputs"
        # Directory doesn't exist yet

        with patch("src.web.api.config") as mock_config:
            mock_config.input_dir = inputs_dir
            save_ocr_text("새 OCR 텍스트")

            ocr_file = inputs_dir / "input_ocr.txt"
            assert ocr_file.exists()
            assert ocr_file.read_text(encoding="utf-8") == "새 OCR 텍스트"

    def test_save_ocr_text_overwrites(self, tmp_path):
        """Test save_ocr_text overwrites existing file."""
        inputs_dir = tmp_path / "inputs"
        inputs_dir.mkdir()
        ocr_file = inputs_dir / "input_ocr.txt"
        ocr_file.write_text("기존 내용", encoding="utf-8")

        with patch("src.web.api.config") as mock_config:
            mock_config.input_dir = inputs_dir
            save_ocr_text("새 내용")

            assert ocr_file.read_text(encoding="utf-8") == "새 내용"


class TestInitResources:
    """Tests for init_resources function."""

    @pytest.mark.asyncio
    async def test_init_resources_creates_agent(self, tmp_path):
        """Test init_resources creates GeminiAgent."""
        import src.web.api as api_module

        # Reset global state
        original_agent = api_module.agent
        original_kg = api_module.kg
        original_mm = api_module.mm

        try:
            api_module.agent = None
            api_module.kg = None
            api_module.mm = None

            with patch("src.web.api.REPO_ROOT", tmp_path):
                # Create templates directory
                templates_dir = tmp_path / "templates"
                templates_dir.mkdir()

                with (
                    patch("src.web.api.GeminiAgent") as mock_agent_class,
                    patch("src.web.api.QAKnowledgeGraph") as mock_kg_class,
                ):
                    mock_kg_class.side_effect = Exception("No Neo4j")

                    await init_resources()

                    mock_agent_class.assert_called_once()
                    assert api_module.agent is not None
        finally:
            # Restore original state
            api_module.agent = original_agent
            api_module.kg = original_kg
            api_module.mm = original_mm

    @pytest.mark.asyncio
    async def test_init_resources_with_kg_success(self, tmp_path):
        """Test init_resources creates KnowledgeGraph when Neo4j available."""
        import src.web.api as api_module

        original_agent = api_module.agent
        original_kg = api_module.kg
        original_mm = api_module.mm

        try:
            api_module.agent = None
            api_module.kg = None
            api_module.mm = None

            with patch("src.web.api.REPO_ROOT", tmp_path):
                templates_dir = tmp_path / "templates"
                templates_dir.mkdir()

                mock_kg = MagicMock()
                with (
                    patch("src.web.api.GeminiAgent"),
                    patch("src.web.api.QAKnowledgeGraph", return_value=mock_kg),
                    patch("src.web.api.MultimodalUnderstanding") as mock_mm_class,
                ):
                    await init_resources()

                    assert api_module.kg is not None
                    mock_mm_class.assert_called_once_with(kg=mock_kg)
        finally:
            api_module.agent = original_agent
            api_module.kg = original_kg
            api_module.mm = original_mm


class TestGenerateSingleQA:
    """Tests for generate_single_qa function."""

    @pytest.mark.asyncio
    async def test_generate_single_qa_basic(self):
        """Test generate_single_qa returns expected structure."""
        mock_agent = MagicMock()
        mock_agent.generate_query = AsyncMock(return_value=["생성된 질의"])

        with patch("src.web.api.kg", None):
            result = await generate_single_qa(mock_agent, "OCR 텍스트", "reasoning")

            assert "type" in result
            assert result["type"] == "reasoning"
            assert "query" in result
            assert result["query"] == "생성된 질의"
            assert "answer" in result

    @pytest.mark.asyncio
    async def test_generate_single_qa_empty_queries(self):
        """Test generate_single_qa raises on empty queries."""
        mock_agent = MagicMock()
        mock_agent.generate_query = AsyncMock(return_value=[])

        with (
            patch("src.web.api.kg", None),
            pytest.raises(ValueError, match="질의 생성 실패"),
        ):
            await generate_single_qa(mock_agent, "OCR 텍스트", "reasoning")

    @pytest.mark.asyncio
    async def test_generate_single_qa_with_kg(self, monkeypatch):
        """Test generate_single_qa uses template generator with kg."""
        mock_agent = MagicMock()
        mock_agent.generate_query = AsyncMock(return_value=["생성된 질의"])

        mock_kg = MagicMock()
        mock_template_gen = MagicMock()
        mock_template_gen.generate_prompt_for_query_type.return_value = (
            "템플릿 프롬프트"
        )

        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "password")

        with (
            patch("src.web.api.kg", mock_kg),
            patch(
                "src.processing.template_generator.DynamicTemplateGenerator",
                return_value=mock_template_gen,
            ),
        ):
            result = await generate_single_qa(
                mock_agent, "OCR 텍스트", "global_explanation"
            )

            assert result["type"] == "global_explanation"


class TestLogReviewSessionEdgeCases:
    """Additional edge case tests for log_review_session."""

    def test_log_review_session_unicode_content(self, tmp_path):
        """Test log_review_session handles unicode content."""
        with patch("src.web.api.REPO_ROOT", tmp_path):
            log_review_session(
                mode="edit",
                question="한글 질문 🎉",
                answer_before="이모지 포함 답변 ✨",
                answer_after="수정된 답변 🚀",
                edit_request_used="더 자세하게",
                inspector_comment="잘했어요 👍",
            )

            log_dir = tmp_path / "data" / "outputs" / "review_logs"
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            log_file = log_dir / f"review_{today}.jsonl"

            with open(log_file, "r", encoding="utf-8") as f:
                entry = json.loads(f.readline())

            assert "🎉" in entry["question"]
            assert "✨" in entry["answer_before"]
            assert "🚀" in entry["answer_after"]
            assert "👍" in entry["inspector_comment"]

    def test_log_review_session_long_content(self, tmp_path):
        """Test log_review_session handles very long content."""
        long_text = "A" * 10000

        with patch("src.web.api.REPO_ROOT", tmp_path):
            log_review_session(
                mode="inspect",
                question=long_text,
                answer_before=long_text,
                answer_after=long_text,
                edit_request_used=long_text,
                inspector_comment=long_text,
            )

            log_dir = tmp_path / "data" / "outputs" / "review_logs"
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            log_file = log_dir / f"review_{today}.jsonl"

            with open(log_file, "r", encoding="utf-8") as f:
                entry = json.loads(f.readline())

            assert len(entry["question"]) == 10000


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check_all_none(self, client):
        """Test health check when all resources are None."""
        import src.web.api as api_module

        original_agent = api_module.agent
        original_kg = api_module.kg
        original_mm = api_module.mm

        try:
            api_module.agent = None
            api_module.kg = None
            api_module.mm = None

            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["agent"] is False
            assert data["neo4j"] is False
            assert data["multimodal"] is False
        finally:
            api_module.agent = original_agent
            api_module.kg = original_kg
            api_module.mm = original_mm

    def test_health_check_with_agent(self, client):
        """Test health check when agent is initialized."""
        import src.web.api as api_module

        original_agent = api_module.agent
        original_kg = api_module.kg
        original_mm = api_module.mm

        try:
            api_module.agent = MagicMock()
            api_module.kg = None
            api_module.mm = None

            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["agent"] is True
            assert data["neo4j"] is False
        finally:
            api_module.agent = original_agent
            api_module.kg = original_kg
            api_module.mm = original_mm


class TestWorkspaceApiExtended:
    """Extended tests for workspace API."""

    def test_workspace_inspect_with_mocked_agent(self, client, tmp_path):
        """Test workspace inspect mode with mocked agent."""
        import src.web.api as api_module

        original_agent = api_module.agent

        # Create OCR file
        inputs_dir = tmp_path / "inputs"
        inputs_dir.mkdir()
        (inputs_dir / "input_ocr.txt").write_text("OCR 내용", encoding="utf-8")

        try:
            mock_agent = MagicMock()
            api_module.agent = mock_agent

            with patch("src.web.api.config") as mock_config:
                mock_config.input_dir = inputs_dir

                with patch("src.web.api.inspect_answer") as mock_inspect:
                    mock_inspect.return_value = "수정된 답변"

                    response = client.post(
                        "/api/workspace",
                        json={
                            "mode": "inspect",
                            "answer": "원본 답변",
                            "query": "테스트 질의",
                        },
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["mode"] == "inspect"
                    assert data["result"]["fixed"] == "수정된 답변"
        finally:
            api_module.agent = original_agent

    def test_workspace_edit_with_mocked_agent(self, client, tmp_path):
        """Test workspace edit mode with mocked agent."""
        import src.web.api as api_module

        original_agent = api_module.agent

        inputs_dir = tmp_path / "inputs"
        inputs_dir.mkdir()
        (inputs_dir / "input_ocr.txt").write_text("OCR 내용", encoding="utf-8")

        try:
            mock_agent = MagicMock()
            api_module.agent = mock_agent

            with patch("src.web.api.config") as mock_config:
                mock_config.input_dir = inputs_dir

                with patch("src.web.api.edit_content") as mock_edit:
                    mock_edit.return_value = "수정된 내용"

                    response = client.post(
                        "/api/workspace",
                        json={
                            "mode": "edit",
                            "answer": "원본 답변",
                            "edit_request": "더 간결하게",
                        },
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["mode"] == "edit"
                    assert data["result"]["edited"] == "수정된 내용"
        finally:
            api_module.agent = original_agent


class TestQAGenerateApiExtended:
    """Extended tests for QA generation API."""

    def test_generate_batch_with_mocked_agent(self, client, tmp_path):
        """Test batch QA generation with mocked agent."""
        import src.web.api as api_module

        original_agent = api_module.agent

        inputs_dir = tmp_path / "inputs"
        inputs_dir.mkdir()
        (inputs_dir / "input_ocr.txt").write_text("OCR 내용", encoding="utf-8")

        try:
            mock_agent = MagicMock()
            mock_agent.generate_query = AsyncMock(return_value=["생성된 질의"])
            api_module.agent = mock_agent

            with patch("src.web.api.config") as mock_config:
                mock_config.input_dir = inputs_dir

                with patch("src.web.api.kg", None):
                    response = client.post(
                        "/api/qa/generate",
                        json={"mode": "batch"},
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["mode"] == "batch"
                    assert len(data["pairs"]) == 4
        finally:
            api_module.agent = original_agent


class TestEvalApiExtended:
    """Extended tests for evaluation API."""

    def test_eval_external_with_mocked_agent(self, client, tmp_path):
        """Test external evaluation with mocked agent."""
        import src.web.api as api_module

        original_agent = api_module.agent

        inputs_dir = tmp_path / "inputs"
        inputs_dir.mkdir()
        (inputs_dir / "input_ocr.txt").write_text("OCR 내용", encoding="utf-8")

        try:
            mock_agent = MagicMock()
            api_module.agent = mock_agent

            with patch("src.web.api.config") as mock_config:
                mock_config.input_dir = inputs_dir

                with patch(
                    "src.workflow.external_eval.evaluate_external_answers"
                ) as mock_eval:
                    mock_eval.return_value = [
                        {"candidate_id": "A", "score": 0.9},
                        {"candidate_id": "B", "score": 0.7},
                        {"candidate_id": "C", "score": 0.5},
                    ]

                    response = client.post(
                        "/api/eval/external",
                        json={
                            "query": "테스트 질의",
                            "answers": ["답변 A", "답변 B", "답변 C"],
                        },
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["best"] == "A"
                    assert len(data["results"]) == 3
        finally:
            api_module.agent = original_agent


class TestMultimodalApiExtended:
    """Extended tests for multimodal API."""

    def test_multimodal_with_mocked_mm(self, client, tmp_path):
        """Test multimodal analysis with mocked mm."""
        import src.web.api as api_module

        original_mm = api_module.mm

        inputs_dir = tmp_path / "inputs"
        inputs_dir.mkdir()

        try:
            mock_mm = MagicMock()
            mock_mm.analyze_image_deep.return_value = {
                "extracted_text": "추출된 텍스트",
                "has_table": True,
            }
            api_module.mm = mock_mm

            with patch("src.web.api.config") as mock_config:
                mock_config.input_dir = inputs_dir

                # Create a minimal PNG image
                image_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
                files = {"file": ("test.png", io.BytesIO(image_content), "image/png")}

                response = client.post("/api/multimodal/analyze", files=files)

                assert response.status_code == 200
                data = response.json()
                assert data["filename"] == "test.png"
                assert "metadata" in data
        finally:
            api_module.mm = original_mm

    def test_multimodal_invalid_content_type(self, client):
        """Test multimodal with invalid content type when mm is available."""
        import src.web.api as api_module

        original_mm = api_module.mm

        try:
            mock_mm = MagicMock()
            api_module.mm = mock_mm

            files = {"file": ("test.txt", io.BytesIO(b"text"), "text/plain")}

            response = client.post("/api/multimodal/analyze", files=files)

            assert response.status_code == 400
        finally:
            api_module.mm = original_mm

    def test_multimodal_missing_content_type(self, client):
        """Test multimodal with missing content type when mm is available."""
        import src.web.api as api_module

        original_mm = api_module.mm

        try:
            mock_mm = MagicMock()
            api_module.mm = mock_mm

            # File with None content type
            files = {"file": ("test.bin", io.BytesIO(b"binary"), None)}

            response = client.post("/api/multimodal/analyze", files=files)

            assert response.status_code == 400
        finally:
            api_module.mm = original_mm

    def test_multimodal_analysis_error(self, client, tmp_path):
        """Test multimodal handles analysis errors."""
        import src.web.api as api_module

        original_mm = api_module.mm

        inputs_dir = tmp_path / "inputs"
        inputs_dir.mkdir()

        try:
            mock_mm = MagicMock()
            mock_mm.analyze_image_deep.side_effect = Exception("Analysis failed")
            api_module.mm = mock_mm

            with patch("src.web.api.config") as mock_config:
                mock_config.input_dir = inputs_dir

                image_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
                files = {"file": ("test.png", io.BytesIO(image_content), "image/png")}

                response = client.post("/api/multimodal/analyze", files=files)

                assert response.status_code == 500
        finally:
            api_module.mm = original_mm
