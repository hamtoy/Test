"""Tests for src/monitoring/metrics.py uncovered lines."""

from unittest.mock import MagicMock, patch


from src.monitoring import metrics


class TestMetricsRecordFunctions:
    """Test metrics recording functions when Prometheus is not available."""

    @patch("src.monitoring.metrics.PROMETHEUS_AVAILABLE", False)
    def test_record_api_error_no_prometheus(self) -> None:
        """Test record_api_error when Prometheus is not available."""
        # Should not raise an error
        metrics.record_api_error(model="test-model", error_type="timeout")

    @patch("src.monitoring.metrics.PROMETHEUS_AVAILABLE", True)
    @patch("src.monitoring.metrics.api_errors")
    def test_record_api_error_with_prometheus(self, mock_api_errors: MagicMock) -> None:
        """Test record_api_error when Prometheus is available."""
        metrics.record_api_error(model="test-model", error_type="timeout")
        mock_api_errors.labels.assert_called_once_with(
            model="test-model", error_type="timeout"
        )
        mock_api_errors.labels.return_value.inc.assert_called_once()

    @patch("src.monitoring.metrics.PROMETHEUS_AVAILABLE", False)
    def test_record_cache_access_no_prometheus(self) -> None:
        """Test record_cache_access when Prometheus is not available."""
        # Should not raise an error
        metrics.record_cache_access(cache_type="memory", hit=True)
        metrics.record_cache_access(cache_type="memory", hit=False)

    @patch("src.monitoring.metrics.PROMETHEUS_AVAILABLE", True)
    @patch("src.monitoring.metrics.cache_hits")
    @patch("src.monitoring.metrics.cache_misses")
    def test_record_cache_access_hit(
        self, mock_misses: MagicMock, mock_hits: MagicMock
    ) -> None:
        """Test record_cache_access for cache hit."""
        metrics.record_cache_access(cache_type="memory", hit=True)
        mock_hits.labels.assert_called_once_with(cache_type="memory")
        mock_hits.labels.return_value.inc.assert_called_once()
        mock_misses.labels.assert_not_called()

    @patch("src.monitoring.metrics.PROMETHEUS_AVAILABLE", True)
    @patch("src.monitoring.metrics.cache_hits")
    @patch("src.monitoring.metrics.cache_misses")
    def test_record_cache_access_miss(
        self, mock_misses: MagicMock, mock_hits: MagicMock
    ) -> None:
        """Test record_cache_access for cache miss."""
        metrics.record_cache_access(cache_type="memory", hit=False)
        mock_misses.labels.assert_called_once_with(cache_type="memory")
        mock_misses.labels.return_value.inc.assert_called_once()
        mock_hits.labels.assert_not_called()

    @patch("src.monitoring.metrics.PROMETHEUS_AVAILABLE", False)
    def test_record_token_usage_no_prometheus(self) -> None:
        """Test record_token_usage when Prometheus is not available."""
        # Should not raise an error
        metrics.record_token_usage(prompt_tokens=100, completion_tokens=50)

    @patch("src.monitoring.metrics.PROMETHEUS_AVAILABLE", True)
    @patch("src.monitoring.metrics.token_usage")
    def test_record_token_usage_with_prometheus(
        self, mock_token_usage: MagicMock
    ) -> None:
        """Test record_token_usage when Prometheus is available."""
        metrics.record_token_usage(prompt_tokens=100, completion_tokens=50)
        assert mock_token_usage.labels.call_count == 2
        mock_token_usage.labels.assert_any_call(type="prompt")
        mock_token_usage.labels.assert_any_call(type="completion")

    @patch("src.monitoring.metrics.PROMETHEUS_AVAILABLE", False)
    def test_record_workflow_completion_no_prometheus(self) -> None:
        """Test record_workflow_completion when Prometheus is not available."""
        # Should not raise an error
        metrics.record_workflow_completion(status="success", duration_seconds=1.5)

    @patch("src.monitoring.metrics.PROMETHEUS_AVAILABLE", True)
    @patch("src.monitoring.metrics.workflow_status")
    @patch("src.monitoring.metrics.workflow_duration")
    def test_record_workflow_completion_with_prometheus(
        self, mock_duration: MagicMock, mock_status: MagicMock
    ) -> None:
        """Test record_workflow_completion when Prometheus is available."""
        metrics.record_workflow_completion(status="success", duration_seconds=1.5)
        mock_status.labels.assert_called_once_with(status="success")
        mock_status.labels.return_value.inc.assert_called_once()
        mock_duration.observe.assert_called_once_with(1.5)
