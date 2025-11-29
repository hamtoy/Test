"""Tests for the BatchProcessor module.

Tests cover:
- BatchRequest creation and JSONL conversion
- BatchProcessor JSONL building
- Batch job submission and polling
- Job management (list, get, cancel, cleanup)
"""

from typing import Any

import json
from pathlib import Path

import pytest

from src.agent.batch_processor import (
    BatchJob,
    BatchJobStatus,
    BatchProcessor,
    BatchRequest,
    BatchResult,
)


class TestBatchRequest:
    """Tests for BatchRequest dataclass."""

    def test_basic_request_creation(self) -> None:
        """Test creating a basic batch request."""
        request = BatchRequest(
            custom_id="req-001",
            text="Hello, world!",
        )

        assert request.custom_id == "req-001"
        assert request.text == "Hello, world!"
        assert request.model_name == "gemini-3-pro-preview"
        assert request.temperature == 0.2
        assert request.max_output_tokens == 2048

    def test_request_with_custom_params(self) -> None:
        """Test creating a request with custom parameters."""
        request = BatchRequest(
            custom_id="req-002",
            text="Custom request",
            model_name="gemini-2-flash",
            system_instruction="You are a helpful assistant.",
            temperature=0.7,
            max_output_tokens=4096,
        )

        assert request.model_name == "gemini-2-flash"
        assert request.system_instruction == "You are a helpful assistant."
        assert request.temperature == 0.7
        assert request.max_output_tokens == 4096

    def test_to_jsonl_dict_basic(self) -> None:
        """Test JSONL conversion without system instruction."""
        request = BatchRequest(
            custom_id="req-003",
            text="Test prompt",
            temperature=0.5,
            max_output_tokens=1024,
        )

        result = request.to_jsonl_dict()

        assert result["custom_id"] == "req-003"
        assert result["method"] == "POST"
        assert "gemini-3-pro-preview:generateContent" in result["url"]
        assert result["body"]["contents"][0]["parts"][0]["text"] == "Test prompt"
        assert result["body"]["generationConfig"]["temperature"] == 0.5
        assert result["body"]["generationConfig"]["maxOutputTokens"] == 1024
        assert "systemInstruction" not in result["body"]

    def test_to_jsonl_dict_with_system_instruction(self) -> None:
        """Test JSONL conversion with system instruction."""
        request = BatchRequest(
            custom_id="req-004",
            text="User prompt",
            system_instruction="System context",
        )

        result = request.to_jsonl_dict()

        assert (
            result["body"]["systemInstruction"]["parts"][0]["text"] == "System context"
        )


class TestBatchResult:
    """Tests for BatchResult dataclass."""

    def test_successful_result(self) -> None:
        """Test creating a successful result."""
        result = BatchResult(
            custom_id="req-001",
            status="success",
            content="Generated response",
            usage={"prompt_tokens": 10, "completion_tokens": 20},
        )

        assert result.custom_id == "req-001"
        assert result.status == "success"
        assert result.content == "Generated response"
        assert result.usage == {"prompt_tokens": 10, "completion_tokens": 20}
        assert result.error is None

    def test_failed_result(self) -> None:
        """Test creating a failed result."""
        result = BatchResult(
            custom_id="req-002",
            status="error",
            error="Rate limit exceeded",
        )

        assert result.status == "error"
        assert result.error == "Rate limit exceeded"
        assert result.content is None


class TestBatchJob:
    """Tests for BatchJob dataclass."""

    def test_job_creation(self) -> None:
        """Test creating a batch job."""
        job = BatchJob(job_id="batch-123")

        assert job.job_id == "batch-123"
        assert job.status == BatchJobStatus.PENDING
        assert len(job.requests) == 0
        assert len(job.results) == 0
        assert job.created_at is not None

    def test_job_to_dict(self) -> None:
        """Test serializing a batch job."""
        job = BatchJob(
            job_id="batch-456",
            status=BatchJobStatus.COMPLETED,
        )

        result = job.to_dict()

        assert result["job_id"] == "batch-456"
        assert result["status"] == "completed"
        assert result["request_count"] == 0
        assert result["created_at"] is not None


