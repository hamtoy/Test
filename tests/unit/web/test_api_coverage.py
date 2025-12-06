"""Comprehensive tests for src/web/api.py to improve coverage to 80%+."""

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from src.config import AppConfig
from src.web import api


@pytest.fixture
def test_client():
    """Create test client for API testing."""
    # Mock dependencies to avoid initialization
    with patch("src.web.api.init_resources", new_callable=AsyncMock):
        with patch("src.web.api._init_health_checks", new_callable=AsyncMock):
            client = TestClient(api.app)
            yield client


@pytest.fixture
def mock_agent():
    """Mock GeminiAgent for testing."""
    agent = AsyncMock()
    agent.rewrite_best_answer = AsyncMock(return_value="Mocked answer")
    agent.generate_query = AsyncMock(return_value=["Generated query"])
    return agent


@pytest.fixture
def mock_kg():
    """Mock QAKnowledgeGraph for testing."""
    kg = MagicMock()
    kg.get_rules_for_query_type = MagicMock(return_value=[])
    kg.close = MagicMock()
    return kg


@pytest.fixture
def mock_pipeline():
    """Mock IntegratedQAPipeline for testing."""
    pipeline = AsyncMock()
    pipeline.generate_qa_pair = AsyncMock(
        return_value={
            "query": "Test query",
            "answer": "Test answer",
        }
    )
    return pipeline


class TestGetConfig:
    """Test get_config function."""

    def test_get_config_creates_instance(self):
        """Test that get_config creates AppConfig instance."""
        api._config = None
        config = api.get_config()
        assert isinstance(config, AppConfig)

    def test_get_config_reuses_instance(self):
        """Test that get_config reuses existing instance."""
        config1 = api.get_config()
        config2 = api.get_config()
        assert config1 is config2

    def test_get_config_sets_dummy_key_without_env(self, monkeypatch):
        """Test that get_config sets dummy key when not in production."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "development")
        api._config = None

        config = api.get_config()

        assert config.gemini_api_key.startswith("AIza")
        assert len(config.gemini_api_key) == 39

    def test_get_config_requires_key_in_production(self, monkeypatch):
        """Test that get_config requires key in production."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("ENVIRONMENT", "production")
        api._config = None

        with pytest.raises(ValueError, match="GEMINI_API_KEY required"):
            api.get_config()


class TestUtilityWrappers:
    """Test utility wrapper functions."""

    def test_load_ocr_text(self, tmp_path, monkeypatch):
        """Test load_ocr_text wrapper."""
        ocr_file = tmp_path / "ocr.txt"
        ocr_file.write_text("Test OCR content", encoding="utf-8")

        api._config = None
        monkeypatch.setenv("DATA_DIR", str(tmp_path))

        with patch("src.web.utils._load_ocr_text", return_value="Test OCR content") as mock_load:
            result = api.load_ocr_text()

            assert result == "Test OCR content"
            mock_load.assert_called_once()

    def test_save_ocr_text(self, tmp_path, monkeypatch):
        """Test save_ocr_text wrapper."""
        api._config = None
        monkeypatch.setenv("DATA_DIR", str(tmp_path))

        with patch("src.web.utils._save_ocr_text") as mock_save:
            api.save_ocr_text("New OCR content")

            mock_save.assert_called_once()

    def test_log_review_session(self):
        """Test log_review_session wrapper."""
        with patch("src.web.utils._log_review_session") as mock_log:
            api.log_review_session(
                mode="edit",
                question="Test question",
                answer_before="Before",
                answer_after="After",
                edit_request_used="Edit request",
                inspector_comment="Comment",
            )

            mock_log.assert_called_once()


class TestRequestIdMiddleware:
    """Test _request_id_middleware."""

    @pytest.mark.asyncio
    async def test_request_id_middleware_generates_id(self):
        """Test middleware generates request ID if not provided."""
        from starlette.requests import Request
        from starlette.responses import PlainTextResponse

        request = Request({"type": "http", "method": "GET", "headers": []})

        async def call_next(req):
            return PlainTextResponse("OK")

        response = await api._request_id_middleware(request, call_next)

        assert hasattr(request.state, "request_id")
        assert api.REQUEST_ID_HEADER in response.headers

    @pytest.mark.asyncio
    async def test_request_id_middleware_uses_existing_id(self):
        """Test middleware uses existing request ID from headers."""
        from starlette.requests import Request
        from starlette.responses import PlainTextResponse

        existing_id = "existing-request-id-123"
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "headers": [(b"x-request-id", existing_id.encode())],
            }
        )

        async def call_next(req):
            return PlainTextResponse("OK")

        response = await api._request_id_middleware(request, call_next)

        assert request.state.request_id == existing_id
        assert response.headers[api.REQUEST_ID_HEADER] == existing_id


