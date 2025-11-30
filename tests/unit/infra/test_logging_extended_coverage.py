"""Additional tests for src/infra/logging.py to improve coverage."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from src.infra.logging import (
    SensitiveDataFilter,
    StructuredLogger,
    get_current_log_level,
    get_log_level,
    log_metrics,
    set_log_level,
)


class TestGetLogLevel:
    """Tests for get_log_level function."""

    def test_development_returns_debug(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test development environment returns DEBUG level."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.delenv("LOG_LEVEL_OVERRIDE", raising=False)
        assert get_log_level() == logging.DEBUG

    def test_staging_returns_info(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test staging environment returns INFO level."""
        monkeypatch.setenv("ENVIRONMENT", "staging")
        monkeypatch.delenv("LOG_LEVEL_OVERRIDE", raising=False)
        assert get_log_level() == logging.INFO

    def test_production_returns_warning(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test production environment returns WARNING level."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("LOG_LEVEL_OVERRIDE", raising=False)
        assert get_log_level() == logging.WARNING

    def test_unknown_environment_defaults_to_info(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test unknown environment defaults to INFO."""
        monkeypatch.setenv("ENVIRONMENT", "unknown")
        monkeypatch.delenv("LOG_LEVEL_OVERRIDE", raising=False)
        assert get_log_level() == logging.INFO

    def test_log_level_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test LOG_LEVEL_OVERRIDE takes precedence."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("LOG_LEVEL_OVERRIDE", "DEBUG")
        assert get_log_level() == logging.DEBUG

    def test_log_level_override_invalid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test invalid LOG_LEVEL_OVERRIDE falls back to environment."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("LOG_LEVEL_OVERRIDE", "INVALID_LEVEL")
        assert get_log_level() == logging.WARNING


class TestSetLogLevel:
    """Tests for set_log_level function."""

    def test_set_valid_level(self) -> None:
        """Test setting a valid log level returns True."""
        result = set_log_level("DEBUG")
        assert result is True
        assert logging.getLogger().level == logging.DEBUG

    def test_set_invalid_level(self) -> None:
        """Test setting an invalid log level returns False."""
        result = set_log_level("INVALID")
        assert result is False

    def test_set_all_valid_levels(self) -> None:
        """Test setting all valid log levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            result = set_log_level(level)
            assert result is True
            assert logging.getLogger().level == getattr(logging, level)


class TestGetCurrentLogLevel:
    """Tests for get_current_log_level function."""

    def test_returns_current_level_name(self) -> None:
        """Test returning the current log level name."""
        logging.getLogger().setLevel(logging.WARNING)
        assert get_current_log_level() == "WARNING"


class TestLogMetrics:
    """Tests for log_metrics function."""

    def test_log_metrics_with_tokens(self) -> None:
        """Test log_metrics with token counts."""
        mock_logger = MagicMock()
        log_metrics(
            mock_logger,
            prompt_tokens=100,
            completion_tokens=50,
        )
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "metrics" in call_args.kwargs["extra"]
        metrics = call_args.kwargs["extra"]["metrics"]
        assert metrics["prompt_tokens"] == 100
        assert metrics["completion_tokens"] == 50
        assert metrics["total_tokens"] == 150

    def test_log_metrics_with_latency(self) -> None:
        """Test log_metrics with latency."""
        mock_logger = MagicMock()
        log_metrics(
            mock_logger,
            latency_ms=500.5555,
            prompt_tokens=100,
            completion_tokens=50,
        )
        call_args = mock_logger.info.call_args
        metrics = call_args.kwargs["extra"]["metrics"]
        assert metrics["latency_ms"] == 500.56
        assert "tokens_per_sec" in metrics

    def test_log_metrics_with_cache(self) -> None:
        """Test log_metrics with cache stats."""
        mock_logger = MagicMock()
        log_metrics(
            mock_logger,
            cache_hits=8,
            cache_misses=2,
        )
        call_args = mock_logger.info.call_args
        metrics = call_args.kwargs["extra"]["metrics"]
        assert metrics["cache_hits"] == 8
        assert metrics["cache_misses"] == 2
        assert metrics["cache_hit_ratio"] == 0.8

    def test_log_metrics_with_zero_cache(self) -> None:
        """Test log_metrics with zero cache total."""
        mock_logger = MagicMock()
        log_metrics(
            mock_logger,
            cache_hits=0,
            cache_misses=0,
        )
        call_args = mock_logger.info.call_args
        metrics = call_args.kwargs["extra"]["metrics"]
        assert metrics["cache_hit_ratio"] == 0.0

    def test_log_metrics_with_api_stats(self) -> None:
        """Test log_metrics with API retry/failure stats."""
        mock_logger = MagicMock()
        log_metrics(
            mock_logger,
            api_retries=3,
            api_failures=1,
        )
        call_args = mock_logger.info.call_args
        metrics = call_args.kwargs["extra"]["metrics"]
        assert metrics["api_retries"] == 3
        assert metrics["api_failures"] == 1

    def test_log_metrics_zero_latency(self) -> None:
        """Test log_metrics with zero latency doesn't calculate tokens_per_sec."""
        mock_logger = MagicMock()
        log_metrics(
            mock_logger,
            latency_ms=0.0,
            prompt_tokens=100,
        )
        call_args = mock_logger.info.call_args
        metrics = call_args.kwargs["extra"]["metrics"]
        assert "tokens_per_sec" not in metrics


class TestStructuredLogger:
    """Tests for StructuredLogger class."""

    def test_init(self) -> None:
        """Test StructuredLogger initialization."""
        logger = StructuredLogger("test_logger")
        assert logger.logger is not None
        assert logger.logger.name == "test_logger"

    def test_log_api_call(self) -> None:
        """Test log_api_call method."""
        logger = StructuredLogger("test")
        with patch.object(logger.logger, "info") as mock_info:
            logger.log_api_call(
                model="gemini-pro",
                prompt_tokens=100,
                response_tokens=50,
                latency_ms=200.0,
                status="success",
            )
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            extra = call_args.kwargs["extra"]
            assert extra["event_type"] == "api_call"
            assert extra["model"] == "gemini-pro"
            assert extra["prompt_tokens"] == 100
            assert extra["response_tokens"] == 50
            assert extra["latency_ms"] == 200.0
            assert extra["status"] == "success"

    def test_log_cache_event_hit(self) -> None:
        """Test log_cache_event with cache hit."""
        logger = StructuredLogger("test")
        with patch.object(logger.logger, "debug") as mock_debug:
            logger.log_cache_event(
                cache_key="test_key",
                hit=True,
                ttl_remaining=300,
            )
            mock_debug.assert_called_once()
            call_args = mock_debug.call_args
            extra = call_args.kwargs["extra"]
            assert extra["event_type"] == "cache"
            assert extra["cache_key"] == "test_key"
            assert extra["hit"] is True
            assert extra["ttl_remaining"] == 300

    def test_log_cache_event_miss(self) -> None:
        """Test log_cache_event with cache miss."""
        logger = StructuredLogger("test")
        with patch.object(logger.logger, "debug") as mock_debug:
            logger.log_cache_event(
                cache_key="test_key",
                hit=False,
            )
            mock_debug.assert_called_once()
            call_args = mock_debug.call_args
            extra = call_args.kwargs["extra"]
            assert extra["hit"] is False

    def test_log_error_without_context(self) -> None:
        """Test log_error without context."""
        logger = StructuredLogger("test")
        with patch.object(logger.logger, "error") as mock_error:
            logger.log_error(
                error_type="api_error",
                message="API call failed",
            )
            mock_error.assert_called_once()
            call_args = mock_error.call_args
            extra = call_args.kwargs["extra"]
            assert extra["event_type"] == "error"
            assert extra["error_type"] == "api_error"
            assert "context" not in extra

    def test_log_error_with_context(self) -> None:
        """Test log_error with context."""
        logger = StructuredLogger("test")
        with patch.object(logger.logger, "error") as mock_error:
            logger.log_error(
                error_type="api_error",
                message="API call failed",
                context={"retry_count": 3},
            )
            mock_error.assert_called_once()
            call_args = mock_error.call_args
            extra = call_args.kwargs["extra"]
            assert extra["context"] == {"retry_count": 3}

    def test_log_workflow_started(self) -> None:
        """Test log_workflow for started stage."""
        logger = StructuredLogger("test")
        with patch.object(logger.logger, "info") as mock_info:
            logger.log_workflow(
                workflow_name="qa_pipeline",
                stage="started",
            )
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            assert "workflow:qa_pipeline:started" in call_args.args[0]
            extra = call_args.kwargs["extra"]
            assert extra["event_type"] == "workflow"
            assert extra["workflow_name"] == "qa_pipeline"
            assert extra["stage"] == "started"

    def test_log_workflow_completed_with_duration(self) -> None:
        """Test log_workflow for completed stage with duration."""
        logger = StructuredLogger("test")
        with patch.object(logger.logger, "info") as mock_info:
            logger.log_workflow(
                workflow_name="qa_pipeline",
                stage="completed",
                duration_ms=1500.5,
            )
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            extra = call_args.kwargs["extra"]
            assert extra["duration_ms"] == 1500.5

    def test_log_workflow_with_metadata(self) -> None:
        """Test log_workflow with metadata."""
        logger = StructuredLogger("test")
        with patch.object(logger.logger, "info") as mock_info:
            logger.log_workflow(
                workflow_name="qa_pipeline",
                stage="completed",
                metadata={"query_count": 5},
            )
            mock_info.assert_called_once()
            call_args = mock_info.call_args
            extra = call_args.kwargs["extra"]
            assert extra["metadata"] == {"query_count": 5}


class TestSensitiveDataFilterWithArgs:
    """Additional tests for SensitiveDataFilter."""

    # API key format: 'AIza' prefix + 35 characters = 39 total characters
    API_KEY_SUFFIX_LENGTH = 35

    def test_filter_masks_api_key_in_message(self) -> None:
        """Test filter masks API key embedded directly in log message."""
        filt = SensitiveDataFilter()
        raw_key = "AIza" + "X" * self.API_KEY_SUFFIX_LENGTH

        # Create record with API key directly in the message string
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg=f"Key: {raw_key}",
            args=(),
            exc_info=None,
            func=None,
            sinfo=None,
        )

        assert filt.filter(record)
        assert "[FILTERED_API_KEY]" in record.msg
        assert "AIza" not in record.msg

    def test_filter_non_sensitive_message_unchanged(self) -> None:
        """Test filter doesn't modify non-sensitive messages."""
        filt = SensitiveDataFilter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Safe message without sensitive data",
            args=(),
            exc_info=None,
            func=None,
            sinfo=None,
        )

        original_msg = record.msg
        assert filt.filter(record)
        assert record.msg == original_msg
