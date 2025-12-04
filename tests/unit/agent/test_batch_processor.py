"""Tests for SmartBatchProcessor and BatchProcessor."""
# mypy: ignore-errors

import asyncio
from pathlib import Path
from unittest.mock import Mock
from datetime import datetime, timezone

import pytest

from src.agent.batch_processor import (
    BatchJobStatus,
    BatchProcessor,
    BatchRequest,
    SmartBatchProcessor,
    BatchJob,
    BatchJobResult,
)


class TestSmartBatchProcessor:
    """Tests for SmartBatchProcessor."""

    @pytest.mark.asyncio
    async def test_batch_processor_success(self) -> None:
        processor = SmartBatchProcessor[int, int](max_concurrent=2)

        async def double(x: int) -> int:
            await asyncio.sleep(0.01)
            return x * 2

        result = await processor.process_batch([1, 2, 3], double)
        assert result.successful == [2, 4, 6]
        assert result.failed == []
        assert result.success_rate == 1.0
        assert result.total == 3

    @pytest.mark.asyncio
    async def test_batch_processor_partial_failure(self) -> None:
        processor = SmartBatchProcessor[int, int](max_retries=1)

        async def failing(x: int) -> int:
            if x == 2:
                raise ValueError("fail")
            return x

        result = await processor.process_batch([1, 2, 3], failing)
        assert len(result.failed) == 1
        assert result.success_rate == pytest.approx(2 / 3)
        assert 2 in [item for item, _ in result.failed]

    @pytest.mark.asyncio
    async def test_batch_processor_respects_rate_limit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # force rate limiter to sleep on second call
        processor = SmartBatchProcessor[int, int](
            max_concurrent=2, requests_per_minute=60
        )
        calls: list[float] = []

        async def record(x: int) -> int:
            calls.append(asyncio.get_event_loop().time())
            return x

        result = await processor.process_batch([1, 2], record)
        assert len(result.successful) == 2
        assert result.success_rate == 1.0
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_batch_processor_with_retries(self) -> None:
        """Test retry logic with intermittent failures."""
        processor = SmartBatchProcessor[int, int](max_retries=2, max_concurrent=1)
        attempt_count = {}

        async def flaky(x: int) -> int:
            attempt_count[x] = attempt_count.get(x, 0) + 1
            if attempt_count[x] < 2:  # Fail first attempt
                raise ValueError(f"Attempt {attempt_count[x]} failed")
            return x * 10

        result = await processor.process_batch([1, 2, 3], flaky)
        assert len(result.successful) == 3
        assert result.success_rate == 1.0

    @pytest.mark.asyncio
    async def test_batch_processor_empty_batch(self) -> None:
        """Test processing empty batch."""
        processor = SmartBatchProcessor[int, int]()

        async def process(x: int) -> int:
            return x

        result = await processor.process_batch([], process)
        assert result.successful == []
        assert result.failed == []
        # Empty batch has 0.0 success rate, not 1.0
        assert result.success_rate == 0.0
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_batch_processor_all_failures(self) -> None:
        """Test when all items fail."""
        processor = SmartBatchProcessor[int, int](max_retries=1)

        async def always_fail(x: int) -> int:
            raise ValueError("Always fails")

        result = await processor.process_batch([1, 2, 3], always_fail)
        assert len(result.successful) == 0
        assert len(result.failed) == 3
        assert result.success_rate == 0.0


class TestBatchJobStatus:
    """Tests for BatchJobStatus enum."""

    def test_status_values(self):
        """Test all status values are defined."""
        assert BatchJobStatus.PENDING.value == "pending"
        assert BatchJobStatus.PROCESSING.value == "processing"
        assert BatchJobStatus.COMPLETED.value == "completed"
        assert BatchJobStatus.FAILED.value == "failed"
        assert BatchJobStatus.CANCELLED.value == "cancelled"


class TestBatchRequest:
    """Tests for BatchRequest dataclass."""

    def test_create_batch_request(self):
        """Test creating a BatchRequest."""
        request = BatchRequest(
            custom_id="test-123",
            text="Test text",
            system_instruction="Test instruction",
            temperature=0.7,
            max_output_tokens=1000,
        )

        assert request.custom_id == "test-123"
        assert request.text == "Test text"
        assert request.system_instruction == "Test instruction"
        assert request.temperature == 0.7
        assert request.max_output_tokens == 1000


