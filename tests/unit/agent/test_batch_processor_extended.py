"""Extended tests for batch_processor module to increase coverage."""
# mypy: ignore-errors

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.agent.batch_processor import (
    AsyncRateLimiter,
    BatchJob,
    BatchJobResult,
    BatchJobStatus,
    BatchProcessor,
    BatchRequest,
    BatchResult,
    SmartBatchProcessor,
)


class TestBatchRequest:
    """Tests for BatchRequest dataclass."""

    def test_to_jsonl_dict_basic(self):
        """Test basic JSONL dict conversion."""
        req = BatchRequest(
            custom_id="test-123",
            text="Test text",
            model_name="gemini-flash",
        )

        result = req.to_jsonl_dict()

        assert result["custom_id"] == "test-123"
        assert result["method"] == "POST"
        assert result["url"] == "/v1/models/gemini-flash:generateContent"
        assert result["body"]["contents"][0]["parts"][0]["text"] == "Test text"
        assert result["body"]["generationConfig"]["temperature"] == 0.2

    def test_to_jsonl_dict_with_system_instruction(self):
        """Test JSONL dict with system instruction."""
        req = BatchRequest(
            custom_id="test-456",
            text="Query text",
            system_instruction="You are a helpful assistant",
            temperature=0.5,
            max_output_tokens=2048,
        )

        result = req.to_jsonl_dict()

        assert "systemInstruction" in result["body"]
        assert (
            result["body"]["systemInstruction"]["parts"][0]["text"]
            == "You are a helpful assistant"
        )
        assert result["body"]["generationConfig"]["temperature"] == 0.5
        assert result["body"]["generationConfig"]["maxOutputTokens"] == 2048


class TestBatchJobResult:
    """Tests for BatchJobResult dataclass."""

    def test_batch_job_result_success(self):
        """Test successful result creation."""
        result = BatchJobResult(
            custom_id="req-1",
            status="success",
            content="Response text",
            usage={"prompt_tokens": 10, "completion_tokens": 20},
        )

        assert result.custom_id == "req-1"
        assert result.status == "success"
        assert result.content == "Response text"
        assert result.usage == {"prompt_tokens": 10, "completion_tokens": 20}

    def test_batch_job_result_error(self):
        """Test error result creation."""
        result = BatchJobResult(
            custom_id="req-2",
            status="error",
            error="API error occurred",
        )

        assert result.status == "error"
        assert result.error == "API error occurred"
        assert result.content is None


class TestBatchJob:
    """Tests for BatchJob dataclass."""

    def test_batch_job_to_dict(self):
        """Test batch job serialization."""
        created_time = datetime.now(timezone.utc)
        job = BatchJob(
            job_id="job-123",
            status=BatchJobStatus.COMPLETED,
            requests=[
                BatchRequest(custom_id="r1", text="Text 1"),
                BatchRequest(custom_id="r2", text="Text 2"),
            ],
            results=[
                BatchJobResult(custom_id="r1", status="success", content="Result 1"),
            ],
            input_file_path=Path("/tmp/input.jsonl"),
            created_at=created_time,
        )

        result = job.to_dict()

        assert result["job_id"] == "job-123"
        assert result["status"] == "completed"
        assert result["request_count"] == 2
        assert result["result_count"] == 1
        assert result["input_file_path"] == str(Path("/tmp/input.jsonl"))
        assert result["created_at"] == created_time.isoformat()

    def test_batch_job_to_dict_with_none_paths(self):
        """Test batch job serialization with None paths."""
        job = BatchJob(job_id="job-456")

        result = job.to_dict()

        assert result["input_file_path"] is None
        assert result["output_file_path"] is None
        assert result["completed_at"] is None


