"""Tests for the unified workspace functionality."""

from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.web.api import app, detect_workflow


@pytest.fixture
def client() -> Any:
    """Create test client for the API."""
    return TestClient(app)


class TestDetectWorkflow:
    """Tests for the detect_workflow function."""

    def test_full_generation_both_empty(self) -> None:
        """Test full_generation workflow when both query and answer are empty."""
        result = detect_workflow("", "", "")
        assert result == "full_generation"

        result = detect_workflow(None, None, None)
        assert result == "full_generation"

        result = detect_workflow("   ", "   ", "")
        assert result == "full_generation"

    def test_query_generation_answer_only(self) -> None:
        """Test query_generation workflow when only answer is provided."""
        result = detect_workflow("", "Some answer", "")
        assert result == "query_generation"

        result = detect_workflow(None, "Some answer", None)
        assert result == "query_generation"

    def test_answer_generation_query_only(self) -> None:
        """Test answer_generation workflow when only query is provided."""
        result = detect_workflow("Some query", "", "")
        assert result == "answer_generation"

        result = detect_workflow("Some query", None, None)
        assert result == "answer_generation"

    def test_rewrite_both_no_edit(self) -> None:
        """Test rewrite workflow when both query and answer provided without edit request."""
        result = detect_workflow("Some query", "Some answer", "")
        assert result == "rewrite"

        result = detect_workflow("Some query", "Some answer", None)
        assert result == "rewrite"

    def test_edit_query_with_edit_request(self) -> None:
        """Test edit_query workflow when query and edit_request provided."""
        result = detect_workflow("Some query", "", "Make it better")
        assert result == "edit_query"

        result = detect_workflow("Some query", None, "Make it better")
        assert result == "edit_query"

    def test_edit_answer_with_edit_request(self) -> None:
        """Test edit_answer workflow when answer and edit_request provided."""
        result = detect_workflow("", "Some answer", "Make it better")
        assert result == "edit_answer"

        result = detect_workflow(None, "Some answer", "Make it better")
        assert result == "edit_answer"

    def test_edit_both_with_edit_request(self) -> None:
        """Test edit_both workflow when query, answer and edit_request provided."""
        result = detect_workflow("Some query", "Some answer", "Make both better")
        assert result == "edit_both"


