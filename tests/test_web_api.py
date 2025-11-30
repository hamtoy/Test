"""Tests for the Web API module."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.web.api import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client."""
    return TestClient(app)


class TestPageRoutes:
    """Test HTML page routes."""

    def test_root_page(self, client: TestClient) -> None:
        """Test root page."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_qa_page(self, client: TestClient) -> None:
        """Test QA page."""
        response = client.get("/qa")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_eval_page(self, client: TestClient) -> None:
        """Test evaluation page."""
        response = client.get("/eval")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_workspace_page(self, client: TestClient) -> None:
        """Test workspace page."""
        response = client.get("/workspace")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_multimodal_page(self, client: TestClient) -> None:
        """Test multimodal page."""
        response = client.get("/multimodal")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestOCREndpoint:
    """Test OCR endpoint."""

    def test_get_ocr_exists(self, client: TestClient) -> None:
        """Test getting OCR text when file exists."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = "Sample OCR Text"

        mock_input_dir = MagicMock()
        mock_input_dir.__truediv__.return_value = mock_path

        with patch("src.web.api.config") as mock_config:
            mock_config.input_dir = mock_input_dir
            response = client.get("/api/ocr")
            assert response.status_code == 200
            assert response.json() == {"ocr": "Sample OCR Text"}

    def test_get_ocr_missing(self, client: TestClient) -> None:
        """Test getting OCR text when file is missing."""
        mock_path = MagicMock()
        mock_path.exists.return_value = False

        mock_input_dir = MagicMock()
        mock_input_dir.__truediv__.return_value = mock_path

        with patch("src.web.api.config") as mock_config:
            mock_config.input_dir = mock_input_dir
            response = client.get("/api/ocr")
            assert response.status_code == 200
            assert response.json() == {"ocr": "", "error": "OCR 파일이 없습니다."}


class TestQAGeneration:
    """Test QA generation endpoints."""

    def test_generate_single_valid(self, client: TestClient) -> None:
        """Test single QA generation with valid type."""
        payload = {"mode": "single", "qtype": "reasoning"}
        response = client.post("/api/qa/generate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "single"
        assert data["pair"]["type"] == "추론"
        assert "샘플 질의" in data["pair"]["query"]

    def test_generate_single_invalid_type(self, client: TestClient) -> None:
        """Test single QA generation with invalid type."""
        payload = {"mode": "single", "qtype": "invalid_type"}
        response = client.post("/api/qa/generate", json=payload)
        assert response.status_code == 400
        assert "Invalid question type" in response.json()["detail"]

    def test_generate_batch(self, client: TestClient) -> None:
        """Test batch QA generation."""
        payload = {"mode": "batch"}
        response = client.post("/api/qa/generate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "batch"
        assert len(data["pairs"]) == 4  # 4 types defined in mock


class TestEvaluation:
    """Test evaluation endpoints."""

    def test_evaluate_external_valid(self, client: TestClient) -> None:
        """Test external evaluation with valid inputs."""
        payload = {"query": "Test Query", "answers": ["Answer A", "Answer B"]}
        response = client.post("/api/eval/external", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 2
        assert data["best"] in ["A", "B"]

    def test_evaluate_external_no_answers(self, client: TestClient) -> None:
        """Test external evaluation with no answers."""
        payload = {"query": "Test Query", "answers": []}
        response = client.post("/api/eval/external", json=payload)
        assert response.status_code == 400
        assert "No answers provided" in response.json()["detail"]

    def test_evaluate_external_too_many_answers(self, client: TestClient) -> None:
        """Test external evaluation with more answers than labels."""
        payload = {
            "query": "Test Query",
            "answers": ["Answer"] * 7,  # 7 answers, but only 6 labels
        }
        response = client.post("/api/eval/external", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 6  # Should be capped at 6


class TestWorkspace:
    """Test workspace endpoints."""

    def test_workspace_inspect(self, client: TestClient) -> None:
        """Test workspace inspect mode."""
        payload = {"mode": "inspect", "answer": "Original Text"}
        response = client.post("/api/workspace", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["fixed"] is not None
        assert "[검수됨]" in data["result"]["fixed"]

    def test_workspace_edit(self, client: TestClient) -> None:
        """Test workspace edit mode."""
        payload = {
            "mode": "edit",
            "answer": "Original Text",
            "edit_request": "Make it shorter",
        }
        response = client.post("/api/workspace", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["edited"] is not None
        assert "수정됨" in data["result"]["edited"]

    def test_workspace_edit_missing_request(self, client: TestClient) -> None:
        """Test workspace edit mode without edit request."""
        payload = {
            "mode": "edit",
            "answer": "Original Text",
            "edit_request": "   ",  # Empty string
        }
        response = client.post("/api/workspace", json=payload)
        assert response.status_code == 400
        assert "Edit request is required" in response.json()["detail"]

    def test_workspace_invalid_mode(self, client: TestClient) -> None:
        """Test workspace with invalid mode."""
        payload = {"mode": "invalid", "answer": "Original Text"}
        response = client.post("/api/workspace", json=payload)
        assert response.status_code == 400
        assert "Invalid mode" in response.json()["detail"]


class TestMultimodal:
    """Test multimodal endpoints."""

    def test_analyze_image_valid(self, client: TestClient) -> None:
        """Test image analysis with valid image."""
        file_content = b"fake image content"
        files = {"file": ("test.jpg", file_content, "image/jpeg")}
        response = client.post("/api/multimodal/analyze", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.jpg"
        assert data["metadata"]["has_table_chart"] is True

    def test_analyze_image_invalid_type(self, client: TestClient) -> None:
        """Test image analysis with non-image file."""
        file_content = b"text content"
        files = {"file": ("test.txt", file_content, "text/plain")}
        response = client.post("/api/multimodal/analyze", files=files)
        assert response.status_code == 400
        assert "Only image files are allowed" in response.json()["detail"]
