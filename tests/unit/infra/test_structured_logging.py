"""Tests for structured logging functionality."""
# mypy: ignore-errors

import json
import logging
from src.infra.structured_logging import JsonFormatter, setup_structured_logging


class TestJsonFormatter:
    """JsonFormatter unit tests."""

    def test_basic_log_formatting(self):
        """Test basic log message JSON formatting."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        data = json.loads(result)

        assert data["level"] == "INFO"
        assert data["logger"] == "test_logger"
        assert data["message"] == "Test message"

    def test_log_with_exception(self):
        """Test log with exception information."""
        formatter = JsonFormatter()
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            record = logging.LogRecord(
                name="test_logger",
                level=logging.ERROR,
                pathname="test.py",
                lineno=10,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )
            result = formatter.format(record)
            data = json.loads(result)

            assert data["level"] == "ERROR"
            assert "exc_info" in data
            assert "ValueError: Test error" in data["exc_info"]

    def test_log_with_stack_info(self):
        """Test log with stack trace information."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.WARNING,
            pathname="test.py",
            lineno=10,
            msg="Warning message",
            args=(),
            exc_info=None,
        )
        record.stack_info = "Stack trace here"
        result = formatter.format(record)
        data = json.loads(result)

        assert "stack" in data
        assert data["stack"] == "Stack trace here"

    def test_custom_fields_included(self):
        """Test custom fields are included in output."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Custom fields test",
            args=(),
            exc_info=None,
        )
        record.user_id = "12345"
        record.request_id = "abc-def"

        result = formatter.format(record)
        data = json.loads(result)

        assert data["user_id"] == "12345"
        assert data["request_id"] == "abc-def"

    def test_internal_fields_excluded(self):
        """Test internal fields are excluded from output."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        data = json.loads(result)

        # Internal fields should not be included
        assert "pathname" not in data
        assert "filename" not in data
        assert "lineno" not in data
        assert "funcName" not in data

    def test_private_fields_excluded(self):
        """Test fields starting with underscore are excluded."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record._private_field = "should_not_appear"
        record.public_field = "should_appear"

        result = formatter.format(record)
        data = json.loads(result)

        assert "_private_field" not in data
        assert data["public_field"] == "should_appear"


class TestSetupStructuredLogging:
    """Tests for setup_structured_logging function."""

    def test_setup_default_level(self):
        """Test setup with default INFO level."""
        setup_structured_logging()
        root = logging.getLogger()

        assert root.level == logging.INFO
        assert len(root.handlers) > 0
        assert isinstance(root.handlers[0].formatter, JsonFormatter)

    def test_setup_custom_level(self):
        """Test setup with custom log level."""
        setup_structured_logging("DEBUG")
        root = logging.getLogger()

        assert root.level == logging.DEBUG

    def test_setup_warning_level(self):
        """Test setup with WARNING level."""
        setup_structured_logging("WARNING")
        root = logging.getLogger()

        assert root.level == logging.WARNING

    def test_setup_error_level(self):
        """Test setup with ERROR level."""
        setup_structured_logging("ERROR")
        root = logging.getLogger()

        assert root.level == logging.ERROR

    def test_setup_invalid_level_defaults_to_info(self):
        """Test invalid log level defaults to INFO."""
        setup_structured_logging("INVALID_LEVEL")
        root = logging.getLogger()

        assert root.level == logging.INFO

    def test_setup_clears_existing_handlers(self):
        """Test that existing handlers are removed."""
        root = logging.getLogger()
        # Add a dummy handler
        dummy_handler = logging.StreamHandler()
        root.addHandler(dummy_handler)

        setup_structured_logging()

        # Should have exactly 1 handler (the new one)
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JsonFormatter)

    def test_setup_lowercase_level(self):
        """Test setup with lowercase level name."""
        setup_structured_logging("debug")
        root = logging.getLogger()

        assert root.level == logging.DEBUG

    def test_setup_mixed_case_level(self):
        """Test setup with mixed case level name."""
        setup_structured_logging("WaRnInG")
        root = logging.getLogger()

        assert root.level == logging.WARNING
