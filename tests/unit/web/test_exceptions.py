"""Tests for web exceptions module."""

from __future__ import annotations

import pytest

from src.web.exceptions import (
    RetryableError,
    TimeoutError,
    ValidationError,
    WorkflowExecutionError,
    WorkspaceError,
)


class TestWorkspaceError:
    """Test WorkspaceError base exception."""

    def test_workspace_error_creation(self) -> None:
        """Test basic WorkspaceError creation."""
        error = WorkspaceError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)

    def test_workspace_error_inheritance(self) -> None:
        """Test WorkspaceError inherits from Exception."""
        error = WorkspaceError("Test")
        assert isinstance(error, Exception)


class TestWorkflowExecutionError:
    """Test WorkflowExecutionError exception."""

    def test_workflow_execution_error_creation(self) -> None:
        """Test WorkflowExecutionError creation with workflow and message."""
        error = WorkflowExecutionError("test_workflow", "Something went wrong")
        assert error.workflow == "test_workflow"
        assert error.original_error is None
        assert "test_workflow" in str(error)
        assert "Something went wrong" in str(error)

    def test_workflow_execution_error_with_original_error(self) -> None:
        """Test WorkflowExecutionError with original exception."""
        original = ValueError("Original error")
        error = WorkflowExecutionError(
            "test_workflow", "Wrapped error", original_error=original
        )
        assert error.workflow == "test_workflow"
        assert error.original_error is original
        assert isinstance(error, WorkspaceError)

    def test_workflow_execution_error_message_format(self) -> None:
        """Test WorkflowExecutionError message formatting."""
        error = WorkflowExecutionError("my_workflow", "failed to execute")
        expected = "Workflow 'my_workflow' failed: failed to execute"
        assert str(error) == expected


class TestRetryableError:
    """Test RetryableError exception."""

    def test_retryable_error_creation(self) -> None:
        """Test RetryableError creation."""
        error = RetryableError("Temporary failure")
        assert str(error) == "Temporary failure"
        assert isinstance(error, WorkspaceError)

    def test_retryable_error_inheritance(self) -> None:
        """Test RetryableError inherits from WorkspaceError."""
        error = RetryableError("Test")
        assert isinstance(error, WorkspaceError)
        assert isinstance(error, Exception)


class TestTimeoutError:
    """Test TimeoutError exception."""

    def test_timeout_error_creation(self) -> None:
        """Test TimeoutError creation with operation and timeout."""
        error = TimeoutError("database_query", 30)
        assert error.operation == "database_query"
        assert error.timeout_seconds == 30
        assert "database_query" in str(error)
        assert "30" in str(error)

    def test_timeout_error_message_format(self) -> None:
        """Test TimeoutError message formatting."""
        error = TimeoutError("api_call", 60)
        expected = "Operation 'api_call' timed out after 60 seconds"
        assert str(error) == expected

    def test_timeout_error_inheritance(self) -> None:
        """Test TimeoutError inherits from WorkspaceError."""
        error = TimeoutError("test_op", 10)
        assert isinstance(error, WorkspaceError)
        assert isinstance(error, Exception)

    def test_timeout_error_with_zero_timeout(self) -> None:
        """Test TimeoutError with zero timeout value."""
        error = TimeoutError("instant_op", 0)
        assert error.timeout_seconds == 0
        assert "0 seconds" in str(error)


class TestValidationError:
    """Test ValidationError exception."""

    def test_validation_error_creation(self) -> None:
        """Test ValidationError creation with field and message."""
        error = ValidationError("email", "Invalid email format")
        assert error.field == "email"
        assert "email" in str(error)
        assert "Invalid email format" in str(error)

    def test_validation_error_message_format(self) -> None:
        """Test ValidationError message formatting."""
        error = ValidationError("username", "Too short")
        expected = "Validation failed for 'username': Too short"
        assert str(error) == expected

    def test_validation_error_inheritance(self) -> None:
        """Test ValidationError inherits from WorkspaceError."""
        error = ValidationError("field", "error")
        assert isinstance(error, WorkspaceError)
        assert isinstance(error, Exception)

    def test_validation_error_with_empty_field(self) -> None:
        """Test ValidationError with empty field name."""
        error = ValidationError("", "Missing field")
        assert error.field == ""
        assert "Missing field" in str(error)


class TestExceptionRaising:
    """Test that exceptions can be raised and caught properly."""

    def test_raise_and_catch_workspace_error(self) -> None:
        """Test raising and catching WorkspaceError."""
        with pytest.raises(WorkspaceError, match="Test error"):
            raise WorkspaceError("Test error")

    def test_raise_and_catch_workflow_execution_error(self) -> None:
        """Test raising and catching WorkflowExecutionError."""
        with pytest.raises(WorkflowExecutionError, match="my_workflow"):
            raise WorkflowExecutionError("my_workflow", "failed")

    def test_raise_and_catch_retryable_error(self) -> None:
        """Test raising and catching RetryableError."""
        with pytest.raises(RetryableError, match="Retry me"):
            raise RetryableError("Retry me")

    def test_raise_and_catch_timeout_error(self) -> None:
        """Test raising and catching TimeoutError."""
        with pytest.raises(TimeoutError, match="timed out"):
            raise TimeoutError("operation", 30)

    def test_raise_and_catch_validation_error(self) -> None:
        """Test raising and catching ValidationError."""
        with pytest.raises(ValidationError, match="Validation failed"):
            raise ValidationError("field", "error")

    def test_catch_derived_error_as_base(self) -> None:
        """Test catching derived exceptions as WorkspaceError."""
        with pytest.raises(WorkspaceError):
            raise TimeoutError("op", 10)

        with pytest.raises(WorkspaceError):
            raise ValidationError("field", "msg")

        with pytest.raises(WorkspaceError):
            raise RetryableError("msg")
