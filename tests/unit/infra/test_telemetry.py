"""Tests for OpenTelemetry telemetry functionality."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.infra.telemetry import (
    get_meter,
    get_tracer,
    init_telemetry,
    traced,
    traced_async,
)


class TestInitTelemetry:
    """Tests for init_telemetry function."""

    @patch.dict(
        os.environ, {"OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317"}
    )
    @patch("src.infra.telemetry.trace")
    @patch("src.infra.telemetry.metrics")
    @patch("src.infra.telemetry.Resource")
    @patch("src.infra.telemetry.TracerProvider")
    @patch("src.infra.telemetry.BatchSpanProcessor")
    @patch("src.infra.telemetry.OTLPSpanExporter")
    @patch("src.infra.telemetry.MeterProvider")
    @patch("src.infra.telemetry.PeriodicExportingMetricReader")
    @patch("src.infra.telemetry.OTLPMetricExporter")
    def test_init_with_endpoint(
        self,
        mock_metric_exporter,
        mock_metric_reader,
        mock_meter_provider,
        mock_span_exporter,
        mock_span_processor,
        mock_tracer_provider,
        mock_resource,
        mock_metrics,
        mock_trace,
    ):
        """Test initialization with OTLP endpoint."""
        # Setup mocks
        mock_resource_instance = MagicMock()
        mock_resource.create.return_value = mock_resource_instance
        mock_tracer_provider_instance = MagicMock()
        mock_tracer_provider.return_value = mock_tracer_provider_instance

        init_telemetry("test-service", "http://localhost:4317")

        # Verify trace provider was set
        mock_trace.set_tracer_provider.assert_called_once()

    @patch.dict(os.environ, {}, clear=True)
    @patch("src.infra.telemetry.trace")
    def test_init_without_endpoint(self, mock_trace):
        """Test that telemetry is disabled without endpoint."""
        init_telemetry("test-service")

        # Trace provider should not be set
        mock_trace.set_tracer_provider.assert_not_called()

    @patch("src.infra.telemetry.trace", None)
    def test_init_without_opentelemetry(self):
        """Test graceful handling when OpenTelemetry is not installed."""
        # Should not raise exception
        init_telemetry("test-service", "http://localhost:4317")


class TestGetTracer:
    """Tests for get_tracer function."""

    def test_get_tracer_returns_callable(self):
        """Test that tracer returns a callable object."""
        tracer = get_tracer()

        assert tracer is not None
        assert hasattr(tracer, "start_as_current_span")

    @patch("src.infra.telemetry.trace", None)
    def test_noop_tracer_when_no_trace(self):
        """Test noop tracer when trace module is None."""
        tracer = get_tracer()

        # Noop tracer methods should work without errors
        span = tracer.start_as_current_span("test")
        with span:
            span.set_attribute("key", "value")
            span.record_exception(Exception("test"))
            span.set_status("OK")

    @patch("src.infra.telemetry._tracer", None)
    @patch("src.infra.telemetry.trace")
    def test_get_tracer_fallback(self, mock_trace):
        """Test get_tracer falls back to trace.get_tracer."""
        mock_tracer = MagicMock()
        mock_trace.get_tracer.return_value = mock_tracer

        tracer = get_tracer()

        assert tracer == mock_tracer


class TestGetMeter:
    """Tests for get_meter function."""

    def test_get_meter_returns_callable(self):
        """Test that meter returns a callable object."""
        meter = get_meter()

        assert meter is not None
        assert hasattr(meter, "create_counter")

    @patch("src.infra.telemetry.metrics", None)
    def test_noop_meter_when_no_metrics(self):
        """Test noop meter when metrics module is None."""
        meter = get_meter()

        # Noop meter methods should work without errors
        counter = meter.create_counter("test_counter")
        counter.add(1)  # Should not raise exception

    @patch("src.infra.telemetry._meter", None)
    @patch("src.infra.telemetry.metrics")
    def test_get_meter_fallback(self, mock_metrics):
        """Test get_meter falls back to metrics.get_meter."""
        mock_meter = MagicMock()
        mock_metrics.get_meter.return_value = mock_meter

        meter = get_meter()

        assert meter == mock_meter


class TestTracedDecorator:
    """Tests for traced decorator."""

    def test_traced_decorator_basic(self):
        """Test basic traced decorator functionality."""

        @traced("test_operation")
        def sample_function():
            return "result"

        result = sample_function()
        assert result == "result"

    def test_traced_with_attributes(self):
        """Test traced decorator with attributes."""

        @traced("test_op", attributes={"key": "value"})
        def sample_function():
            return 42

        result = sample_function()
        assert result == 42

    def test_traced_exception_handling(self):
        """Test traced decorator with exception."""

        @traced("failing_operation")
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            failing_function()

    def test_traced_preserves_function_metadata(self):
        """Test that decorator preserves function metadata."""

        @traced("test_op")
        def documented_function():
            """This is a docstring."""
            pass

        assert documented_function.__doc__ == "This is a docstring."
        assert documented_function.__name__ == "documented_function"

    def test_traced_with_arguments(self):
        """Test traced decorator with function arguments."""

        @traced("add_operation")
        def add(a, b):
            return a + b

        result = add(2, 3)
        assert result == 5

    def test_traced_with_kwargs(self):
        """Test traced decorator with keyword arguments."""

        @traced("greeting_operation")
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        result = greet("World", greeting="Hi")
        assert result == "Hi, World!"


class TestTracedAsyncDecorator:
    """Tests for traced_async decorator."""

    @pytest.mark.asyncio
    async def test_traced_async_decorator_basic(self):
        """Test basic traced_async decorator functionality."""

        @traced_async("async_operation")
        async def async_sample_function():
            return "async_result"

        result = await async_sample_function()
        assert result == "async_result"

    @pytest.mark.asyncio
    async def test_traced_async_with_attributes(self):
        """Test traced_async decorator with attributes."""

        @traced_async("async_op", attributes={"user_id": "123"})
        async def async_function():
            return 100

        result = await async_function()
        assert result == 100

    @pytest.mark.asyncio
    async def test_traced_async_exception_handling(self):
        """Test traced_async decorator with exception."""

        @traced_async("failing_async_op")
        async def failing_async_function():
            raise RuntimeError("Async error")

        with pytest.raises(RuntimeError, match="Async error"):
            await failing_async_function()

    @pytest.mark.asyncio
    async def test_traced_async_preserves_metadata(self):
        """Test that async decorator preserves function metadata."""

        @traced_async("async_test")
        async def documented_async_function():
            """Async docstring."""
            pass

        assert documented_async_function.__doc__ == "Async docstring."
        assert documented_async_function.__name__ == "documented_async_function"

    @pytest.mark.asyncio
    async def test_traced_async_with_arguments(self):
        """Test traced_async decorator with arguments."""

        @traced_async("async_multiply")
        async def multiply(a, b):
            return a * b

        result = await multiply(3, 4)
        assert result == 12

    @pytest.mark.asyncio
    async def test_traced_async_with_kwargs(self):
        """Test traced_async decorator with keyword arguments."""

        @traced_async("async_format")
        async def format_message(msg, prefix="INFO"):
            return f"[{prefix}] {msg}"

        result = await format_message("Test", prefix="DEBUG")
        assert result == "[DEBUG] Test"


class TestNoopImplementations:
    """Tests for noop implementations when OpenTelemetry is not available."""

    @patch("src.infra.telemetry.trace", None)
    def test_noop_span_context_manager(self):
        """Test noop span as context manager."""
        tracer = get_tracer()
        span = tracer.start_as_current_span("test")

        # Should work as context manager without errors
        with span:
            pass

    @patch("src.infra.telemetry.trace", None)
    def test_noop_span_set_attribute(self):
        """Test noop span set_attribute."""
        tracer = get_tracer()
        span = tracer.start_as_current_span("test")

        # Should not raise exception
        result = span.set_attribute("key", "value")
        assert result is None

    @patch("src.infra.telemetry.trace", None)
    def test_noop_span_record_exception(self):
        """Test noop span record_exception."""
        tracer = get_tracer()
        span = tracer.start_as_current_span("test")

        # Should not raise exception
        result = span.record_exception(Exception("test"))
        assert result is None

    @patch("src.infra.telemetry.trace", None)
    def test_noop_span_set_status(self):
        """Test noop span set_status."""
        tracer = get_tracer()
        span = tracer.start_as_current_span("test")

        # Should not raise exception
        result = span.set_status("OK")
        assert result is None

    @patch("src.infra.telemetry.metrics", None)
    def test_noop_counter_add(self):
        """Test noop counter add."""
        meter = get_meter()
        counter = meter.create_counter("test_counter")

        # Should not raise exception
        result = counter.add(5)
        assert result is None

    @patch("src.infra.telemetry.metrics", None)
    def test_noop_meter_create_counter(self):
        """Test noop meter create_counter."""
        meter = get_meter()

        # Should return noop counter
        counter = meter.create_counter("test", description="test counter")
        assert counter is not None
        assert hasattr(counter, "add")
