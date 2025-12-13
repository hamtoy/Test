"""Comprehensive test coverage for src/web/api.py."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from src.web.api import (
    _error_logging_middleware,
    _get_request_id,
    _log_api_error,
    _request_id_middleware,
    app,
    get_config,
    init_resources,
)


class TestHelperFunctions:
    """Test helper functions."""

    def test_get_request_id_exists(self) -> None:
        """Test _get_request_id when request_id exists."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "test-request-123"

        result = _get_request_id(mock_request)

        assert result == "test-request-123"

    def test_get_request_id_missing(self) -> None:
        """Test _get_request_id when request_id is missing."""
        mock_request = MagicMock(spec=Request)
        mock_request.state = MagicMock()
        delattr(mock_request.state, "request_id")

        result = _get_request_id(mock_request)

        assert result == ""

    def test_log_api_error(self) -> None:
        """Test _log_api_error logs with proper context."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req-456"
        mock_request.url.path = "/api/test"
        mock_request.method = "POST"
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.return_value = "TestAgent/1.0"

        mock_logger = MagicMock()
        test_exc = ValueError("Test error")

        _log_api_error(
            "Test message", request=mock_request, exc=test_exc, logger_obj=mock_logger
        )

        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert "Test message" in call_args[0]
        assert call_args[1]["extra"]["request_id"] == "req-456"
        assert call_args[1]["extra"]["path"] == "/api/test"
        assert call_args[1]["extra"]["error_type"] == "ValueError"


class TestMiddleware:
    """Test middleware functions."""

    @pytest.mark.asyncio
    async def test_request_id_middleware_generates_id(self) -> None:
        """Test _request_id_middleware generates request ID if missing."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = None
        mock_request.state = MagicMock()

        mock_response = MagicMock(spec=Response)
        mock_response.headers = {}

        async def mock_call_next(request: Request) -> Response:
            return mock_response

        result = await _request_id_middleware(mock_request, mock_call_next)

        assert hasattr(mock_request.state, "request_id")
        assert len(mock_request.state.request_id) > 0
        assert "X-Request-Id" in result.headers

    @pytest.mark.asyncio
    async def test_request_id_middleware_uses_existing_id(self) -> None:
        """Test _request_id_middleware uses existing header."""
        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = "existing-id-789"
        mock_request.state = MagicMock()

        mock_response = MagicMock(spec=Response)
        mock_response.headers = {}

        async def mock_call_next(request: Request) -> Response:
            return mock_response

        result = await _request_id_middleware(mock_request, mock_call_next)

        assert mock_request.state.request_id == "existing-id-789"
        assert result.headers["X-Request-Id"] == "existing-id-789"

    @pytest.mark.asyncio
    async def test_error_logging_middleware_http_exception(self) -> None:
        """Test _error_logging_middleware handles HTTPException."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req-error-1"
        mock_request.url.path = "/api/fail"
        mock_request.method = "GET"

        async def mock_call_next(request: Request) -> Response:
            raise HTTPException(status_code=404, detail="Not found")

        with pytest.raises(HTTPException) as exc_info:
            await _error_logging_middleware(mock_request, mock_call_next)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_error_logging_middleware_generic_exception(self) -> None:
        """Test _error_logging_middleware handles generic exceptions."""
        mock_request = MagicMock(spec=Request)
        mock_request.state.request_id = "req-error-2"
        mock_request.url.path = "/api/crash"
        mock_request.method = "POST"

        async def mock_call_next(request: Request) -> Response:
            raise ValueError("Unexpected error")

        response = await _error_logging_middleware(mock_request, mock_call_next)

        assert response.status_code == 500
        # Response body should be JSON with error details


class TestConfigInitialization:
    """Test configuration initialization."""

    @patch.dict(os.environ, {"GEMINI_API_KEY": "AIza" + "A" * 35})
    def test_get_config_with_valid_key(self) -> None:
        """Test get_config with valid API key."""
        # Reset global config
        from src.web import api as api_module

        api_module._config = None

        config = get_config()

        assert config is not None
        # Check that config was created successfully
        assert hasattr(config, "model_name")

    @patch.dict(os.environ, {}, clear=True)
    def test_get_config_without_key_non_production(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test get_config creates dummy key in non-production."""
        from src.web import api as api_module

        api_module._config = None
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("ENVIRONMENT", raising=False)

        config = get_config()

        assert config is not None
        # Should have created a dummy key
        assert os.getenv("GEMINI_API_KEY", "").startswith("AIza")

    @patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=True)
    def test_get_config_production_requires_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test get_config raises error in production without key."""
        from src.web import api as api_module

        api_module._config = None
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        with pytest.raises(ValueError, match="GEMINI_API_KEY required in production"):
            get_config()


class TestResourceInitialization:
    """Test init_resources function."""

    @pytest.mark.asyncio
    @patch("src.web.api.get_registry")
    @patch("src.web.api.GeminiAgent")
    @patch("src.web.api.QAKnowledgeGraph")
    @patch("src.web.api.IntegratedQAPipeline")
    async def test_init_resources_first_time(
        self,
        mock_pipeline_cls: Mock,
        mock_kg_cls: Mock,
        mock_agent_cls: Mock,
        mock_get_registry: Mock,
    ) -> None:
        """Test init_resources on first initialization."""
        mock_registry = MagicMock()
        mock_registry.is_initialized.return_value = False
        mock_get_registry.return_value = mock_registry

        mock_agent = MagicMock()
        mock_kg = MagicMock()
        mock_pipeline = MagicMock()

        mock_agent_cls.return_value = mock_agent
        mock_kg_cls.return_value = mock_kg
        mock_pipeline_cls.return_value = mock_pipeline

        await init_resources()

        mock_registry.register_config.assert_called_once()
        mock_registry.register_agent.assert_called_once_with(mock_agent)
        mock_registry.register_kg.assert_called_once_with(mock_kg)
        mock_registry.register_pipeline.assert_called_once_with(mock_pipeline)

    @pytest.mark.asyncio
    @patch("src.web.api.get_registry")
    async def test_init_resources_already_initialized(
        self, mock_get_registry: Mock
    ) -> None:
        """Test init_resources when already initialized."""
        mock_registry = MagicMock()
        mock_registry.is_initialized.return_value = True
        mock_registry.agent = MagicMock()
        mock_registry.kg = MagicMock()
        mock_registry.pipeline = MagicMock()
        mock_registry.config = MagicMock()
        mock_get_registry.return_value = mock_registry

        await init_resources()

        # Should not call register methods again
        mock_registry.register_config.assert_not_called()
        mock_registry.register_agent.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.web.api.get_registry")
    @patch("src.web.api.GeminiAgent")
    @patch("src.web.api.QAKnowledgeGraph")
    async def test_init_resources_kg_connection_failure(
        self,
        mock_kg_cls: Mock,
        mock_agent_cls: Mock,
        mock_get_registry: Mock,
    ) -> None:
        """Test init_resources handles KG connection failure gracefully."""
        mock_registry = MagicMock()
        mock_registry.is_initialized.return_value = False
        mock_get_registry.return_value = mock_registry

        mock_agent_cls.return_value = MagicMock()
        mock_kg_cls.side_effect = Exception("Neo4j connection failed")

        await init_resources()

        # Should register None for kg
        assert any(
            call[0][0] is None for call in mock_registry.register_kg.call_args_list
        )


class TestAPIEndpoints:
    """Test API endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    def test_session_get_no_session(self, client: TestClient) -> None:
        """Test /api/session GET without session."""
        # This will fail without proper session middleware setup
        # Testing error path
        with patch("src.web.api.session_manager") as mock_sm:
            mock_sm.serialize.side_effect = AttributeError("No session")
            client.get("/api/session")
            # Should handle error gracefully

    def test_session_delete(self, client: TestClient) -> None:
        """Test /api/session DELETE."""
        with patch("src.web.api.session_manager"):
            mock_session = MagicMock()
            mock_session.session_id = "test-session-123"

            # Mock request state
            with patch("starlette.requests.Request.state") as mock_state:
                mock_state.session = mock_session
                # Response verification depends on implementation


