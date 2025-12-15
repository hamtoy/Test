"""Tests for analysis router."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    from src.web.api import app

    return TestClient(app)


class TestSemanticAnalysisEndpoint:
    """Tests for /api/analysis/semantic endpoint."""

    def test_semantic_missing_credentials(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test semantic analysis fails without Neo4j credentials."""
        monkeypatch.delenv("NEO4J_URI", raising=False)
        monkeypatch.delenv("NEO4J_USER", raising=False)
        monkeypatch.delenv("NEO4J_PASSWORD", raising=False)

        response = client.post("/api/analysis/semantic")
        assert response.status_code == 500
        assert "Neo4j credentials" in response.json()["detail"]

    def test_semantic_success(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test successful semantic analysis."""
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "password")

        mock_driver = MagicMock()
        mock_blocks = [
            {"id": "1", "content": "test content keyword"},
            {"id": "2", "content": "another test"},
        ]
        mock_counter = MagicMock()
        mock_counter.most_common.return_value = [("keyword", 3), ("test", 2)]

        with patch("neo4j.GraphDatabase.driver", return_value=mock_driver):
            with patch("src.analysis.semantic.fetch_blocks", return_value=mock_blocks):
                with patch(
                    "src.analysis.semantic.count_keywords", return_value=mock_counter
                ):
                    with patch("src.analysis.semantic.create_topics"):
                        with patch("src.analysis.semantic.link_blocks_to_topics"):
                            response = client.post(
                                "/api/analysis/semantic", params={"top_k": 10}
                            )

                            assert response.status_code == 200
                            data = response.json()
                            assert data["status"] == "success"

    def test_semantic_no_blocks(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test semantic analysis with no blocks."""
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "password")

        mock_driver = MagicMock()

        with patch("neo4j.GraphDatabase.driver", return_value=mock_driver):
            with patch("src.analysis.semantic.fetch_blocks", return_value=[]):
                response = client.post("/api/analysis/semantic")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "no_data"

    def test_semantic_exception(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test semantic analysis handles exceptions."""
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "password")

        with patch(
            "neo4j.GraphDatabase.driver", side_effect=Exception("Connection failed")
        ):
            response = client.post("/api/analysis/semantic")
            assert response.status_code == 500


class TestDocumentCompareEndpoint:
    """Tests for /api/analysis/document-compare endpoint."""

    def test_document_compare_missing_credentials(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test document compare fails without Neo4j credentials."""
        monkeypatch.delenv("NEO4J_URI", raising=False)
        monkeypatch.delenv("NEO4J_USER", raising=False)
        monkeypatch.delenv("NEO4J_PASSWORD", raising=False)

        response = client.get("/api/analysis/document-compare")
        assert response.status_code == 500

    def test_document_compare_success(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test successful document comparison."""
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "password")

        mock_driver = MagicMock()
        mock_structures = [{"title": "Page 1", "total": 5, "types": ["paragraph"]}]
        mock_commons = [("Common content", ["Page 1", "Page 2"])]

        with patch("neo4j.GraphDatabase.driver", return_value=mock_driver):
            with patch(
                "src.analysis.document_compare.compare_structure",
                return_value=mock_structures,
            ):
                with patch(
                    "src.analysis.document_compare.find_common_content",
                    return_value=mock_commons,
                ):
                    response = client.get("/api/analysis/document-compare")

                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == "success"

    def test_document_compare_exception(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test document compare handles exceptions."""
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "password")

        with patch(
            "neo4j.GraphDatabase.driver", side_effect=Exception("Database error")
        ):
            response = client.get("/api/analysis/document-compare")
            assert response.status_code == 500


class TestPromoteRulesEndpoint:
    """Tests for /api/analysis/promote-rules endpoint."""

    def test_promote_rules_success(self, client: TestClient) -> None:
        """Test successful rule promotion."""
        mock_rules = [{"rule": "Use ISO date format", "type_hint": "date"}]

        with patch(
            "src.automation.promote_rules.run_promote_rules", return_value=mock_rules
        ):
            response = client.post("/api/analysis/promote-rules", params={"days": 7})

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"

    def test_promote_rules_empty(self, client: TestClient) -> None:
        """Test rule promotion with no rules found."""
        with patch("src.automation.promote_rules.run_promote_rules", return_value=[]):
            response = client.post("/api/analysis/promote-rules")

            assert response.status_code == 200
            data = response.json()
            assert data["rules_suggested"] == 0

    def test_promote_rules_os_error(self, client: TestClient) -> None:
        """Test rule promotion handles OSError."""
        with patch(
            "src.automation.promote_rules.run_promote_rules",
            side_effect=OSError("File not found"),
        ):
            response = client.post("/api/analysis/promote-rules")
            assert response.status_code == 500

    def test_promote_rules_exception(self, client: TestClient) -> None:
        """Test rule promotion handles general exceptions."""
        with patch(
            "src.automation.promote_rules.run_promote_rules",
            side_effect=Exception("LLM error"),
        ):
            response = client.post("/api/analysis/promote-rules")
            assert response.status_code == 500