class TestBatchProcessor:
    """Extended tests for BatchProcessor."""

    def test_init_with_config(self):
        """Test processor initialization with config."""
        config = Mock()
        config.model_name = "gemini-pro"
        config.temperature = 0.3
        config.max_output_tokens = 4096

        processor = BatchProcessor(config=config)

        assert processor.config == config
        assert processor.model_name == "gemini-pro"

    def test_init_with_custom_output_dir(self, tmp_path):
        """Test processor with custom output directory."""
        output_dir = tmp_path / "batch_output"

        processor = BatchProcessor(output_dir=output_dir)

        assert processor.output_dir == output_dir
        assert processor.output_dir.exists()

    def test_create_batch_request_with_all_params(self):
        """Test creating batch request with all parameters."""
        config = Mock()
        config.temperature = 0.5
        config.max_output_tokens = 2048
        config.model_name = "gemini-flash"

        processor = BatchProcessor(config=config)

        req = processor.create_batch_request(
            text="Test query",
            custom_id="custom-123",
            system_instruction="Be helpful",
            temperature=0.7,
            max_output_tokens=4096,
        )

        assert req.custom_id == "custom-123"
        assert req.text == "Test query"
        assert req.system_instruction == "Be helpful"
        assert req.temperature == 0.7
        assert req.max_output_tokens == 4096

    def test_create_batch_request_auto_id(self):
        """Test auto-generation of custom_id."""
        processor = BatchProcessor()

        req = processor.create_batch_request(text="Test")

        assert req.custom_id.startswith("req-")
        assert len(req.custom_id) > 4

    def test_build_jsonl(self, tmp_path):
        """Test JSONL file building."""
        processor = BatchProcessor(output_dir=tmp_path)

        requests = [
            BatchRequest(custom_id="r1", text="Text 1"),
            BatchRequest(custom_id="r2", text="Text 2"),
        ]

        file_path = processor.build_jsonl(requests)

        assert file_path.exists()
        assert file_path.suffix == ".jsonl"

        # Verify file content
        with open(file_path, "r") as f:
            lines = f.readlines()

        assert len(lines) == 2
        data1 = json.loads(lines[0])
        assert data1["custom_id"] == "r1"

    def test_create_batch_job(self, tmp_path):
        """Test batch job creation."""
        processor = BatchProcessor(output_dir=tmp_path)

        requests = [
            BatchRequest(custom_id="r1", text="Text 1"),
        ]

        job = processor.create_batch_job(requests)

        assert job.job_id.startswith("batch-")
        assert job.status == BatchJobStatus.PENDING
        assert len(job.requests) == 1
        assert job.input_file_path.exists()
        assert job.job_id in processor._active_jobs

    @pytest.mark.asyncio
    async def test_submit_batch_job_success(self, tmp_path):
        """Test successful batch job submission."""
        processor = BatchProcessor(output_dir=tmp_path)
        requests = [BatchRequest(custom_id="r1", text="Text 1")]
        job = processor.create_batch_job(requests)

        callback_called = False

        def on_complete(j):
            nonlocal callback_called
            callback_called = True

        result = await processor.submit_batch_job(job, on_complete=on_complete)

        assert result.status == BatchJobStatus.PROCESSING
        assert callback_called

    @pytest.mark.asyncio
    async def test_submit_batch_job_no_input_file(self):
        """Test batch job submission without input file."""
        processor = BatchProcessor()
        job = BatchJob(job_id="test-job", input_file_path=None)

        result = await processor.submit_batch_job(job)

        assert result.status == BatchJobStatus.FAILED
        assert "Input file not found" in result.error_message

    @pytest.mark.asyncio
    async def test_poll_batch_job_success(self, tmp_path):
        """Test polling batch job to completion."""
        processor = BatchProcessor(output_dir=tmp_path)
        requests = [BatchRequest(custom_id="r1", text="Text 1")]
        job = processor.create_batch_job(requests)
        job.status = BatchJobStatus.PROCESSING

        result = await processor.poll_batch_job(
            job, interval_seconds=0.1, max_wait_seconds=1
        )

        assert result.status == BatchJobStatus.COMPLETED
        assert result.completed_at is not None
        assert len(result.results) == 1
        assert result.results[0].custom_id == "r1"

    @pytest.mark.asyncio
    async def test_poll_batch_job_timeout(self):
        """Test polling timeout."""
        processor = BatchProcessor()
        job = BatchJob(job_id="test-job", status=BatchJobStatus.PENDING)

        result = await processor.poll_batch_job(
            job, interval_seconds=0.1, max_wait_seconds=0.2
        )

        assert result.status == BatchJobStatus.FAILED
        assert "timed out" in result.error_message.lower()

    def test_get_job(self, tmp_path):
        """Test retrieving job by ID."""
        processor = BatchProcessor(output_dir=tmp_path)
        requests = [BatchRequest(custom_id="r1", text="Text 1")]
        job = processor.create_batch_job(requests)

        retrieved = processor.get_job(job.job_id)

        assert retrieved is not None
        assert retrieved.job_id == job.job_id

    def test_get_job_not_found(self):
        """Test retrieving non-existent job."""
        processor = BatchProcessor()

        result = processor.get_job("non-existent-id")

        assert result is None

    def test_list_jobs_all(self, tmp_path):
        """Test listing all jobs."""
        processor = BatchProcessor(output_dir=tmp_path)

        job1 = processor.create_batch_job([BatchRequest(custom_id="r1", text="1")])
        job2 = processor.create_batch_job([BatchRequest(custom_id="r2", text="2")])

        jobs = processor.list_jobs()

        assert len(jobs) == 2
        assert job1 in jobs
        assert job2 in jobs

    def test_list_jobs_filtered(self, tmp_path):
        """Test listing jobs with status filter."""
        processor = BatchProcessor(output_dir=tmp_path)

        job1 = processor.create_batch_job([BatchRequest(custom_id="r1", text="1")])
        job2 = processor.create_batch_job([BatchRequest(custom_id="r2", text="2")])
        job2.status = BatchJobStatus.COMPLETED

        pending_jobs = processor.list_jobs(status=BatchJobStatus.PENDING)

        assert len(pending_jobs) == 1
        assert pending_jobs[0].job_id == job1.job_id

    def test_cancel_job(self, tmp_path):
        """Test cancelling a job."""
        processor = BatchProcessor(output_dir=tmp_path)
        job = processor.create_batch_job([BatchRequest(custom_id="r1", text="1")])

        result = processor.cancel_job(job.job_id)

        assert result is True
        assert job.status == BatchJobStatus.CANCELLED

    def test_cancel_completed_job(self, tmp_path):
        """Test cancelling already completed job."""
        processor = BatchProcessor(output_dir=tmp_path)
        job = processor.create_batch_job([BatchRequest(custom_id="r1", text="1")])
        job.status = BatchJobStatus.COMPLETED

        result = processor.cancel_job(job.job_id)

        assert result is False

    def test_cancel_nonexistent_job(self):
        """Test cancelling non-existent job."""
        processor = BatchProcessor()

        result = processor.cancel_job("non-existent")

        assert result is False

    def test_cleanup_completed_jobs(self, tmp_path):
        """Test cleanup of completed jobs."""
        processor = BatchProcessor(output_dir=tmp_path)

        job1 = processor.create_batch_job([BatchRequest(custom_id="r1", text="1")])
        job2 = processor.create_batch_job([BatchRequest(custom_id="r2", text="2")])
        job1.status = BatchJobStatus.COMPLETED
        job2.status = BatchJobStatus.FAILED

        count = processor.cleanup_completed_jobs(delete_files=False)

        assert count == 2
        assert len(processor._active_jobs) == 0

    def test_cleanup_with_file_deletion(self, tmp_path):
        """Test cleanup with file deletion."""
        processor = BatchProcessor(output_dir=tmp_path)
        job = processor.create_batch_job([BatchRequest(custom_id="r1", text="1")])
        job.status = BatchJobStatus.COMPLETED
        input_file = job.input_file_path

        assert input_file.exists()

        count = processor.cleanup_completed_jobs(delete_files=True)

        assert count == 1
        assert not input_file.exists()