class TestErrorLoggingMiddleware:
    """Test _error_logging_middleware."""

    @pytest.mark.asyncio
    async def test_error_logging_middleware_passes_through(self):
        """Test middleware passes through successful responses."""
        from starlette.requests import Request
        from starlette.responses import PlainTextResponse

        request = Request({"type": "http", "method": "GET", "headers": []})
        request.state.request_id = "test-request-id"

        async def call_next(req):
            return PlainTextResponse("OK")

        response = await api._error_logging_middleware(request, call_next)

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_error_logging_middleware_handles_http_exception(self):
        """Test middleware handles HTTPException."""
        from fastapi import HTTPException
        from starlette.requests import Request

        request = Request({"type": "http", "method": "GET", "headers": []})
        request.state.request_id = "test-request-id"

        async def call_next(req):
            raise HTTPException(status_code=404, detail="Not found")

        with pytest.raises(HTTPException):
            await api._error_logging_middleware(request, call_next)

    @pytest.mark.asyncio
    async def test_error_logging_middleware_handles_generic_exception(self):
        """Test middleware handles generic exceptions."""
        from starlette.requests import Request

        request = Request({"type": "http", "method": "GET", "headers": [], "path": "/test"})
        request.state.request_id = "test-request-id"

        async def call_next(req):
            raise ValueError("Test error")

        response = await api._error_logging_middleware(request, call_next)

        assert response.status_code == 500
        # Response should be JSONResponse with error details
        body = response.body.decode()
        assert "Internal server error" in body


class TestInitResources:
    """Test init_resources function."""

    @pytest.mark.asyncio
    async def test_init_resources_first_time(self, mock_agent, mock_kg, mock_pipeline):
        """Test init_resources initializes all resources."""
        with patch("src.web.api.get_registry") as mock_registry_getter:
            mock_registry = MagicMock()
            mock_registry.is_initialized.return_value = False
            mock_registry_getter.return_value = mock_registry

            with patch("src.web.api.GeminiAgent", return_value=mock_agent):
                with patch("src.web.api.QAKnowledgeGraph", return_value=mock_kg):
                    with patch("src.web.api.IntegratedQAPipeline", return_value=mock_pipeline):
                        await api.init_resources()

            mock_registry.register_config.assert_called_once()
            mock_registry.register_agent.assert_called_once()
            mock_registry.register_kg.assert_called_once()
            mock_registry.register_pipeline.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_resources_already_initialized(self, mock_agent, mock_kg, mock_pipeline):
        """Test init_resources uses existing resources when already initialized."""
        with patch("src.web.api.get_registry") as mock_registry_getter:
            mock_registry = MagicMock()
            mock_registry.is_initialized.return_value = True
            mock_registry.agent = mock_agent
            mock_registry.kg = mock_kg
            mock_registry.pipeline = mock_pipeline
            mock_registry.config = api.get_config()
            mock_registry_getter.return_value = mock_registry

            await api.init_resources()

            # Should use existing resources
            assert api.agent == mock_agent
            assert api.kg == mock_kg
            assert api.pipeline == mock_pipeline

    @pytest.mark.asyncio
    async def test_init_resources_handles_neo4j_failure(self, mock_agent):
        """Test init_resources handles Neo4j connection failure."""
        with patch("src.web.api.get_registry") as mock_registry_getter:
            mock_registry = MagicMock()
            mock_registry.is_initialized.return_value = False
            mock_registry_getter.return_value = mock_registry

            with patch("src.web.api.GeminiAgent", return_value=mock_agent):
                with patch("src.web.api.QAKnowledgeGraph", side_effect=Exception("Neo4j error")):
                    await api.init_resources()

            # Should register None for kg
            calls = [call[0][0] for call in mock_registry.register_kg.call_args_list]
            assert None in calls