class TestUnifiedWorkspaceAPI:
    """Tests for the /api/workspace/unified endpoint."""

    @pytest.fixture
    def mock_agent(self) -> Any:
        """Create a mock GeminiAgent for testing."""
        agent = MagicMock()
        agent.generate_query = AsyncMock(return_value=["Generated query"])
        agent.rewrite_best_answer = AsyncMock(return_value="Generated answer")
        return agent

    @pytest.fixture
    def setup_mocks(
        self, mock_agent: Any, tmp_path: Any
    ) -> Generator[None, None, None]:
        """Set up common mocks for testing."""
        # Setup OCR file
        inputs_dir = tmp_path / "data" / "inputs"
        inputs_dir.mkdir(parents=True)
        (inputs_dir / "input_ocr.txt").write_text("Test OCR text", encoding="utf-8")

        with patch("src.web.api.config") as mock_config:
            mock_config.input_dir = inputs_dir

        # Patch agent and kg
        with patch("src.web.api.agent", mock_agent), patch("src.web.api.kg", None):
            yield

    def test_unified_workspace_full_generation(
        self, client: Any, mock_agent: Any, tmp_path: Any
    ) -> None:
        """Test full_generation workflow."""
        inputs_dir = tmp_path / "data" / "inputs"
        inputs_dir.mkdir(parents=True)
        (inputs_dir / "input_ocr.txt").write_text("Test OCR text", encoding="utf-8")

        with (
            patch("src.web.api.config") as mock_config,
            patch("src.web.api.agent", mock_agent),
            patch("src.web.api.kg", None),
            patch("src.web.api.DEFAULT_ANSWER_RULES", ["Rule 1"]),
        ):
            mock_config.input_dir = inputs_dir
            response = client.post(
                "/api/workspace/unified",
                json={"query": "", "answer": "", "edit_request": ""},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["workflow"] == "full_generation"
            assert "query" in data
            assert "answer" in data
            assert "changes" in data

    def test_unified_workspace_query_generation(
        self, client: Any, mock_agent: Any, tmp_path: Any
    ) -> None:
        """Test query_generation workflow."""
        inputs_dir = tmp_path / "data" / "inputs"
        inputs_dir.mkdir(parents=True)
        (inputs_dir / "input_ocr.txt").write_text("Test OCR text", encoding="utf-8")

        with patch("src.web.api.config") as mock_config:
            mock_config.input_dir = inputs_dir
            with patch("src.web.api.agent", mock_agent), patch("src.web.api.kg", None):
                response = client.post(
                    "/api/workspace/unified",
                    json={
                        "query": "",
                        "answer": "Test answer",
                        "edit_request": "",
                    },
                )

                assert response.status_code == 200
                data = response.json()
                assert data["workflow"] == "query_generation"
                assert data["query"] == "Generated query"
                assert data["answer"] == "Test answer"

    def test_unified_workspace_answer_generation(
        self, client: Any, mock_agent: Any, tmp_path: Any
    ) -> None:
        """Test answer_generation workflow."""
        inputs_dir = tmp_path / "data" / "inputs"
        inputs_dir.mkdir(parents=True)
        (inputs_dir / "input_ocr.txt").write_text("Test OCR text", encoding="utf-8")

        with (
            patch("src.web.api.config") as mock_config,
            patch("src.web.api.agent", mock_agent),
            patch("src.web.api.kg", None),
            patch("src.web.api.DEFAULT_ANSWER_RULES", ["Rule 1"]),
            patch("src.web.api.find_violations", return_value=[]),
        ):
            mock_config.input_dir = inputs_dir
            response = client.post(
                "/api/workspace/unified",
                json={
                    "query": "Test query",
                    "answer": "",
                    "edit_request": "",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["workflow"] == "answer_generation"
            assert data["query"] == "Test query"
            assert data["answer"] == "Generated answer"

    def test_unified_workspace_edit_query(
        self, client: Any, mock_agent: Any, tmp_path: Any
    ) -> None:
        """Test edit_query workflow."""
        inputs_dir = tmp_path / "data" / "inputs"
        inputs_dir.mkdir(parents=True)
        (inputs_dir / "input_ocr.txt").write_text("Test OCR text", encoding="utf-8")

        mock_edit_content = AsyncMock(return_value="Edited query")

        with (
            patch("src.web.api.config") as mock_config,
            patch("src.web.api.agent", mock_agent),
            patch("src.web.api.kg", None),
            patch("src.web.routers.workspace.edit_content", mock_edit_content),
        ):
            mock_config.input_dir = inputs_dir
            response = client.post(
                "/api/workspace/unified",
                json={
                    "query": "Original query",
                    "answer": "",
                    "edit_request": "Make it better",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["workflow"] == "edit_query"
            assert data["query"] == "Edited query"
            assert "질의 수정 완료" in data["changes"]

    def test_unified_workspace_edit_answer(
        self, client: Any, mock_agent: Any, tmp_path: Any
    ) -> None:
        """Test edit_answer workflow."""
        inputs_dir = tmp_path / "data" / "inputs"
        inputs_dir.mkdir(parents=True)
        (inputs_dir / "input_ocr.txt").write_text("Test OCR text", encoding="utf-8")

        mock_edit_content = AsyncMock(return_value="Edited answer")

        with (
            patch("src.web.api.config") as mock_config,
            patch("src.web.api.agent", mock_agent),
            patch("src.web.api.kg", None),
            patch("src.web.routers.workspace.edit_content", mock_edit_content),
        ):
            mock_config.input_dir = inputs_dir
            response = client.post(
                "/api/workspace/unified",
                json={
                    "query": "",
                    "answer": "Original answer",
                    "edit_request": "Make it better",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["workflow"] == "edit_answer"
            assert data["answer"] == "Edited answer"
            assert "답변 수정 완료" in data["changes"]

    def test_unified_workspace_edit_both(
        self, client: Any, mock_agent: Any, tmp_path: Any
    ) -> None:
        """Test edit_both workflow."""
        inputs_dir = tmp_path / "data" / "inputs"
        inputs_dir.mkdir(parents=True)
        (inputs_dir / "input_ocr.txt").write_text("Test OCR text", encoding="utf-8")

        mock_edit_content = AsyncMock(side_effect=["Edited answer", "Edited query"])

        with (
            patch("src.web.api.config") as mock_config,
            patch("src.web.api.agent", mock_agent),
            patch("src.web.api.kg", None),
            patch("src.web.routers.workspace.edit_content", mock_edit_content),
        ):
            mock_config.input_dir = inputs_dir
            response = client.post(
                "/api/workspace/unified",
                json={
                    "query": "Original query",
                    "answer": "Original answer",
                    "edit_request": "Make both better",
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["workflow"] == "edit_both"
            assert data["query"] == "Edited query"
            assert data["answer"] == "Edited answer"
            assert "답변 수정 완료" in data["changes"]
            assert "질의 조정 완료" in data["changes"]

    def test_unified_workspace_rewrite(
        self, client: Any, mock_agent: Any, tmp_path: Any
    ) -> None:
        """Test rewrite workflow."""
        inputs_dir = tmp_path / "data" / "inputs"
        inputs_dir.mkdir(parents=True)
        (inputs_dir / "input_ocr.txt").write_text("Test OCR text", encoding="utf-8")

        mock_inspect_answer = AsyncMock(return_value="Inspected answer")

        with (
            patch("src.web.api.config") as mock_config,
            patch("src.web.api.agent", mock_agent),
            patch("src.web.api.kg", None),
            patch("src.web.routers.workspace.edit_content", mock_inspect_answer),
        ):
            mock_config.input_dir = inputs_dir
            response = client.post(
                "/api/workspace/unified",
                json={
                    "query": "Test query",
                    "answer": "Test answer",
                    "edit_request": "",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["workflow"] == "rewrite"
            assert data["answer"] == "Inspected answer"
            assert "재작성 완료" in data["changes"]

    def test_unified_workspace_agent_not_initialized(self, client: Any) -> None:
        """Test unified workspace when agent is not initialized."""
        with patch("src.web.api.agent", None):
            response = client.post(
                "/api/workspace/unified",
                json={"query": "", "answer": "", "edit_request": ""},
            )

            assert response.status_code == 500
            assert "Agent 초기화 실패" in response.json()["detail"]