class TestAsyncRateLimiter:
    """Tests for AsyncRateLimiter."""

    @pytest.mark.asyncio
    async def test_rate_limiter_basic(self):
        """Test basic rate limiting."""
        limiter = AsyncRateLimiter(requests_per_minute=60)

        start = asyncio.get_event_loop().time()
        await limiter.acquire()
        await limiter.acquire()
        end = asyncio.get_event_loop().time()

        # Should take at least 1 second for 60 RPM
        elapsed = end - start
        assert elapsed >= 0.9  # Allow some tolerance

    @pytest.mark.asyncio
    async def test_rate_limiter_respects_rpm(self):
        """Test RPM enforcement."""
        limiter = AsyncRateLimiter(requests_per_minute=120)  # 2 per second

        start = asyncio.get_event_loop().time()
        for _ in range(3):
            await limiter.acquire()
        end = asyncio.get_event_loop().time()

        elapsed = end - start
        # 3 requests at 120 RPM = ~1.5 seconds
        assert elapsed >= 0.9


class TestBatchResult:
    """Tests for BatchResult generic class."""

    def test_batch_result_success_rate(self):
        """Test success rate calculation."""
        result = BatchResult(
            successful=[1, 2, 3],
            failed=[],
            total=3,
        )

        assert result.success_rate == 1.0

    def test_batch_result_partial_success(self):
        """Test partial success rate."""
        result = BatchResult(
            successful=[1, 2],
            failed=[(3, Exception("error"))],
            total=3,
        )

        assert result.success_rate == pytest.approx(2 / 3)

    def test_batch_result_zero_total(self):
        """Test success rate with zero total."""
        result = BatchResult(
            successful=[],
            failed=[],
            total=0,
        )

        assert result.success_rate == 0.0


