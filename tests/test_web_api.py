"""Tests for the web API module."""

import io
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.web.api import app


@pytest.fixture
def client():
    """Create test client for the API."""
    return TestClient(app)


class TestPageRoutes:
    """Tests for page routes."""

    def test_qa_page_root(self, client):
        """Test the root page redirects to QA page."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_qa_page_explicit(self, client):
        """Test the explicit /qa page."""
        response = client.get("/qa")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_eval_page(self, client):
        """Test the evaluation page."""
        response = client.get("/eval")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_workspace_page(self, client):
        """Test the workspace page."""
        response = client.get("/workspace")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_multimodal_page(self, client):
        """Test the multimodal page."""
        response = client.get("/multimodal")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestOCRApi:
    """Tests for OCR API endpoint."""

    def test_get_ocr_file_exists(self, client, tmp_path, monkeypatch):
        """Test getting OCR text when file exists."""
        # Create a mock ocr.txt file
        ocr_file = tmp_path / "ocr.txt"
        ocr_file.write_text("테스트 OCR 텍스트", encoding="utf-8")

        # Patch PROJECT_ROOT to use tmp_path
        with patch("src.web.api.PROJECT_ROOT", tmp_path):
            # Need to create the data directory
            data_dir = tmp_path / "data"
            data_dir.mkdir()
            (data_dir / "ocr.txt").write_text("테스트 OCR 텍스트", encoding="utf-8")

            response = client.get("/api/ocr")
            assert response.status_code == 200
            data = response.json()
            assert data["ocr"] == "테스트 OCR 텍스트"

    def test_get_ocr_file_not_exists(self, client, tmp_path):
        """Test getting OCR text when file doesn't exist."""
        with patch("src.web.api.PROJECT_ROOT", tmp_path):
            response = client.get("/api/ocr")
            assert response.status_code == 200
            data = response.json()
            assert data["ocr"] is None