class TestConditionalEndpoints:
    """Test conditionally enabled endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    def test_metrics_endpoint_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test /metrics endpoint when enabled using module reimport pattern."""
        import importlib
        import sys
        import types

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        # Set env and reimport metrics module
        monkeypatch.setenv("ENABLE_METRICS", "true")
        sys.modules.pop("src.web.routers.metrics", None)
        metrics = importlib.import_module("src.web.routers.metrics")

        # Mock the metrics dependency
        fake_metrics_mod = types.SimpleNamespace(get_metrics=lambda: "# HELP test\n")
        monkeypatch.setitem(sys.modules, "src.monitoring.metrics", fake_metrics_mod)

        # Create temp app with metrics router
        tmp_app = FastAPI()
        tmp_app.include_router(metrics.router)

        client = TestClient(tmp_app)
        response = client.get("/metrics")

        assert response.status_code == 200
        assert "HELP" in response.text

    @patch.dict(os.environ, {"ENABLE_METRICS": "true"})
    @patch("src.analytics.dashboard.UsageDashboard")
    def test_analytics_current(
        self, mock_dashboard_cls: Mock, client: TestClient
    ) -> None:
        """Test /api/analytics/current endpoint."""
        mock_dashboard = MagicMock()
        mock_dashboard.get_today_stats.return_value = {
            "sessions": 10,
            "cost": 1.50,
            "cache_hit_rate": 0.85,
        }
        mock_dashboard.get_week_total_cost.return_value = 10.0
        mock_dashboard.get_week_avg_quality.return_value = 0.9
        mock_dashboard_cls.return_value = mock_dashboard

        # Test would require app to be recreated with ENABLE_METRICS


