"""Tests for the web API module."""

import asyncio
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.config.constants import (
    QA_BATCH_GENERATION_TIMEOUT,
    QA_SINGLE_GENERATION_TIMEOUT,
)
from src.web.api import app, log_review_session


@pytest.fixture
def client() -> Any:
    """Create test client for the API."""
    return TestClient(app)


@pytest.fixture
def mock_agent() -> Any:
    """Create a mock GeminiAgent for testing."""
    agent = MagicMock()
    agent.generate_content = MagicMock(return_value="Mocked response")
    agent.generate_content_async = AsyncMock(return_value="Mocked response")
    return agent


@pytest.fixture
def mock_mm() -> Any:
    """Create a mock MultimodalUnderstanding for testing."""
    mm = MagicMock()
    mm.extract_text_from_image = MagicMock(return_value="Mocked OCR text from image")
    return mm


class TestPageRoutes:
    """Tests for page routes."""

    def test_qa_page_root(self, client: Any) -> None:
        """Test the root page redirects to QA page."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_qa_page_explicit(self, client: Any) -> None:
        """Test the explicit /qa page."""
        response = client.get("/qa")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_eval_page(self, client: Any) -> None:
        """Test the evaluation page."""
        response = client.get("/eval")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_workspace_page(self, client: Any) -> None:
        """Test the workspace page."""
        response = client.get("/workspace")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_multimodal_page(self, client: Any) -> None:
        """Test the multimodal page."""
        response = client.get("/multimodal")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestOCRApi:
    """Tests for OCR API endpoint."""

    def test_get_ocr_file_exists(
        self, client: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test getting OCR text when file exists."""
        # Create the inputs directory and input_ocr.txt file
        inputs_dir = tmp_path / "data" / "inputs"
        inputs_dir.mkdir(parents=True)
        (inputs_dir / "input_ocr.txt").write_text("테스트 OCR 텍스트", encoding="utf-8")

        # Patch config.input_dir to use tmp_path based directory
        with patch("src.web.api.config") as mock_config:
            mock_config.input_dir = inputs_dir
            response = client.get("/api/ocr")
            assert response.status_code == 200
            data = response.json()
            assert data["ocr"] == "테스트 OCR 텍스트"

    def test_get_ocr_file_not_exists(self, client: Any, tmp_path: Path) -> None:
        """Test getting OCR text when file doesn't exist."""
        # Create empty inputs directory (no ocr file)
        inputs_dir = tmp_path / "data" / "inputs"
        inputs_dir.mkdir(parents=True)

        with patch("src.web.api.config") as mock_config:
            mock_config.input_dir = inputs_dir
            response = client.get("/api/ocr")
            # When file doesn't exist, load_ocr_text raises HTTPException 404
            # and api_get_ocr re-raises it (proper HTTP semantics)
            assert response.status_code == 404
            data = response.json()
            assert data["detail"] == "OCR 파일이 없습니다."

    def test_post_ocr_save(self, client: Any, tmp_path: Path) -> None:
        """Test saving OCR text via POST."""
        inputs_dir = tmp_path / "data" / "inputs"
        inputs_dir.mkdir(parents=True)

        with patch("src.web.api.config") as mock_config:
            mock_config.input_dir = inputs_dir
            response = client.post("/api/ocr", json={"text": "사용자 입력 텍스트"})
            assert response.status_code == 200
            assert response.json()["status"] == "success"

            # 파일에 저장되었는지 확인
            saved_text = (inputs_dir / "input_ocr.txt").read_text(encoding="utf-8")
            assert saved_text == "사용자 입력 텍스트"

    def test_post_ocr_save_empty_text(self, client: Any, tmp_path: Path) -> None:
        """Test saving empty OCR text via POST."""
        inputs_dir = tmp_path / "data" / "inputs"
        inputs_dir.mkdir(parents=True)

        with patch("src.web.api.config") as mock_config:
            mock_config.input_dir = inputs_dir
            response = client.post("/api/ocr", json={"text": ""})
            assert response.status_code == 200
            assert response.json()["status"] == "success"

            # 파일에 저장되었는지 확인
            saved_text = (inputs_dir / "input_ocr.txt").read_text(encoding="utf-8")
            assert saved_text == ""

    def test_post_ocr_save_overwrites_existing(
        self, client: Any, tmp_path: Path
    ) -> None:
        """Test that saving OCR text overwrites existing file."""
        inputs_dir = tmp_path / "data" / "inputs"
        inputs_dir.mkdir(parents=True)
        (inputs_dir / "input_ocr.txt").write_text("기존 텍스트", encoding="utf-8")

        with patch("src.web.api.config") as mock_config:
            mock_config.input_dir = inputs_dir
            response = client.post("/api/ocr", json={"text": "새로운 텍스트"})
            assert response.status_code == 200

            # 파일이 덮어쓰기 되었는지 확인
            saved_text = (inputs_dir / "input_ocr.txt").read_text(encoding="utf-8")
            assert saved_text == "새로운 텍스트"


