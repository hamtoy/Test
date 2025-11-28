"""Tests for src/monitoring/metrics.py to improve coverage."""

import pytest


class TestStubImplementations:
    """Tests for stub implementations when prometheus_client is not available."""

    def test_counter_stub(self):
        """Test Counter stub implementation."""
        from src.monitoring.metrics import Counter, PROMETHEUS_AVAILABLE

        if not PROMETHEUS_AVAILABLE:
            counter = Counter("test_counter", "Test counter", ["label1"])
            assert counter._name == "test_counter"
            # Test labels method
            labeled = counter.labels("value1")
            assert labeled is not None
            # Test inc method (should not raise)
            labeled.inc()
            labeled.inc(5)

    def test_histogram_stub(self):
        """Test Histogram stub implementation."""
        from src.monitoring.metrics import Histogram, PROMETHEUS_AVAILABLE

        if not PROMETHEUS_AVAILABLE:
            histogram = Histogram("test_histogram", "Test histogram", ["label1"])
            assert histogram._name == "test_histogram"
            # Test labels method
            labeled = histogram.labels("value1")
            assert labeled is not None
            # Test observe method (should not raise)
            labeled.observe(1.5)

    def test_gauge_stub(self):
        """Test Gauge stub implementation."""
        from src.monitoring.metrics import Gauge, PROMETHEUS_AVAILABLE

        if not PROMETHEUS_AVAILABLE:
            gauge = Gauge("test_gauge", "Test gauge")
            assert gauge._name == "test_gauge"
            assert gauge._value == 0.0
            # Test set method
            gauge.set(10.0)
            assert gauge._value == 10.0
            # Test inc method
            gauge.inc()
            assert gauge._value == 11.0
            gauge.inc(5)
            assert gauge._value == 16.0
            # Test dec method
            gauge.dec()
            assert gauge._value == 15.0
            gauge.dec(5)
            assert gauge._value == 10.0


class TestMetricObjects:
    """Test metric object creation."""

    def test_api_calls_total_exists(self):
        """Test api_calls_total counter exists."""
        from src.monitoring.metrics import api_calls_total

        assert api_calls_total is not None

    def test_api_latency_exists(self):
        """Test api_latency histogram exists."""
        from src.monitoring.metrics import api_latency

        assert api_latency is not None

    def test_api_errors_exists(self):
        """Test api_errors counter exists."""
        from src.monitoring.metrics import api_errors

        assert api_errors is not None

    def test_cache_hits_exists(self):
        """Test cache_hits counter exists."""
        from src.monitoring.metrics import cache_hits

        assert cache_hits is not None

    def test_cache_misses_exists(self):
        """Test cache_misses counter exists."""
        from src.monitoring.metrics import cache_misses

        assert cache_misses is not None

    def test_cache_size_exists(self):
        """Test cache_size gauge exists."""
        from src.monitoring.metrics import cache_size

        assert cache_size is not None

    def test_token_usage_exists(self):
        """Test token_usage counter exists."""
        from src.monitoring.metrics import token_usage

        assert token_usage is not None

    def test_cost_usd_exists(self):
        """Test cost_usd counter exists."""
        from src.monitoring.metrics import cost_usd

        assert cost_usd is not None

    def test_workflow_duration_exists(self):
        """Test workflow_duration histogram exists."""
        from src.monitoring.metrics import workflow_duration

        assert workflow_duration is not None

    def test_workflow_status_exists(self):
        """Test workflow_status counter exists."""
        from src.monitoring.metrics import workflow_status

        assert workflow_status is not None


class TestHelperFunctions:
    """Test helper functions."""

    def test_get_metrics(self):
        """Test get_metrics returns bytes."""
        from src.monitoring.metrics import get_metrics

        result = get_metrics()
        assert isinstance(result, bytes)

    def test_record_api_call(self):
        """Test record_api_call does not raise."""
        from src.monitoring.metrics import record_api_call

        # Should not raise regardless of PROMETHEUS_AVAILABLE
        record_api_call("gemini-1.5-flash", "success", 1.5)
        record_api_call("gemini-1.5-pro", "error", 0.5)

    def test_record_api_error(self):
        """Test record_api_error does not raise."""
        from src.monitoring.metrics import record_api_error

        # Should not raise regardless of PROMETHEUS_AVAILABLE
        record_api_error("gemini-1.5-flash", "timeout")
        record_api_error("gemini-1.5-pro", "rate_limit")

    def test_record_cache_access_hit(self):
        """Test record_cache_access with cache hit."""
        from src.monitoring.metrics import record_cache_access

        # Should not raise regardless of PROMETHEUS_AVAILABLE
        record_cache_access("redis", hit=True)

    def test_record_cache_access_miss(self):
        """Test record_cache_access with cache miss."""
        from src.monitoring.metrics import record_cache_access

        # Should not raise regardless of PROMETHEUS_AVAILABLE
        record_cache_access("redis", hit=False)

    def test_record_token_usage(self):
        """Test record_token_usage does not raise."""
        from src.monitoring.metrics import record_token_usage

        # Should not raise regardless of PROMETHEUS_AVAILABLE
        record_token_usage(100, 50)
        record_token_usage(0, 0)

    def test_record_workflow_completion(self):
        """Test record_workflow_completion does not raise."""
        from src.monitoring.metrics import record_workflow_completion

        # Should not raise regardless of PROMETHEUS_AVAILABLE
        record_workflow_completion("success", 10.5)
        record_workflow_completion("error", 0.1)


class TestModuleExports:
    """Test module exports."""

    def test_module_all_exports(self):
        """Test __all__ exports are accessible."""
        from src.monitoring import metrics

        for name in metrics.__all__:
            assert hasattr(metrics, name), f"Missing export: {name}"

    def test_init_exports(self):
        """Test __init__.py exports."""
        from src import monitoring

        # Check that key functions are accessible
        assert hasattr(monitoring, "get_metrics")
        assert hasattr(monitoring, "record_api_call")
        assert hasattr(monitoring, "record_api_error")
        assert hasattr(monitoring, "record_cache_access")
        assert hasattr(monitoring, "record_token_usage")
        assert hasattr(monitoring, "record_workflow_completion")
        assert hasattr(monitoring, "PROMETHEUS_AVAILABLE")


class TestPrometheusAvailability:
    """Test PROMETHEUS_AVAILABLE flag."""

    def test_prometheus_available_is_bool(self):
        """Test PROMETHEUS_AVAILABLE is a boolean."""
        from src.monitoring.metrics import PROMETHEUS_AVAILABLE

        assert isinstance(PROMETHEUS_AVAILABLE, bool)


class TestGenerateLatestStub:
    """Test generate_latest stub function."""

    def test_generate_latest_stub(self):
        """Test the stub generate_latest function."""
        from src.monitoring.metrics import PROMETHEUS_AVAILABLE

        if not PROMETHEUS_AVAILABLE:
            from src.monitoring.metrics import generate_latest

            result = generate_latest()
            assert isinstance(result, bytes)
            assert b"Prometheus" in result
