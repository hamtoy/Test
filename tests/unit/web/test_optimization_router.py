"""Tests for optimization router."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    from src.web.api import app

    return TestClient(app)


class TestAnalyzeEndpoint:
    """Tests for /api/optimization/analyze endpoint."""

    def test_analyze_success(self, client: TestClient) -> None:
        """Test successful analysis trigger."""
        mock_report = {
            "trends": {"accuracy": "improving"},
            "suggestions": ["optimize prompts"],
            "issues": [],
        }

        from unittest.mock import AsyncMock

        with patch(
            "src.web.routers.optimization.SelfImprovingSystem"
        ) as mock_system_cls:
            mock_instance = MagicMock()
            mock_instance.analyze_and_suggest = AsyncMock(return_value=mock_report)
            mock_system_cls.return_value = mock_instance

            response = client.post("/api/optimization/analyze")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"

    def test_analyze_exception(self, client: TestClient) -> None:
        """Test analysis handles exceptions."""
        with patch(
            "src.web.routers.optimization.SelfImprovingSystem"
        ) as mock_system_cls:
            mock_instance = MagicMock()
            mock_instance.analyze_and_suggest = MagicMock(
                side_effect=Exception("Analysis failed")
            )
            mock_system_cls.return_value = mock_instance

            response = client.post("/api/optimization/analyze")
            assert response.status_code == 500
            assert "Analysis failed" in response.json()["detail"]


class TestSuggestionsEndpoint:
    """Tests for /api/optimization/suggestions endpoint."""

    def test_suggestions_no_file(self, client: TestClient, tmp_path: Path) -> None:
        """Test suggestions when file doesn't exist."""
        with patch(
            "src.web.routers.optimization.SelfImprovingSystem"
        ) as mock_system_cls:
            mock_instance = MagicMock()
            mock_instance.suggestions_file = tmp_path / "nonexistent.json"
            mock_system_cls.return_value = mock_instance

            response = client.get("/api/optimization/suggestions")

            assert response.status_code == 200
            data = response.json()
            assert data["suggestions"] == []
            assert data["timestamp"] is None

    def test_suggestions_with_file(self, client: TestClient, tmp_path: Path) -> None:
        """Test suggestions when file exists."""
        suggestions_file = tmp_path / "suggestions.json"
        suggestions_data = {
            "suggestions": [{"id": 1, "text": "Improve prompt"}],
            "timestamp": "2024-01-01T00:00:00",
        }
        suggestions_file.write_text(
            '{"suggestions": [{"id": 1, "text": "Improve prompt"}], "timestamp": "2024-01-01T00:00:00"}',
            encoding="utf-8",
        )

        with patch(
            "src.web.routers.optimization.SelfImprovingSystem"
        ) as mock_system_cls:
            mock_instance = MagicMock()
            mock_instance.suggestions_file = suggestions_file
            mock_system_cls.return_value = mock_instance

            response = client.get("/api/optimization/suggestions")

            assert response.status_code == 200
            data = response.json()
            assert len(data["suggestions"]) == 1
            assert data["timestamp"] == "2024-01-01T00:00:00"

    def test_suggestions_invalid_json(self, client: TestClient, tmp_path: Path) -> None:
        """Test suggestions handles invalid JSON."""
        suggestions_file = tmp_path / "suggestions.json"
        suggestions_file.write_text("invalid json{", encoding="utf-8")

        with patch(
            "src.web.routers.optimization.SelfImprovingSystem"
        ) as mock_system_cls:
            mock_instance = MagicMock()
            mock_instance.suggestions_file = suggestions_file
            mock_system_cls.return_value = mock_instance

            response = client.get("/api/optimization/suggestions")
            assert response.status_code == 500

    def test_suggestions_read_error(self, client: TestClient, tmp_path: Path) -> None:
        """Test suggestions handles read errors."""
        with patch(
            "src.web.routers.optimization.SelfImprovingSystem"
        ) as mock_system_cls:
            mock_instance = MagicMock()
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.read_text.side_effect = OSError("Permission denied")
            mock_instance.suggestions_file = mock_file
            mock_system_cls.return_value = mock_instance

            response = client.get("/api/optimization/suggestions")
            assert response.status_code == 500