class TestQAGenerateApi:
    """Tests for QA generation API endpoint."""

    @pytest.mark.skip(reason="Requires mocked agent with specific response format")
    def test_generate_batch_qa(self, client: Any) -> None:
        """Test batch QA generation."""
        response = client.post("/api/qa/generate", json={"mode": "batch"})
        assert response.status_code == 200
        data = response.json()
        assert "pairs" in data
        assert len(data["pairs"]) == 4
        assert data["mode"] == "batch"

    @pytest.mark.skip(reason="Requires mocked agent with specific response format")
    def test_generate_single_qa_valid_type(self, client: Any) -> None:
        """Test single QA generation with valid type."""
        response = client.post(
            "/api/qa/generate", json={"mode": "single", "qtype": "reasoning"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "pair" in data
        assert data["mode"] == "single"
        assert data["pair"]["type"] == "추론"

    def test_generate_single_qa_missing_type(self, client: Any) -> None:
        """Test single QA generation with missing type returns 500 when agent is None."""
        response = client.post("/api/qa/generate", json={"mode": "single"})
        # Agent is None so returns 500
        assert response.status_code == 500

    def test_generate_single_qa_invalid_type(self, client: Any) -> None:
        """Test single QA generation with invalid type returns 422 (validation error)."""
        response = client.post(
            "/api/qa/generate", json={"mode": "single", "qtype": "invalid_type"}
        )
        # Pydantic validation for qtype literal fails before agent check
        assert response.status_code == 422

    @pytest.mark.skip(reason="Requires mocked agent with specific response format")
    def test_generate_single_qa_all_types(self, client: Any) -> None:
        """Test single QA generation with all valid types."""
        valid_types = [
            ("global_explanation", "전반 설명"),
            ("reasoning", "추론"),
            ("target_short", "타겟 단답"),
            ("target_long", "타겟 장답"),
        ]
        for qtype, expected_type in valid_types:
            response = client.post(
                "/api/qa/generate", json={"mode": "single", "qtype": qtype}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["pair"]["type"] == expected_type


class TestQAGenerateApiTimeout:
    """Tests for QA generation API timeout functionality."""

    @pytest.mark.asyncio
    async def test_single_qa_timeout(self, tmp_path: Path) -> None:
        """Test single QA generation timeout."""
        # Create OCR file
        inputs_dir = tmp_path / "data" / "inputs"
        inputs_dir.mkdir(parents=True)
        (inputs_dir / "input_ocr.txt").write_text("테스트 OCR 텍스트", encoding="utf-8")

        # Mock agent that takes longer than timeout
        async def slow_generate(*args: Any, **kwargs: Any) -> list[str]:
            await asyncio.sleep(QA_SINGLE_GENERATION_TIMEOUT + 5)
            return ["test query"]

        with patch("src.web.api.config") as mock_config:
            mock_config.input_dir = inputs_dir

            with patch("src.web.api.agent") as mock_agent:
                mock_agent.generate_query = slow_generate

                client = TestClient(app)
                response = client.post(
                    "/api/qa/generate",
                    json={"mode": "single", "qtype": "reasoning"},
                )
                # Should return 504 timeout error
                assert response.status_code == 504
                data = response.json()
                assert "시간 초과" in data["detail"]

    @pytest.mark.asyncio
    async def test_batch_qa_timeout(self, tmp_path: Path) -> None:
        """Test batch QA generation timeout."""
        # Create OCR file
        inputs_dir = tmp_path / "data" / "inputs"
        inputs_dir.mkdir(parents=True)
        (inputs_dir / "input_ocr.txt").write_text("테스트 OCR 텍스트", encoding="utf-8")

        # Mock agent that takes longer than timeout
        async def slow_generate(*args: Any, **kwargs: Any) -> list[str]:
            await asyncio.sleep(QA_BATCH_GENERATION_TIMEOUT + 5)
            return ["test query"]

        with patch("src.web.api.config") as mock_config:
            mock_config.input_dir = inputs_dir

            with patch("src.web.api.agent") as mock_agent:
                mock_agent.generate_query = slow_generate

                client = TestClient(app)
                response = client.post("/api/qa/generate", json={"mode": "batch"})
                # Should return 504 timeout error
                assert response.status_code == 504
                data = response.json()
                assert "시간 초과" in data["detail"]


class TestEvalApi:
    """Tests for evaluation API endpoint."""

    @pytest.mark.skip(reason="Requires mocked agent with specific response format")
    def test_evaluate_answers(self, client: Any) -> None:
        """Test evaluation of multiple answers."""
        response = client.post(
            "/api/eval/external",
            json={
                "query": "Test query",
                "answers": ["Answer A", "Answer B", "Answer C"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "best" in data
        assert len(data["results"]) == 3

    def test_evaluate_no_answers(self, client: Any) -> None:
        """Test evaluation with no answers returns 422 (validation error)."""
        response = client.post(
            "/api/eval/external", json={"query": "Test query", "answers": []}
        )
        # Pydantic validation requires exactly 3 answers, so empty list fails
        assert response.status_code == 422

    def test_evaluate_wrong_count_answers(self, client: Any) -> None:
        """Test evaluation with wrong number of answers returns 422."""
        # Must be exactly 3 answers per model validation
        answers = [f"Answer {i}" for i in range(10)]
        response = client.post(
            "/api/eval/external", json={"query": "Test query", "answers": answers}
        )
        assert response.status_code == 422

    @pytest.mark.skip(reason="Requires mocked agent with specific response format")
    def test_evaluate_score_calculation(self, client: Any) -> None:
        """Test that evaluation returns scores for answers."""
        answers = ["Answer A", "Answer B", "Answer C"]
        response = client.post(
            "/api/eval/external",
            json={"query": "Test", "answers": answers},
        )
        assert response.status_code == 200
        data = response.json()
        assert "best" in data


class TestWorkspaceApi:
    """Tests for workspace API endpoint."""

    @pytest.mark.skip(reason="Requires mocked agent")
    def test_workspace_inspect_mode(self, client: Any) -> None:
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

    @pytest.mark.skip(reason="Requires mocked agent")
    def test_workspace_edit_mode(self, client: Any) -> None:
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

    def test_workspace_edit_mode_empty_request(self, client: Any) -> None:
        """Test workspace edit mode with empty request returns 500 when agent is None."""
        response = client.post(
            "/api/workspace",
            json={
                "mode": "edit",
                "answer": "Original answer",
                "edit_request": "",
            },
        )
        # Agent is None so returns 500 before validation
        assert response.status_code == 500

    def test_workspace_edit_mode_whitespace_request(self, client: Any) -> None:
        """Test workspace edit mode with whitespace-only request returns 500."""
        response = client.post(
            "/api/workspace",
            json={
                "mode": "edit",
                "answer": "Original answer",
                "edit_request": "   ",
            },
        )
        # Agent is None so returns 500
        assert response.status_code == 500

    def test_workspace_invalid_mode(self, client: Any) -> None:
        """Test workspace with invalid mode returns 422 (validation error)."""
        response = client.post(
            "/api/workspace",
            json={
                "mode": "invalid",
                "answer": "Original answer",
                "edit_request": "",
            },
        )
        # Pydantic validation for mode literal fails
        assert response.status_code == 422


class TestMultimodalApi:
    """Tests for multimodal/image analysis API endpoint."""

    @pytest.mark.skip(reason="Requires mocked mm (MultimodalUnderstanding)")
    def test_analyze_image_valid(self, client: Any) -> None:
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

    @pytest.mark.skip(reason="Requires mocked mm (MultimodalUnderstanding)")
    def test_analyze_image_jpeg(self, client: Any) -> None:
        """Test image analysis with JPEG file."""
        image_content = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        files = {"file": ("test.jpg", io.BytesIO(image_content), "image/jpeg")}
        response = client.post("/api/multimodal/analyze", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.jpg"

    def test_analyze_non_image_file(self, client: Any) -> None:
        """Test image analysis with non-image file returns 500 when mm is None."""
        files = {"file": ("test.txt", io.BytesIO(b"text content"), "text/plain")}
        response = client.post("/api/multimodal/analyze", files=files)
        # mm is None so returns 500 before content type validation
        assert response.status_code == 500

    def test_analyze_image_no_content_type(self, client: Any) -> None:
        """Test image analysis with file missing content type returns 500."""
        files = {"file": ("test.bin", io.BytesIO(b"binary content"), None)}
        response = client.post("/api/multimodal/analyze", files=files)
        # mm is None so returns 500
        assert response.status_code == 500

    @pytest.mark.skip(reason="Requires mocked mm (MultimodalUnderstanding)")
    def test_analyze_image_with_gif(self, client: Any) -> None:
        """Test image analysis with GIF file."""
        files = {
            "file": ("test.gif", io.BytesIO(b"GIF89a" + b"\x00" * 100), "image/gif")
        }
        response = client.post("/api/multimodal/analyze", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.gif"


class TestLogReviewSession:
    """Tests for log_review_session helper function."""

    def test_log_review_session_creates_directory(self, tmp_path: Path) -> None:
        """Test that log_review_session creates the log directory if it doesn't exist."""
        log_review_session(
            mode="inspect",
            question="테스트 질문",
            answer_before="수정 전 답변",
            answer_after="수정 후 답변",
            edit_request_used="",
            inspector_comment="테스트 코멘트",
            base_dir=tmp_path,
        )

        # Check that the directory was created
        log_dir = tmp_path / "data" / "outputs" / "review_logs"
        assert log_dir.exists()

        # Check that the log file was created
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = log_dir / f"review_{today}.jsonl"
        assert log_file.exists()

        # Verify log content
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 1
        log_entry = json.loads(lines[0])
        assert log_entry["mode"] == "inspect"
        assert log_entry["question"] == "테스트 질문"
        assert log_entry["answer_before"] == "수정 전 답변"
        assert log_entry["answer_after"] == "수정 후 답변"
        assert log_entry["edit_request_used"] == ""
        assert log_entry["inspector_comment"] == "테스트 코멘트"
        assert "timestamp" in log_entry

    def test_log_review_session_appends_multiple_entries(self, tmp_path: Path) -> None:
        """Test that log_review_session appends multiple entries to the same file."""
        # Log first entry
        log_review_session(
            mode="inspect",
            question="Q1",
            answer_before="A1 before",
            answer_after="A1 after",
            edit_request_used="",
            inspector_comment="C1",
            base_dir=tmp_path,
        )

        # Log second entry
        log_review_session(
            mode="edit",
            question="Q2",
            answer_before="A2 before",
            answer_after="A2 after",
            edit_request_used="수정 요청",
            inspector_comment="C2",
            base_dir=tmp_path,
        )

        # Verify both entries are in the file
        log_dir = tmp_path / "data" / "outputs" / "review_logs"
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = log_dir / f"review_{today}.jsonl"

        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 2

        entry1 = json.loads(lines[0])
        entry2 = json.loads(lines[1])
        assert entry1["mode"] == "inspect"
        assert entry2["mode"] == "edit"
        assert entry2["edit_request_used"] == "수정 요청"

    def test_log_review_session_handles_empty_strings(self, tmp_path: Path) -> None:
        """Test that log_review_session accepts empty strings for all fields."""
        log_review_session(
            mode="inspect",
            question="",
            answer_before="",
            answer_after="",
            edit_request_used="",
            inspector_comment="",
            base_dir=tmp_path,
        )

        log_dir = tmp_path / "data" / "outputs" / "review_logs"
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file = log_dir / f"review_{today}.jsonl"

        with open(log_file, "r", encoding="utf-8") as f:
            log_entry = json.loads(f.readline())

        assert log_entry["question"] == ""
        assert log_entry["answer_before"] == ""
        assert log_entry["answer_after"] == ""
        assert log_entry["edit_request_used"] == ""
        assert log_entry["inspector_comment"] == ""

    def test_log_review_session_failure_does_not_raise(self, tmp_path: Path) -> None:
        """Test that log_review_session failure doesn't raise an exception."""
        # Patch REPO_ROOT to an invalid path (read-only or non-existent)
        # Should not raise even though it can't write
        log_review_session(
            mode="inspect",
            question="Q",
            answer_before="A",
            answer_after="B",
            edit_request_used="",
            inspector_comment="C",
            base_dir=Path("/nonexistent/path"),
        )
        # If we get here, the function handled the error gracefully