class TestSmartBatchProcessorExtended:
    """Extended tests for SmartBatchProcessor."""

    @pytest.mark.asyncio
    async def test_progress_callback(self):
        """Test progress callback invocation."""
        progress_updates = []

        def on_progress(completed, total):
            progress_updates.append((completed, total))

        processor = SmartBatchProcessor[int, int](
            max_concurrent=2,
            on_progress=on_progress,
        )

        async def process(x: int) -> int:
            await asyncio.sleep(0.01)
            return x * 2

        await processor.process_batch([1, 2, 3], process)

        assert len(progress_updates) == 3
        assert progress_updates[-1] == (3, 3)

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test exponential backoff on retries."""
        processor = SmartBatchProcessor[int, int](
            max_retries=2,
            retry_delay=0.1,
        )

        attempt_times = []

        async def failing(x: int) -> int:
            attempt_times.append(asyncio.get_event_loop().time())
            if len(attempt_times) < 3:
                raise ValueError("retry")
            return x

        result = await processor.process_batch([1], failing)

        assert len(result.successful) == 1
        # Check exponential backoff timing
        if len(attempt_times) >= 3:
            delay1 = attempt_times[1] - attempt_times[0]
            delay2 = attempt_times[2] - attempt_times[1]
            # Second delay should be ~2x first delay
            assert delay2 > delay1 * 1.5

    @pytest.mark.asyncio
    async def test_mixed_success_and_failure(self):
        """Test batch with both successes and failures."""
        processor = SmartBatchProcessor[int, int](max_retries=1)

        async def mixed(x: int) -> int:
            if x % 2 == 0:
                raise ValueError("even number")
            return x * 10

        result = await processor.process_batch([1, 2, 3, 4, 5], mixed)

        assert len(result.successful) == 3  # 1, 3, 5
        assert len(result.failed) == 2  # 2, 4
        assert result.success_rate == 0.6