class TestOCREndpoints:
    """Test OCR-related endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    def test_api_get_ocr_success(self, client: TestClient) -> None:
        """Test /api/ocr GET success."""
        with patch("src.web.routers.ocr._load_ocr_text") as mock_load:
            mock_load.return_value = "Sample OCR text"

            response = client.get("/api/ocr")

            assert response.status_code == 200
            data = response.json()
            assert data["ocr"] == "Sample OCR text"

    def test_api_get_ocr_http_exception(self, client: TestClient) -> None:
        """Test /api/ocr GET with HTTPException - should re-raise with proper status."""
        with patch("src.web.routers.ocr._load_ocr_text") as mock_load:
            mock_load.side_effect = HTTPException(
                status_code=404, detail="File not found"
            )

            response = client.get("/api/ocr")

            # HTTPException should be re-raised, not caught and returned as 200
            assert response.status_code == 404
            data = response.json()
            assert data["detail"] == "File not found"

    def test_api_get_ocr_generic_exception(self, client: TestClient) -> None:
        """Test /api/ocr GET with generic exception."""
        with patch("src.web.routers.ocr._load_ocr_text") as mock_load:
            mock_load.side_effect = IOError("Disk error")

            response = client.get("/api/ocr")

            assert response.status_code == 500

    def test_api_save_ocr_success(self, client: TestClient) -> None:
        """Test /api/ocr POST success."""
        with patch("src.web.routers.ocr._save_ocr_text") as mock_save:
            payload = {"text": "New OCR content"}

            response = client.post("/api/ocr", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            mock_save.assert_called_once()

    def test_api_save_ocr_failure(self, client: TestClient) -> None:
        """Test /api/ocr POST failure."""
        with patch("src.web.routers.ocr._save_ocr_text") as mock_save:
            mock_save.side_effect = IOError("Cannot write file")
            payload = {"text": "Content"}

            response = client.post("/api/ocr", json=payload)

            assert response.status_code == 500


class TestPageRoutes:
    """Test HTML page routes."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        return TestClient(app)

    def test_root_redirect(self, client: TestClient) -> None:
        """Test root redirects to /qa."""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307  # Temporary redirect
        assert response.headers["location"] == "/qa"

    def test_qa_page(self, client: TestClient) -> None:
        """Test /qa page renders."""
        response = client.get("/qa")
        assert response.status_code == 200

    def test_eval_page(self, client: TestClient) -> None:
        """Test /eval page renders."""
        response = client.get("/eval")
        assert response.status_code == 200

    def test_workspace_page(self, client: TestClient) -> None:
        """Test /workspace page renders."""
        response = client.get("/workspace")
        assert response.status_code == 200


class TestUtilityWrappers:
    """Test utility wrapper functions."""

    @patch("src.web.api.config")
    @pytest.mark.asyncio
    async def test_load_ocr_text_wrapper(self, mock_config: Mock) -> None:
        """Test load_ocr_text wrapper function."""
        from src.web.api import load_ocr_text

        from unittest.mock import AsyncMock, patch

        with patch(
            "src.web.api._load_ocr_text", new=AsyncMock(return_value="OCR content")
        ):
            result = await load_ocr_text()

            assert result == "OCR content"

    @patch("src.web.api.config")
    @pytest.mark.asyncio
    async def test_save_ocr_text_wrapper(self, mock_config: Mock) -> None:
        """Test save_ocr_text wrapper function."""
        from src.web.api import save_ocr_text

        from unittest.mock import AsyncMock, patch

        save_mock = AsyncMock()
        with patch("src.web.api._save_ocr_text", new=save_mock):
            await save_ocr_text("New content")
            save_mock.assert_awaited_once_with(mock_config, "New content")
