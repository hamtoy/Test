"""Tests for GeminiBatchClient and batch processing dataclasses."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.llm.batch import (
    BatchJob,
    BatchJobStatus,
    BatchRequest,
    BatchResult,
    GeminiBatchClient,
)


class TestBatchDataclasses:
    """Tests for batch processing dataclasses."""

    def test_batch_request_creation(self) -> None:
        """Test BatchRequest creates with auto-generated ID."""
        req = BatchRequest(prompt="Test prompt")
        assert req.prompt == "Test prompt"
        assert len(req.request_id) == 8
        assert req.temperature == 0.2

    def test_batch_request_custom_values(self) -> None:
        """Test BatchRequest with custom values."""
        req = BatchRequest(prompt="Test", request_id="custom", temperature=0.8)
        assert req.request_id == "custom"
        assert req.temperature == 0.8

    def test_batch_result_creation(self) -> None:
        """Test BatchResult creation."""
        result = BatchResult(request_id="test-id", response="Answer")
        assert result.request_id == "test-id"
        assert result.response == "Answer"
        assert result.error is None

    def test_batch_result_with_error(self) -> None:
        """Test BatchResult with error."""
        result = BatchResult(request_id="test-id", response=None, error="Failed")
        assert result.response is None
        assert result.error == "Failed"

    def test_batch_job_creation(self) -> None:
        """Test BatchJob creation."""
        job = BatchJob(
            job_id="job-123",
            status=BatchJobStatus.PENDING,
            created_at=datetime.now(),
            model_name="gemini-flash",
            total_requests=10,
        )
        assert job.job_id == "job-123"
        assert job.status == BatchJobStatus.PENDING
        assert job.total_requests == 10
        assert job.completed_requests == 0
        assert job.results == []


class TestBatchJobStatus:
    """Tests for BatchJobStatus enum."""

    def test_status_values(self) -> None:
        """Test all status values exist."""
        assert BatchJobStatus.PENDING.value == "pending"
        assert BatchJobStatus.RUNNING.value == "running"
        assert BatchJobStatus.COMPLETED.value == "completed"
        assert BatchJobStatus.FAILED.value == "failed"
        assert BatchJobStatus.CANCELLED.value == "cancelled"


class TestGeminiBatchClient:
    """Tests for GeminiBatchClient."""

    def test_client_initialization(self) -> None:
        """Test client initializes with default model."""
        client = GeminiBatchClient()
        assert client.model_name == "gemini-flash-latest"
        assert client._jobs == {}

    def test_client_custom_model(self) -> None:
        """Test client with custom model name."""
        client = GeminiBatchClient(model_name="gemini-pro")
        assert client.model_name == "gemini-pro"

    def test_submit_batch(self) -> None:
        """Test submitting a batch job."""
        client = GeminiBatchClient()
        requests = [
            BatchRequest(prompt="Question 1"),
            BatchRequest(prompt="Question 2"),
        ]

        job = client.submit_batch(requests)

        assert job.job_id.startswith("batch_")
        assert job.status == BatchJobStatus.PENDING
        assert job.total_requests == 2
        assert job.model_name == "gemini-flash-latest"

    def test_submit_batch_custom_model(self) -> None:
        """Test submitting batch with custom model."""
        client = GeminiBatchClient()
        requests = [BatchRequest(prompt="Test")]

        job = client.submit_batch(requests, model_name="gemini-pro")

        assert job.model_name == "gemini-pro"

    def test_get_status_existing(self) -> None:
        """Test getting status of existing job."""
        client = GeminiBatchClient()
        requests = [BatchRequest(prompt="Test")]
        job = client.submit_batch(requests)

        status = client.get_status(job.job_id)

        assert status is not None
        assert status.job_id == job.job_id

    def test_get_status_nonexistent(self) -> None:
        """Test getting status of nonexistent job."""
        client = GeminiBatchClient()

        status = client.get_status("nonexistent-job")

        assert status is None

    def test_get_results_not_found(self) -> None:
        """Test get_results raises for nonexistent job."""
        client = GeminiBatchClient()

        with pytest.raises(ValueError, match="Job not found"):
            client.get_results("nonexistent")

    def test_get_results_not_completed(self) -> None:
        """Test get_results raises for incomplete job."""
        client = GeminiBatchClient()
        requests = [BatchRequest(prompt="Test")]
        job = client.submit_batch(requests)

        with pytest.raises(ValueError, match="Job not completed"):
            client.get_results(job.job_id)

    def test_get_results_completed(self) -> None:
        """Test get_results returns results for completed job."""
        client = GeminiBatchClient()
        requests = [BatchRequest(prompt="Test")]
        job = client.submit_batch(requests)

        # Manually complete the job
        job.status = BatchJobStatus.COMPLETED
        job.results = [BatchResult(request_id="test", response="Answer")]

        results = client.get_results(job.job_id)

        assert len(results) == 1
        assert results[0].response == "Answer"

    def test_cancel_pending_job(self) -> None:
        """Test cancelling a pending job."""
        client = GeminiBatchClient()
        requests = [BatchRequest(prompt="Test")]
        job = client.submit_batch(requests)

        result = client.cancel(job.job_id)

        assert result is True
        status = client.get_status(job.job_id)
        assert status is not None
        assert status.status == BatchJobStatus.CANCELLED

    def test_cancel_running_job(self) -> None:
        """Test cancelling a running job."""
        client = GeminiBatchClient()
        requests = [BatchRequest(prompt="Test")]
        job = client.submit_batch(requests)
        job.status = BatchJobStatus.RUNNING

        result = client.cancel(job.job_id)

        assert result is True
        assert job.status == BatchJobStatus.CANCELLED

    def test_cancel_completed_job(self) -> None:
        """Test cancelling a completed job fails."""
        client = GeminiBatchClient()
        requests = [BatchRequest(prompt="Test")]
        job = client.submit_batch(requests)
        job.status = BatchJobStatus.COMPLETED

        result = client.cancel(job.job_id)

        assert result is False
        assert job.status == BatchJobStatus.COMPLETED

    def test_cancel_nonexistent_job(self) -> None:
        """Test cancelling nonexistent job returns False."""
        client = GeminiBatchClient()

        result = client.cancel("nonexistent")

        assert result is False

    def test_list_jobs_empty(self) -> None:
        """Test listing jobs when none exist."""
        client = GeminiBatchClient()

        jobs = client.list_jobs()

        assert jobs == []

    def test_list_jobs_all(self) -> None:
        """Test listing all jobs."""
        client = GeminiBatchClient()
        client.submit_batch([BatchRequest(prompt="Test 1")])
        client.submit_batch([BatchRequest(prompt="Test 2")])

        jobs = client.list_jobs()

        assert len(jobs) == 2

    def test_list_jobs_with_status_filter(self) -> None:
        """Test listing jobs with status filter."""
        client = GeminiBatchClient()
        job1 = client.submit_batch([BatchRequest(prompt="Test 1")])
        client.submit_batch([BatchRequest(prompt="Test 2")])
        job1.status = BatchJobStatus.COMPLETED

        pending_jobs = client.list_jobs(status=BatchJobStatus.PENDING)
        completed_jobs = client.list_jobs(status=BatchJobStatus.COMPLETED)

        assert len(pending_jobs) == 1
        assert len(completed_jobs) == 1

    def test_list_jobs_with_limit(self) -> None:
        """Test listing jobs with limit."""
        client = GeminiBatchClient()
        for i in range(5):
            client.submit_batch([BatchRequest(prompt=f"Test {i}")])

        jobs = client.list_jobs(limit=3)

        assert len(jobs) == 3

    def test_get_stats_empty(self) -> None:
        """Test stats with no jobs."""
        client = GeminiBatchClient()

        stats = client.get_stats()

        assert stats["total"] == 0
        assert stats["pending"] == 0

    def test_get_stats_with_jobs(self) -> None:
        """Test stats with various job statuses."""
        client = GeminiBatchClient()
        job1 = client.submit_batch([BatchRequest(prompt="Test 1")])
        job2 = client.submit_batch([BatchRequest(prompt="Test 2")])
        job1.status = BatchJobStatus.COMPLETED
        job2.status = BatchJobStatus.FAILED

        stats = client.get_stats()

        assert stats["total"] == 2
        assert stats["completed"] == 1
        assert stats["failed"] == 1
        assert stats["pending"] == 0