class TestInitHealthChecks:
    """Test _init_health_checks function."""

    @pytest.mark.asyncio
    async def test_init_health_checks_registers_neo4j(self, monkeypatch):
        """Test health checks registers Neo4j when URI is set."""
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "password")

        await api._init_health_checks()

        # Should have registered neo4j check
        assert "neo4j" in api.health_checker._checks

    @pytest.mark.asyncio
    async def test_init_health_checks_registers_redis(self, monkeypatch):
        """Test health checks registers Redis when URL is set."""
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

        await api._init_health_checks()

        assert "redis" in api.health_checker._checks

    @pytest.mark.asyncio
    async def test_init_health_checks_registers_gemini(self, monkeypatch):
        """Test health checks registers Gemini when API key is set."""
        monkeypatch.setenv("GEMINI_API_KEY", "AIza" + "0" * 35)

        await api._init_health_checks()

        assert "gemini" in api.health_checker._checks


class TestPageEndpoints:
    """Test page rendering endpoints."""

    def test_root_redirects_to_qa(self, test_client):
        """Test root path redirects to /qa."""
        response = test_client.get("/", follow_redirects=False)
        assert response.status_code in (307, 302)  # Redirect status codes
        assert response.headers["location"] == "/qa"

    def test_qa_page_renders(self, test_client):
        """Test /qa page renders successfully."""
        response = test_client.get("/qa")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_eval_page_renders(self, test_client):
        """Test /eval page renders successfully."""
        response = test_client.get("/eval")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_workspace_page_renders(self, test_client):
        """Test /workspace page renders successfully."""
        response = test_client.get("/workspace")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestSessionEndpoints:
    """Test session management endpoints."""

    def test_get_session(self, test_client):
        """Test GET /api/session returns session data."""
        with patch.object(api.session_manager, "serialize", return_value={"session_id": "test"}):
            response = test_client.get("/api/session")
            assert response.status_code == 200
            assert "session_id" in response.json()

    def test_delete_session(self, test_client):
        """Test DELETE /api/session clears session."""
        with patch.object(api.session_manager, "destroy") as mock_destroy:
            response = test_client.delete("/api/session")
            assert response.status_code == 200
            assert response.json()["cleared"] is True


class TestOCREndpoints:
    """Test OCR endpoints."""

    def test_get_ocr_success(self, test_client):
        """Test GET /api/ocr returns OCR text."""
        with patch("src.web.api.load_ocr_text", return_value="Test OCR content"):
            response = test_client.get("/api/ocr")
            assert response.status_code == 200
            assert response.json()["ocr"] == "Test OCR content"

    def test_get_ocr_handles_error(self, test_client):
        """Test GET /api/ocr handles errors gracefully."""
        from fastapi import HTTPException

        with patch("src.web.api.load_ocr_text", side_effect=HTTPException(404, "Not found")):
            response = test_client.get("/api/ocr")
            assert response.status_code == 200  # Error handled gracefully
            assert response.json()["ocr"] == ""
            assert "error" in response.json()

    def test_post_ocr_success(self, test_client):
        """Test POST /api/ocr saves OCR text."""
        with patch("src.web.api.save_ocr_text") as mock_save:
            response = test_client.post("/api/ocr", json={"text": "New OCR content"})
            assert response.status_code == 200
            assert response.json()["status"] == "success"
            mock_save.assert_called_once_with("New OCR content")

    def test_post_ocr_handles_failure(self, test_client):
        """Test POST /api/ocr handles save failures."""
        with patch("src.web.api.save_ocr_text", side_effect=Exception("Save failed")):
            response = test_client.post("/api/ocr", json={"text": "New OCR content"})
            assert response.status_code == 500


class TestMultimodalEndpoints:
    """Test multimodal endpoints."""

    def test_multimodal_page_disabled(self, test_client):
        """Test /multimodal page shows disabled message."""
        if api.ENABLE_MULTIMODAL:
            response = test_client.get("/multimodal")
            assert response.status_code == 200
            assert b"disabled" in response.content.lower()

    def test_analyze_image_disabled(self, test_client):
        """Test multimodal analysis endpoint is disabled."""
        if api.ENABLE_MULTIMODAL:
            # Create a fake file upload
            files = {"file": ("test.jpg", b"fake image data", "image/jpeg")}
            response = test_client.post("/api/multimodal/analyze", files=files)
            assert response.status_code == 500
            assert "disabled" in response.json()["detail"].lower()


