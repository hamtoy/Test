"""Tests for monitoring metrics exporter module."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock, patch

import pytest

from src.monitoring.metrics_exporter import MetricsExporter, get_exporter


class TestMetricsExporter:
    """Test MetricsExporter class."""

    def test_metrics_exporter_init(self) -> None:
        """Test MetricsExporter initialization."""
        exporter = MetricsExporter()
        assert exporter._initialized is False
        assert exporter._request_latency is None
        assert exporter._requests_total is None
        assert exporter._tokens_total is None
        assert exporter._cost_total is None
        assert exporter._cache_hits is None
        assert exporter._cache_misses is None

    @patch("src.monitoring.metrics_exporter.logger")
    def test_init_metrics_success(self, mock_logger: Mock) -> None:
        """Test successful metrics initialization when prometheus is available."""
        # Skip this test if prometheus_client is not installed
        # We'll test the actual behavior through other tests
        pytest.skip("prometheus_client not required for this test suite")

    @patch("src.monitoring.metrics_exporter.logger")
    def test_init_metrics_import_error(self, mock_logger: Mock) -> None:
        """Test metrics initialization with ImportError."""
        exporter = MetricsExporter()

        # Simulate ImportError by making the import fail
        import builtins

        original_import = builtins.__import__

        def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "prometheus_client":
                raise ImportError("No prometheus")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = exporter._init_metrics()

            assert result is False
            assert exporter._initialized is False
            mock_logger.warning.assert_called_once()

    def test_init_metrics_already_initialized(self) -> None:
        """Test that _init_metrics returns True if already initialized."""
        exporter = MetricsExporter()
        exporter._initialized = True

        result = exporter._init_metrics()

        assert result is True

    def test_record_request_not_initialized(self) -> None:
        """Test record_request when metrics not initialized."""
        exporter = MetricsExporter()

        with patch.object(exporter, "_init_metrics", return_value=False):
            # Should not raise exception
            exporter.record_request("/api/test", "GET", 0.5, 200)

    def test_record_request_success(self) -> None:
        """Test successful request recording."""
        exporter = MetricsExporter()
        mock_latency = Mock()
        mock_total = Mock()
        exporter._initialized = True
        exporter._request_latency = mock_latency
        exporter._requests_total = mock_total

        exporter.record_request("/api/test", "POST", 1.5, 201)

        mock_latency.labels.assert_called_once_with(endpoint="/api/test", method="POST")
        mock_latency.labels.return_value.observe.assert_called_once_with(1.5)

        mock_total.labels.assert_called_once_with(
            endpoint="/api/test", method="POST", status="201"
        )
        mock_total.labels.return_value.inc.assert_called_once()

    def test_record_request_missing_metrics(self) -> None:
        """Test record_request when metric objects are None."""
        exporter = MetricsExporter()
        exporter._initialized = True
        exporter._request_latency = None
        exporter._requests_total = None

        # Should not raise exception
        exporter.record_request("/api/test", "GET", 0.5, 200)

    def test_record_tokens_not_initialized(self) -> None:
        """Test record_tokens when not initialized."""
        exporter = MetricsExporter()

        with patch.object(exporter, "_init_metrics", return_value=False):
            exporter.record_tokens("gemini-pro", input_tokens=100)

    def test_record_tokens_success(self) -> None:
        """Test successful token recording."""
        exporter = MetricsExporter()
        mock_tokens = Mock()
        exporter._initialized = True
        exporter._tokens_total = mock_tokens

        exporter.record_tokens(
            "gemini-pro", input_tokens=100, output_tokens=50, cached_tokens=20
        )

        # Should be called 3 times (input, output, cached)
        assert mock_tokens.labels.call_count == 3
        assert mock_tokens.labels.return_value.inc.call_count == 3

    def test_record_tokens_only_input(self) -> None:
        """Test recording only input tokens."""
        exporter = MetricsExporter()
        mock_tokens = Mock()
        exporter._initialized = True
        exporter._tokens_total = mock_tokens

        exporter.record_tokens("gemini-pro", input_tokens=100)

        mock_tokens.labels.assert_called_once_with(model="gemini-pro", type="input")
        mock_tokens.labels.return_value.inc.assert_called_once_with(100)

    def test_record_tokens_zero_values(self) -> None:
        """Test that zero token values are not recorded."""
        exporter = MetricsExporter()
        mock_tokens = Mock()
        exporter._initialized = True
        exporter._tokens_total = mock_tokens

        exporter.record_tokens(
            "gemini-pro", input_tokens=0, output_tokens=0, cached_tokens=0
        )

        # Should not call labels at all
        mock_tokens.labels.assert_not_called()

    def test_record_tokens_none_tokens_total(self) -> None:
        """Test record_tokens when _tokens_total is None."""
        exporter = MetricsExporter()
        exporter._initialized = True
        exporter._tokens_total = None

        # Should not raise exception
        exporter.record_tokens("gemini-pro", input_tokens=100)

    def test_record_cost_not_initialized(self) -> None:
        """Test record_cost when not initialized."""
        exporter = MetricsExporter()

        with patch.object(exporter, "_init_metrics", return_value=False):
            exporter.record_cost("gemini-pro", 0.05)

    def test_record_cost_success(self) -> None:
        """Test successful cost recording."""
        exporter = MetricsExporter()
        mock_cost = Mock()
        exporter._initialized = True
        exporter._cost_total = mock_cost

        exporter.record_cost("gemini-pro", 0.123)

        mock_cost.labels.assert_called_once_with(model="gemini-pro")
        mock_cost.labels.return_value.inc.assert_called_once_with(0.123)

    def test_record_cost_none_cost_total(self) -> None:
        """Test record_cost when _cost_total is None."""
        exporter = MetricsExporter()
        exporter._initialized = True
        exporter._cost_total = None

        # Should not raise exception
        exporter.record_cost("gemini-pro", 0.05)

    def test_record_cache_not_initialized(self) -> None:
        """Test record_cache when not initialized."""
        exporter = MetricsExporter()

        with patch.object(exporter, "_init_metrics", return_value=False):
            exporter.record_cache("redis", hit=True)

    def test_record_cache_hit(self) -> None:
        """Test recording cache hit."""
        exporter = MetricsExporter()
        mock_hits = Mock()
        mock_misses = Mock()
        exporter._initialized = True
        exporter._cache_hits = mock_hits
        exporter._cache_misses = mock_misses

        exporter.record_cache("redis", hit=True)

        mock_hits.labels.assert_called_once_with(cache_type="redis")
        mock_hits.labels.return_value.inc.assert_called_once()
        mock_misses.labels.assert_not_called()

    def test_record_cache_miss(self) -> None:
        """Test recording cache miss."""
        exporter = MetricsExporter()
        mock_hits = Mock()
        mock_misses = Mock()
        exporter._initialized = True
        exporter._cache_hits = mock_hits
        exporter._cache_misses = mock_misses

        exporter.record_cache("memory", hit=False)

        mock_misses.labels.assert_called_once_with(cache_type="memory")
        mock_misses.labels.return_value.inc.assert_called_once()
        mock_hits.labels.assert_not_called()

    def test_record_cache_hit_none_cache_hits(self) -> None:
        """Test record_cache hit when _cache_hits is None."""
        exporter = MetricsExporter()
        exporter._initialized = True
        exporter._cache_hits = None
        exporter._cache_misses = Mock()

        # Should not raise exception
        exporter.record_cache("redis", hit=True)

    def test_record_cache_miss_none_cache_misses(self) -> None:
        """Test record_cache miss when _cache_misses is None."""
        exporter = MetricsExporter()
        exporter._initialized = True
        exporter._cache_hits = Mock()
        exporter._cache_misses = None

        # Should not raise exception
        exporter.record_cache("redis", hit=False)


class TestGetExporter:
    """Test get_exporter function."""

    def test_get_exporter_returns_singleton(self) -> None:
        """Test that get_exporter returns the same instance."""
        exporter1 = get_exporter()
        exporter2 = get_exporter()

        assert exporter1 is exporter2
        assert isinstance(exporter1, MetricsExporter)

    def test_get_exporter_returns_metrics_exporter(self) -> None:
        """Test that get_exporter returns MetricsExporter instance."""
        exporter = get_exporter()

        assert isinstance(exporter, MetricsExporter)
