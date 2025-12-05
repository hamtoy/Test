"""워크스페이스 관련 예외 정의."""
from __future__ import annotations


class WorkspaceError(Exception):
    """워크스페이스 기본 에러."""

    pass


class WorkflowExecutionError(WorkspaceError):
    """워크플로우 실행 중 발생한 에러."""

    def __init__(self, workflow: str, message: str, original_error: Exception | None = None):
        self.workflow = workflow
        self.original_error = original_error
        super().__init__(f"Workflow '{workflow}' failed: {message}")


class RetryableError(WorkspaceError):
    """재시도 가능한 에러."""

    pass


class TimeoutError(WorkspaceError):
    """타임아웃 에러."""

    def __init__(self, operation: str, timeout_seconds: int):
        self.operation = operation
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Operation '{operation}' timed out after {timeout_seconds} seconds"
        )


class ValidationError(WorkspaceError):
    """검증 실패 에러."""

    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(f"Validation failed for '{field}': {message}")
