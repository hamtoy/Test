"""Tests for src/monitoring/exporter.py module.

This module tests the Prometheus metrics exporter functionality including:
- MetricsMiddleware for HTTP request/response metrics
- add_metrics_endpoint for registering /metrics endpoint
- setup_metrics for complete metrics setup
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import Response


class TestMetricsMiddleware:
    """Test MetricsMiddleware class."""

    @pytest.mark.asyncio
    async def test_dispatch_success_status(self) -> None:
        """Test dispatch records success status for 2xx responses."""
        from src.monitoring.exporter import MetricsMiddleware

        # Create mock app
        mock_app = MagicMock()
        middleware = MetricsMiddleware(mock_app)

        # Create mock request
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/test"

        # Create mock response with success status
        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200

        # Create mock call_next that returns the response
        async def mock_call_next(request: Any) -> Response:
            return mock_response

        with patch("src.monitoring.exporter.record_api_call") as mock_record:
            result = await middleware.dispatch(mock_request, mock_call_next)

            assert result == mock_response
            mock_record.assert_called_once()
            call_args = mock_record.call_args
            assert call_args.kwargs["model"] == "http"
            assert call_args.kwargs["status"] == "success"
            assert "latency_seconds" in call_args.kwargs

    @pytest.mark.asyncio
    async def test_dispatch_error_status_4xx(self) -> None:
        """Test dispatch records error status for 4xx responses."""
        from src.monitoring.exporter import MetricsMiddleware

        mock_app = MagicMock()
        middleware = MetricsMiddleware(mock_app)

        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/error"

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 400

        async def mock_call_next(request: Any) -> Response:
            return mock_response

        with patch("src.monitoring.exporter.record_api_call") as mock_record:
            result = await middleware.dispatch(mock_request, mock_call_next)

            assert result == mock_response
            mock_record.assert_called_once()
            assert mock_record.call_args.kwargs["status"] == "error"

    @pytest.mark.asyncio
    async def test_dispatch_error_status_5xx(self) -> None:
        """Test dispatch records error status for 5xx responses."""
        from src.monitoring.exporter import MetricsMiddleware

        mock_app = MagicMock()
        middleware = MetricsMiddleware(mock_app)

        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/server-error"

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 500

        async def mock_call_next(request: Any) -> Response:
            return mock_response

        with patch("src.monitoring.exporter.record_api_call") as mock_record:
            result = await middleware.dispatch(mock_request, mock_call_next)

            assert result == mock_response
            assert mock_record.call_args.kwargs["status"] == "error"

    @pytest.mark.asyncio
    async def test_dispatch_exception_records_error(self) -> None:
        """Test dispatch records error status when exception is raised."""
        from src.monitoring.exporter import MetricsMiddleware

        mock_app = MagicMock()
        middleware = MetricsMiddleware(mock_app)

        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/exception"

        async def mock_call_next_raises(request: Any) -> Response:
            raise ValueError("Test exception")

        with patch("src.monitoring.exporter.record_api_call") as mock_record:
            with pytest.raises(ValueError, match="Test exception"):
                await middleware.dispatch(mock_request, mock_call_next_raises)

            mock_record.assert_called_once()
            assert mock_record.call_args.kwargs["status"] == "error"

    @pytest.mark.asyncio
    async def test_dispatch_metrics_endpoint_excluded(self) -> None:
        """Test that /metrics endpoint requests are not recorded."""
        from src.monitoring.exporter import MetricsMiddleware

        mock_app = MagicMock()
        middleware = MetricsMiddleware(mock_app)

        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/metrics"

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200

        async def mock_call_next(request: Any) -> Response:
            return mock_response

        with patch("src.monitoring.exporter.record_api_call") as mock_record:
            result = await middleware.dispatch(mock_request, mock_call_next)

            assert result == mock_response
            mock_record.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_measures_latency(self) -> None:
        """Test that latency is measured correctly."""
        from src.monitoring.exporter import MetricsMiddleware

        mock_app = MagicMock()
        middleware = MetricsMiddleware(mock_app)

        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/latency-test"

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200

        async def mock_call_next(request: Any) -> Response:
            return mock_response

        with patch("src.monitoring.exporter.record_api_call") as mock_record:
            await middleware.dispatch(mock_request, mock_call_next)

            latency = mock_record.call_args.kwargs["latency_seconds"]
            assert isinstance(latency, float)
            assert latency >= 0


class TestAddMetricsEndpoint:
    """Test add_metrics_endpoint function."""

    def test_add_metrics_endpoint_registers_route(self) -> None:
        """Test that /metrics endpoint is registered on the app."""
        from src.monitoring.exporter import add_metrics_endpoint

        mock_app = MagicMock()
        mock_app.get = MagicMock(return_value=lambda f: f)

        add_metrics_endpoint(mock_app)

        mock_app.get.assert_called_once_with("/metrics", include_in_schema=False)

    @pytest.mark.asyncio
    async def test_metrics_endpoint_prometheus_available(self) -> None:
        """Test metrics endpoint when prometheus is available."""
        from src.monitoring.exporter import add_metrics_endpoint

        mock_app = MagicMock()
        endpoint_func = None

        def capture_endpoint(*args: Any, **kwargs: Any) -> Any:
            def decorator(func: Any) -> Any:
                nonlocal endpoint_func
                endpoint_func = func
                return func

            return decorator

        mock_app.get = capture_endpoint

        with (
            patch("src.monitoring.exporter.PROMETHEUS_AVAILABLE", True),
            patch(
                "src.monitoring.exporter.get_metrics",
                return_value="# HELP test_metric\ntest_metric 1.0",
            ),
        ):
            add_metrics_endpoint(mock_app)

            # Call the captured endpoint function
            assert endpoint_func is not None
            response = await endpoint_func()

            assert response.status_code == 200
            assert "text/plain" in response.media_type

    @pytest.mark.asyncio
    async def test_metrics_endpoint_prometheus_not_available(self) -> None:
        """Test metrics endpoint when prometheus is not available."""
        from src.monitoring.exporter import add_metrics_endpoint

        mock_app = MagicMock()
        endpoint_func = None

        def capture_endpoint(*args: Any, **kwargs: Any) -> Any:
            def decorator(func: Any) -> Any:
                nonlocal endpoint_func
                endpoint_func = func
                return func

            return decorator

        mock_app.get = capture_endpoint

        with patch("src.monitoring.exporter.PROMETHEUS_AVAILABLE", False):
            add_metrics_endpoint(mock_app)

            assert endpoint_func is not None
            response = await endpoint_func()

            assert response.status_code == 200
            assert "Prometheus client not installed" in response.body.decode()


class TestSetupMetrics:
    """Test setup_metrics function."""

    def test_setup_metrics_with_middleware(self) -> None:
        """Test setup_metrics adds endpoint and middleware."""
        from src.monitoring.exporter import setup_metrics

        mock_app = MagicMock()
        mock_app.get = MagicMock(return_value=lambda f: f)

        setup_metrics(mock_app, enable_middleware=True)

        mock_app.get.assert_called()
        mock_app.add_middleware.assert_called_once()

    def test_setup_metrics_without_middleware(self) -> None:
        """Test setup_metrics adds only endpoint without middleware."""
        from src.monitoring.exporter import setup_metrics

        mock_app = MagicMock()
        mock_app.get = MagicMock(return_value=lambda f: f)

        setup_metrics(mock_app, enable_middleware=False)

        mock_app.get.assert_called()
        mock_app.add_middleware.assert_not_called()

    def test_setup_metrics_default_enables_middleware(self) -> None:
        """Test that middleware is enabled by default."""
        from src.monitoring.exporter import setup_metrics

        mock_app = MagicMock()
        mock_app.get = MagicMock(return_value=lambda f: f)

        setup_metrics(mock_app)

        mock_app.add_middleware.assert_called_once()


class TestModuleExports:
    """Test module exports."""

    def test_all_exports(self) -> None:
        """Test __all__ contains expected exports."""
        from src.monitoring import exporter

        assert hasattr(exporter, "__all__")
        assert "MetricsMiddleware" in exporter.__all__
        assert "add_metrics_endpoint" in exporter.__all__
        assert "setup_metrics" in exporter.__all__