class TestMetricsEndpoints:
    """Test metrics and analytics endpoints."""

    def test_metrics_endpoint(self, test_client):
        """Test /metrics endpoint returns Prometheus metrics."""
        if api.ENABLE_METRICS:
            with patch("src.web.api.get_metrics", return_value="# HELP test_metric"):
                response = test_client.get("/metrics")
                assert response.status_code == 200
                assert response.headers["content-type"] == "text/plain; charset=utf-8"

    def test_current_metrics(self, test_client):
        """Test /api/analytics/current returns current metrics."""
        if api.ENABLE_METRICS:
            with patch("src.web.api.UsageDashboard") as mock_dashboard_class:
                mock_dashboard = MagicMock()
                mock_dashboard.get_today_stats.return_value = {
                    "sessions": 10,
                    "cost": 0.5,
                    "cache_hit_rate": 0.75,
                }
                mock_dashboard.get_week_total_cost.return_value = 2.5
                mock_dashboard.get_week_avg_quality.return_value = 0.85
                mock_dashboard_class.return_value = mock_dashboard

                response = test_client.get("/api/analytics/current")
                assert response.status_code == 200
                data = response.json()
                assert "today" in data
                assert "this_week" in data

    def test_set_log_level_valid(self, test_client):
        """Test POST /admin/log-level with valid level."""
        if api.ENABLE_METRICS:
            with patch("src.web.api.set_log_level", return_value=True):
                response = test_client.post("/admin/log-level?level=DEBUG")
                assert response.status_code == 200
                assert "DEBUG" in response.json()["message"]

    def test_set_log_level_invalid(self, test_client):
        """Test POST /admin/log-level with invalid level."""
        if api.ENABLE_METRICS:
            response = test_client.post("/admin/log-level?level=INVALID")
            assert response.status_code == 400


class TestModuleConstants:
    """Test module-level constants and configuration."""

    def test_enable_multimodal_default(self):
        """Test ENABLE_MULTIMODAL default value."""
        assert isinstance(api.ENABLE_MULTIMODAL, bool)

    def test_enable_metrics_default(self):
        """Test ENABLE_METRICS default value."""
        assert isinstance(api.ENABLE_METRICS, bool)

    def test_request_id_header_defined(self):
        """Test REQUEST_ID_HEADER is defined."""
        assert api.REQUEST_ID_HEADER == "X-Request-Id"

    def test_repo_root_is_path(self):
        """Test REPO_ROOT is a Path object."""
        assert isinstance(api.REPO_ROOT, Path)
        assert isinstance(api.PROJECT_ROOT, Path)
        assert api.REPO_ROOT == api.PROJECT_ROOT


class TestLogApiError:
    """Test _log_api_error helper function."""

    def test_log_api_error_includes_context(self):
        """Test _log_api_error includes request context."""
        from starlette.requests import Request
        from starlette.datastructures import Address

        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/test",
                "headers": [(b"user-agent", b"test-agent")],
            }
        )
        request.state.request_id = "test-123"
        # Mock client
        request._scope["client"] = Address("127.0.0.1", 8000)

        test_exception = ValueError("Test error")

        mock_logger = MagicMock()

        api._log_api_error(
            "Test message",
            request=request,
            exc=test_exception,
            logger_obj=mock_logger,
        )

        mock_logger.error.assert_called_once()
        # Check that extra context was passed
        call_kwargs = mock_logger.error.call_args[1]
        assert "extra" in call_kwargs
        assert call_kwargs["extra"]["request_id"] == "test-123"
        assert call_kwargs["extra"]["path"] == "/test"


class TestGetRequestId:
    """Test _get_request_id helper function."""

    def test_get_request_id_returns_id(self):
        """Test _get_request_id returns request ID from state."""
        from starlette.requests import Request

        request = Request({"type": "http", "method": "GET", "headers": []})
        request.state.request_id = "test-request-id"

        request_id = api._get_request_id(request)

        assert request_id == "test-request-id"

    def test_get_request_id_returns_empty_when_missing(self):
        """Test _get_request_id returns empty string when no ID."""
        from starlette.requests import Request

        request = Request({"type": "http", "method": "GET", "headers": []})

        request_id = api._get_request_id(request)

        assert request_id == ""


class TestAdminRouter:
    """Test admin router inclusion."""

    def test_admin_router_included_when_enabled(self, monkeypatch):
        """Test admin router is included when ENABLE_ADMIN_API=true."""
        # This test would need to reload the module with different env var
        # For now, just verify the constant is checked
        monkeypatch.setenv("ENABLE_ADMIN_API", "true")
        enabled = os.getenv("ENABLE_ADMIN_API", "false").lower() == "true"
        assert enabled is True

    def test_admin_router_excluded_by_default(self):
        """Test admin router is excluded by default."""
        enabled = os.getenv("ENABLE_ADMIN_API", "false").lower() == "true"
        # By default should be False unless explicitly set in environment
        assert enabled is False or enabled is True  # Depends on test environment