class TestQAGenerateApi:
    """Tests for QA generation API endpoint."""

    def test_generate_batch_qa(self, client):
        """Test batch QA generation."""
        response = client.post("/api/qa/generate", json={"mode": "batch"})
        assert response.status_code == 200
        data = response.json()
        assert "pairs" in data
        assert len(data["pairs"]) == 4
        assert data["mode"] == "batch"

    def test_generate_single_qa_valid_type(self, client):
        """Test single QA generation with valid type."""
        response = client.post(
            "/api/qa/generate", json={"mode": "single", "qtype": "reasoning"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "pair" in data
        assert data["mode"] == "single"
        assert data["pair"]["type"] == "추론"

    def test_generate_single_qa_missing_type(self, client):
        """Test single QA generation with missing type."""
        response = client.post("/api/qa/generate", json={"mode": "single"})
        assert response.status_code == 400
        data = response.json()
        assert "Invalid question type" in data["detail"]

    def test_generate_single_qa_invalid_type(self, client):
        """Test single QA generation with invalid type."""
        response = client.post(
            "/api/qa/generate", json={"mode": "single", "qtype": "invalid_type"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "Invalid question type" in data["detail"]

    def test_generate_single_qa_all_types(self, client):
        """Test single QA generation with all valid types."""
        valid_types = [
            ("global_explanation", "전반 설명"),
            ("reasoning", "추론"),
            ("target_short", "타겟 짧은 답변"),
            ("target_long", "타겟 긴 답변"),
        ]
        for qtype, expected_type in valid_types:
            response = client.post(
                "/api/qa/generate", json={"mode": "single", "qtype": qtype}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["pair"]["type"] == expected_type


class TestEvalApi:
    """Tests for evaluation API endpoint."""

    def test_evaluate_answers(self, client):
        """Test evaluation of multiple answers."""
        response = client.post(
            "/api/eval/external",
            json={"query": "Test query", "answers": ["Answer A", "Answer B"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "best" in data
        assert len(data["results"]) == 2

    def test_evaluate_no_answers(self, client):
        """Test evaluation with no answers."""
        response = client.post(
            "/api/eval/external", json={"query": "Test query", "answers": []}
        )
        assert response.status_code == 400
        data = response.json()
        assert "No answers provided" in data["detail"]

    def test_evaluate_many_answers(self, client):
        """Test evaluation with more than 6 answers (limit)."""
        answers = [f"Answer {i}" for i in range(10)]
        response = client.post(
            "/api/eval/external", json={"query": "Test query", "answers": answers}
        )
        assert response.status_code == 200
        data = response.json()
        # Only 6 answers should be processed (A-F)
        assert len(data["results"]) == 6

    def test_evaluate_score_calculation(self, client):
        """Test that longer answers get higher scores."""
        short_answer = "Short"
        long_answer = "This is a much longer answer that should get a higher score"
        response = client.post(
            "/api/eval/external",
            json={"query": "Test", "answers": [short_answer, long_answer]},
        )
        assert response.status_code == 200
        data = response.json()
        # Second answer (B) should have higher score
        assert data["best"] == "B"


class TestWorkspaceApi:
    """Tests for workspace API endpoint."""

    def test_workspace_inspect_mode(self, client):
        """Test workspace inspect mode."""
        response = client.post(
            "/api/workspace",
            json={
                "mode": "inspect",
                "answer": "Original answer",
                "edit_request": "",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "[검수됨]" in data["result"]["fixed"]
        assert data["result"]["edited"] is None

    def test_workspace_edit_mode(self, client):
        """Test workspace edit mode."""
        response = client.post(
            "/api/workspace",
            json={
                "mode": "edit",
                "answer": "Original answer",
                "edit_request": "더 간결하게",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "더 간결하게" in data["result"]["edited"]
        assert data["result"]["fixed"] is None

    def test_workspace_edit_mode_empty_request(self, client):
        """Test workspace edit mode with empty request."""
        response = client.post(
            "/api/workspace",
            json={
                "mode": "edit",
                "answer": "Original answer",
                "edit_request": "",
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert "Edit request is required" in data["detail"]

    def test_workspace_edit_mode_whitespace_request(self, client):
        """Test workspace edit mode with whitespace-only request."""
        response = client.post(
            "/api/workspace",
            json={
                "mode": "edit",
                "answer": "Original answer",
                "edit_request": "   ",
            },
        )
        assert response.status_code == 400

    def test_workspace_invalid_mode(self, client):
        """Test workspace with invalid mode."""
        response = client.post(
            "/api/workspace",
            json={
                "mode": "invalid",
                "answer": "Original answer",
                "edit_request": "",
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert "Invalid mode" in data["detail"]


class TestMultimodalApi:
    """Tests for multimodal/image analysis API endpoint."""

    def test_analyze_image_valid(self, client):
        """Test image analysis with valid image file."""
        # Create a minimal valid image
        image_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        files = {"file": ("test.png", io.BytesIO(image_content), "image/png")}
        response = client.post("/api/multimodal/analyze", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.png"
        assert "metadata" in data
        assert data["metadata"]["has_table_chart"] is True
        assert "topics" in data["metadata"]

    def test_analyze_image_jpeg(self, client):
        """Test image analysis with JPEG file."""
        image_content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        files = {"file": ("test.jpg", io.BytesIO(image_content), "image/jpeg")}
        response = client.post("/api/multimodal/analyze", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.jpg"

    def test_analyze_non_image_file(self, client):
        """Test image analysis with non-image file."""
        files = {"file": ("test.txt", io.BytesIO(b"text content"), "text/plain")}
        response = client.post("/api/multimodal/analyze", files=files)
        assert response.status_code == 400
        data = response.json()
        assert "Only image files are allowed" in data["detail"]

    def test_analyze_image_no_content_type(self, client):
        """Test image analysis with file missing content type."""
        files = {"file": ("test.bin", io.BytesIO(b"binary content"), None)}
        response = client.post("/api/multimodal/analyze", files=files)
        assert response.status_code == 400

    def test_analyze_image_with_gif(self, client):
        """Test image analysis with GIF file."""
        files = {"file": ("test.gif", io.BytesIO(b"GIF89a" + b"\x00" * 100), "image/gif")}
        response = client.post("/api/multimodal/analyze", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.gif"