class TestBatchJob:
    """Tests for BatchJob dataclass."""

    def test_batch_job_creation(self):
        """Test creating a BatchJob."""
        job = BatchJob(job_id="job-123")

        assert job.job_id == "job-123"
        assert job.status == BatchJobStatus.PENDING
        assert job.requests == []
        assert job.results == []
        assert job.error_message is None

    def test_batch_job_to_dict(self):
        """Test serializing BatchJob to dictionary."""
        created_time = datetime.now(timezone.utc)
        job = BatchJob(
            job_id="job-456",
            status=BatchJobStatus.COMPLETED,
            created_at=created_time,
        )

        result = job.to_dict()

        assert result["job_id"] == "job-456"
        assert result["status"] == "completed"
        assert result["request_count"] == 0
        assert result["result_count"] == 0
        assert result["created_at"] == created_time.isoformat()
        assert result["completed_at"] is None

    def test_batch_job_with_paths(self):
        """Test BatchJob with file paths."""
        input_path = Path("/tmp/input.jsonl")
        output_path = Path("/tmp/output.jsonl")

        job = BatchJob(
            job_id="job-789",
            input_file_path=input_path,
            output_file_path=output_path,
        )

        result = job.to_dict()

        assert result["input_file_path"] == str(input_path)
        assert result["output_file_path"] == str(output_path)


class TestBatchProcessor:
    """Tests for BatchProcessor."""

    def test_batch_processor_init_default(self):
        """Test BatchProcessor initialization with defaults."""
        processor = BatchProcessor()

        assert processor.config is None
        assert processor.output_dir.exists()
        assert "batch_jobs" in str(processor.output_dir)
        assert processor.model_name == "gemini-flash-latest"

    def test_batch_processor_init_with_config(self):
        """Test BatchProcessor initialization with config."""
        mock_config = Mock()
        mock_config.model_name = "gemini-1.5-pro"

        processor = BatchProcessor(config=mock_config)

        assert processor.config == mock_config
        assert processor.model_name == "gemini-1.5-pro"

    def test_batch_processor_init_with_output_dir(self, tmp_path):
        """Test BatchProcessor with custom output directory."""
        output_dir = tmp_path / "custom_output"

        processor = BatchProcessor(output_dir=output_dir)

        assert processor.output_dir == output_dir
        assert output_dir.exists()

    def test_create_batch_request_minimal(self):
        """Test creating batch request with minimal parameters."""
        processor = BatchProcessor()

        request = processor.create_batch_request(text="Test input")

        assert request.text == "Test input"
        assert request.custom_id is not None  # Auto-generated
        assert request.system_instruction is None
        assert request.temperature is not None
        assert request.max_output_tokens is not None

    def test_create_batch_request_full(self):
        """Test creating batch request with all parameters."""
        processor = BatchProcessor()

        request = processor.create_batch_request(
            text="Test input",
            custom_id="custom-123",
            system_instruction="System prompt",
            temperature=0.8,
            max_output_tokens=2000,
        )

        assert request.text == "Test input"
        assert request.custom_id == "custom-123"
        assert request.system_instruction == "System prompt"
        assert request.temperature == 0.8
        assert request.max_output_tokens == 2000

    def test_active_jobs_tracking(self):
        """Test that active jobs are tracked."""
        processor = BatchProcessor()

        assert len(processor._active_jobs) == 0
        assert isinstance(processor._active_jobs, dict)


class TestBatchJobResult:
    """Tests for BatchJobResult dataclass."""

    def test_batch_job_result_success(self):
        """Test successful batch job result."""
        result = BatchJobResult(
            custom_id="req-123",
            status="success",
            content="Generated content",
            usage={"prompt_tokens": 100, "completion_tokens": 50},
        )

        assert result.custom_id == "req-123"
        assert result.status == "success"
        assert result.content == "Generated content"
        assert result.error is None
        assert result.usage["prompt_tokens"] == 100

    def test_batch_job_result_error(self):
        """Test failed batch job result."""
        result = BatchJobResult(
            custom_id="req-456", status="error", error="API rate limit exceeded"
        )

        assert result.custom_id == "req-456"
        assert result.status == "error"
        assert result.error == "API rate limit exceeded"
        assert result.content is None