class TestBatchProcessor:
    """Tests for BatchProcessor class."""

    @pytest.fixture
    def processor(self, tmp_path: Path) -> Any:
        """Create a BatchProcessor with a temp directory."""
        return BatchProcessor(output_dir=tmp_path / "batch_jobs")

    def test_processor_initialization(self, processor: Any, tmp_path: Path) -> None:
        """Test processor initialization."""
        assert processor.output_dir.exists()
        assert processor.model_name == "gemini-3-pro-preview"

    def test_create_batch_request(self, processor: Any) -> None:
        """Test creating a batch request through processor."""
        request = processor.create_batch_request(
            text="Test input",
            system_instruction="Be concise",
        )

        assert request.text == "Test input"
        assert request.system_instruction == "Be concise"
        assert request.custom_id.startswith("req-")

    def test_create_batch_request_with_custom_id(self, processor: Any) -> None:
        """Test creating a request with custom ID."""
        request = processor.create_batch_request(
            text="Test",
            custom_id="my-custom-id",
        )

        assert request.custom_id == "my-custom-id"

    def test_build_jsonl(self, processor: Any) -> None:
        """Test building a JSONL file."""
        requests = [
            BatchRequest(custom_id="req-1", text="First"),
            BatchRequest(custom_id="req-2", text="Second"),
            BatchRequest(custom_id="req-3", text="Third"),
        ]

        file_path = processor.build_jsonl(requests)

        assert file_path.exists()
        assert file_path.suffix == ".jsonl"

        # Verify file contents
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()

        assert len(lines) == 3

        # Parse and verify each line
        for i, line in enumerate(lines):
            data = json.loads(line)
            assert data["custom_id"] == f"req-{i + 1}"

    def test_create_batch_job(self, processor: Any) -> None:
        """Test creating a batch job."""
        requests = [
            processor.create_batch_request("Test 1"),
            processor.create_batch_request("Test 2"),
        ]

        job = processor.create_batch_job(requests)

        assert job.job_id.startswith("batch-")
        assert job.status == BatchJobStatus.PENDING
        assert len(job.requests) == 2
        assert job.input_file_path is not None
        assert job.input_file_path.exists()

    @pytest.mark.asyncio
    async def test_submit_batch_job(self, processor: Any) -> None:
        """Test submitting a batch job."""
        requests = [processor.create_batch_request("Submit test")]
        job = processor.create_batch_job(requests)

        result = await processor.submit_batch_job(job)

        assert result.status == BatchJobStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_submit_batch_job_missing_file(self, processor: Any) -> None:
        """Test submitting a job with missing input file."""
        job = BatchJob(job_id="test-missing")
        job.input_file_path = Path("/nonexistent/file.jsonl")

        result = await processor.submit_batch_job(job)

        assert result.status == BatchJobStatus.FAILED
        assert "Input file not found" in result.error_message

    @pytest.mark.asyncio
    async def test_poll_batch_job(self, processor: Any) -> None:
        """Test polling a batch job for completion."""
        requests = [
            processor.create_batch_request("Poll test 1"),
            processor.create_batch_request("Poll test 2"),
        ]
        job = processor.create_batch_job(requests)
        await processor.submit_batch_job(job)

        result = await processor.poll_batch_job(job, interval_seconds=0.1)

        assert result.status == BatchJobStatus.COMPLETED
        assert len(result.results) == 2
        assert result.completed_at is not None

    def test_get_job(self, processor: Any) -> None:
        """Test retrieving a job by ID."""
        requests = [processor.create_batch_request("Get test")]
        job = processor.create_batch_job(requests)

        retrieved = processor.get_job(job.job_id)

        assert retrieved is not None
        assert retrieved.job_id == job.job_id

    def test_get_job_not_found(self, processor: Any) -> None:
        """Test retrieving a non-existent job."""
        result = processor.get_job("nonexistent-id")
        assert result is None

    def test_list_jobs(self, processor: Any) -> None:
        """Test listing all jobs."""
        # Create multiple jobs
        for _ in range(3):
            requests = [processor.create_batch_request("List test")]
            processor.create_batch_job(requests)

        jobs = processor.list_jobs()

        assert len(jobs) == 3

    def test_list_jobs_filtered(self, processor: Any) -> None:
        """Test listing jobs with status filter."""
        requests = [processor.create_batch_request("Filter test")]
        job = processor.create_batch_job(requests)
        job.status = BatchJobStatus.COMPLETED

        pending_jobs = processor.list_jobs(status=BatchJobStatus.PENDING)
        completed_jobs = processor.list_jobs(status=BatchJobStatus.COMPLETED)

        assert len(pending_jobs) == 0
        assert len(completed_jobs) == 1

    def test_cancel_job(self, processor: Any) -> None:
        """Test cancelling a pending job."""
        requests = [processor.create_batch_request("Cancel test")]
        job = processor.create_batch_job(requests)

        success = processor.cancel_job(job.job_id)

        assert success is True
        assert job.status == BatchJobStatus.CANCELLED

    def test_cancel_job_not_found(self, processor: Any) -> None:
        """Test cancelling a non-existent job."""
        success = processor.cancel_job("nonexistent")
        assert success is False

    def test_cancel_completed_job(self, processor: Any) -> None:
        """Test cancelling an already completed job."""
        requests = [processor.create_batch_request("Complete test")]
        job = processor.create_batch_job(requests)
        job.status = BatchJobStatus.COMPLETED

        success = processor.cancel_job(job.job_id)

        assert success is False
        assert job.status == BatchJobStatus.COMPLETED

    def test_cleanup_completed_jobs(self, processor: Any) -> None:
        """Test cleaning up completed jobs."""
        # Create and complete a job
        requests = [processor.create_batch_request("Cleanup test")]
        job = processor.create_batch_job(requests)
        job.status = BatchJobStatus.COMPLETED

        count = processor.cleanup_completed_jobs()

        assert count == 1
        assert processor.get_job(job.job_id) is None

    def test_cleanup_with_file_deletion(self, processor: Any) -> None:
        """Test cleaning up with file deletion."""
        requests = [processor.create_batch_request("File cleanup")]
        job = processor.create_batch_job(requests)
        input_file = job.input_file_path
        job.status = BatchJobStatus.COMPLETED

        count = processor.cleanup_completed_jobs(delete_files=True)

        assert count == 1
        assert not input_file.exists()


class TestBatchJobStatus:
    """Tests for BatchJobStatus enum."""

    def test_status_values(self) -> None:
        """Test that all status values are defined."""
        assert BatchJobStatus.PENDING.value == "pending"
        assert BatchJobStatus.PROCESSING.value == "processing"
        assert BatchJobStatus.COMPLETED.value == "completed"
        assert BatchJobStatus.FAILED.value == "failed"
        assert BatchJobStatus.CANCELLED.value == "cancelled"
