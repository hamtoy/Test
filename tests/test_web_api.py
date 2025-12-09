"""Tests for the Web API module."""

from pathlib import Path
from unittest.mock import MagicMock

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


class TestOCREndpoint:
    """Test OCR endpoint."""

    def test_get_ocr_exists(self, client: TestClient, tmp_path: Path) -> None:
        """Test getting OCR text when file exists."""

        from src.config import AppConfig
        from src.web.routers import ocr as ocr_router_module

        # Create actual directory and file
        inputs_dir = tmp_path / "data" / "inputs"
        inputs_dir.mkdir(parents=True)
        (inputs_dir / "input_ocr.txt").write_text("Sample OCR Text", encoding="utf-8")

        mock_config = MagicMock(spec=AppConfig)
        mock_config.input_dir = inputs_dir
        ocr_router_module.set_dependencies(mock_config)

        response = client.get("/api/ocr")
        assert response.status_code == 200
        assert response.json() == {"ocr": "Sample OCR Text"}

    def test_get_ocr_missing(self, client: TestClient, tmp_path: Path) -> None:
        """Test getting OCR text when file is missing."""
        from src.config import AppConfig
        from src.web.routers import ocr as ocr_router_module

        # Create directory but not the file
        inputs_dir = tmp_path / "data" / "inputs"
        inputs_dir.mkdir(parents=True)

        mock_config = MagicMock(spec=AppConfig)
        mock_config.input_dir = inputs_dir
        ocr_router_module.set_dependencies(mock_config)

        response = client.get("/api/ocr")
        assert response.status_code == 404
        assert response.json() == {"detail": "OCR 파일이 없습니다."}


class TestQAGeneration:
    """Test QA generation endpoints."""

    @pytest.mark.skip(reason="Requires agent initialization with GEMINI_API_KEY")
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
        """Test single QA generation with invalid type returns 422 (Pydantic validation)."""
        payload = {"mode": "single", "qtype": "invalid_type"}
        response = client.post("/api/qa/generate", json=payload)
        # Pydantic returns 422 for validation errors
        assert response.status_code == 422

    @pytest.mark.skip(reason="Requires agent initialization with GEMINI_API_KEY")
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

    @pytest.mark.skip(reason="Requires agent initialization with GEMINI_API_KEY")
    def test_evaluate_external_valid(self, client: TestClient) -> None:
        """Test external evaluation with valid inputs (requires 3 answers)."""
        payload = {
            "query": "Test Query",
            "answers": ["Answer A", "Answer B", "Answer C"],
        }
        response = client.post("/api/eval/external", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 3
        assert data["best"] in ["A", "B", "C"]

    def test_evaluate_external_no_answers(self, client: TestClient) -> None:
        """Test external evaluation with no answers returns 422 (Pydantic validation)."""
        payload = {"query": "Test Query", "answers": []}
        response = client.post("/api/eval/external", json=payload)
        # Pydantic returns 422 for validation errors (requires exactly 3 answers)
        assert response.status_code == 422

    def test_evaluate_external_wrong_count_answers(self, client: TestClient) -> None:
        """Test external evaluation with wrong number of answers returns 422."""
        payload = {
            "query": "Test Query",
            "answers": ["Answer"] * 7,  # API requires exactly 3 answers
        }
        response = client.post("/api/eval/external", json=payload)
        # Pydantic returns 422 for validation errors
        assert response.status_code == 422


class TestWorkspace:
    """Test workspace endpoints."""

    @pytest.mark.skip(reason="Requires agent initialization with GEMINI_API_KEY")
    def test_workspace_inspect(self, client: TestClient) -> None:
        """Test workspace inspect mode."""
        payload = {"mode": "inspect", "answer": "Original Text"}
        response = client.post("/api/workspace", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["result"]["fixed"] is not None
        assert "[검수됨]" in data["result"]["fixed"]

    @pytest.mark.skip(reason="Requires agent initialization with GEMINI_API_KEY")
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

    @pytest.mark.skip(reason="Requires agent initialization with GEMINI_API_KEY")
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
        """Test workspace with invalid mode returns 422 (Pydantic validation)."""
        payload = {"mode": "invalid", "answer": "Original Text"}
        response = client.post("/api/workspace", json=payload)
        # Pydantic returns 422 for validation errors
        assert response.status_code == 422


class TestMultimodal:
    """Test multimodal endpoints."""

    @pytest.mark.skip(reason="Requires multimodal module initialization")
    def test_analyze_image_valid(self, client: TestClient) -> None:
        """Test image analysis with valid image."""
        file_content = b"fake image content"
        files = {"file": ("test.jpg", file_content, "image/jpeg")}
        response = client.post("/api/multimodal/analyze", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.jpg"
        assert data["metadata"]["has_table_chart"] is True

    @pytest.mark.skip(reason="Requires multimodal module initialization")
    def test_analyze_image_invalid_type(self, client: TestClient) -> None:
        """Test image analysis with non-image file."""
        file_content = b"text content"
        files = {"file": ("test.txt", file_content, "text/plain")}
        response = client.post("/api/multimodal/analyze", files=files)
        assert response.status_code == 400
        assert "Only image files are allowed" in response.json()["detail"]
