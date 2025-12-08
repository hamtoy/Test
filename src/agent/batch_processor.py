"""Batch API Processor for GOpt Phase 2 Integration.

This module provides Batch API integration for non-urgent tasks,
enabling up to 50% cost reduction by using Gemini's Batch API.

Key components:
- BatchRequest: Dataclass for individual batch requests
- BatchProcessor: Main class for JSONL building and batch job management
"""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    TypeVar,
    cast,
)

from src.config.constants import (
    BATCH_MAX_WAIT_SECONDS,
    DEFAULT_MAX_OUTPUT_TOKENS,
)

if TYPE_CHECKING:
    from src.config import AppConfig

T = TypeVar("T")
R = TypeVar("R")


class BatchJobStatus(str, Enum):
    """Status of a batch job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BatchRequest:
    """Represents a single request in a batch job.

    Follows the JSONL format specification:
    {"custom_id": "req-1", "method": "POST",
     "url": "/v1/models/gemini-flash-latest:generateContent",
     "body": {"contents": [{"parts": [{"text": "..."}]}]}}
    """

    custom_id: str
    text: str
    model_name: str = "gemini-flash-latest"
    system_instruction: str | None = None
    temperature: float = 0.2
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS

    def to_jsonl_dict(self) -> dict[str, Any]:
        """Convert to JSONL format for batch submission."""
        contents = [{"parts": [{"text": self.text}]}]

        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_output_tokens,
            },
        }

        if self.system_instruction:
            body["systemInstruction"] = {"parts": [{"text": self.system_instruction}]}

        return {
            "custom_id": self.custom_id,
            "method": "POST",
            "url": f"/v1/models/{self.model_name}:generateContent",
            "body": body,
        }


@dataclass
class BatchJobResult:
    """Result of a single request in a batch job."""

    custom_id: str
    status: str
    content: str | None = None
    error: str | None = None
    usage: dict[str, int] | None = None


@dataclass
class BatchJob:
    """Represents a batch job and its metadata."""

    job_id: str
    status: BatchJobStatus = BatchJobStatus.PENDING
    requests: list[BatchRequest] = field(default_factory=list)
    results: list[BatchJobResult] = field(default_factory=list)
    input_file_path: Path | None = None
    output_file_path: Path | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize the batch job to a dictionary."""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "request_count": len(self.requests),
            "result_count": len(self.results),
            "input_file_path": str(self.input_file_path)
            if self.input_file_path
            else None,
            "output_file_path": str(self.output_file_path)
            if self.output_file_path
            else None,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "error_message": self.error_message,
        }


class BatchProcessor:
    """Processor for Gemini Batch API operations.

    Provides functionality for:
    - Building JSONL files from OCRTask items
    - Submitting batch jobs to Gemini Batch API
    - Polling for job completion and retrieving results
    """

    def __init__(
        self,
        config: AppConfig | None = None,
        output_dir: Path | None = None,
    ) -> None:
        """Initialize the BatchProcessor.

        Args:
            config: Application configuration. If None, defaults are used.
            output_dir: Directory for storing batch files. Defaults to temp dir.
        """
        self.logger = logging.getLogger("BatchProcessor")
        self.config = config

        if output_dir:
            self.output_dir = output_dir
            self.output_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.output_dir = Path(tempfile.gettempdir()) / "batch_jobs"
            self.output_dir.mkdir(parents=True, exist_ok=True)

        # Track active jobs
        self._active_jobs: dict[str, BatchJob] = {}

        # Model name from config or default
        self.model_name = (
            getattr(config, "model_name", None) if config else "gemini-flash-latest"
        ) or "gemini-flash-latest"

    def create_batch_request(
        self,
        text: str,
        custom_id: str | None = None,
        system_instruction: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> BatchRequest:
        """Create a single batch request.

        Args:
            text: The input text for the request.
            custom_id: Unique identifier for the request. Auto-generated if None.
            system_instruction: Optional system prompt.
            temperature: Generation temperature. Defaults to config value.
            max_output_tokens: Max tokens in response. Defaults to config value.

        Returns:
            BatchRequest ready for batch submission.
        """
        if custom_id is None:
            custom_id = f"req-{uuid.uuid4().hex[:8]}"

        temp = temperature
        if temp is None:
            temp = getattr(self.config, "temperature", 0.2) if self.config else 0.2

        max_tokens = max_output_tokens
        if max_tokens is None:
            max_tokens = (
                getattr(self.config, "max_output_tokens", DEFAULT_MAX_OUTPUT_TOKENS)
                if self.config
                else DEFAULT_MAX_OUTPUT_TOKENS
            )

        return BatchRequest(
            custom_id=custom_id,
            text=text,
            model_name=self.model_name,
            system_instruction=system_instruction,
            temperature=temp,
            max_output_tokens=max_tokens,
        )

    def build_jsonl(self, requests: list[BatchRequest]) -> Path:
        """Build a JSONL file from batch requests.

        Args:
            requests: List of BatchRequest objects to include.

        Returns:
            Path to the created JSONL file.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        file_name = f"batch_{timestamp}_{uuid.uuid4().hex[:6]}.jsonl"
        file_path = self.output_dir / file_name

        with open(file_path, "w", encoding="utf-8") as f:
            for req in requests:
                line = json.dumps(req.to_jsonl_dict(), ensure_ascii=False)
                f.write(line + "\n")

        self.logger.info(
            "Created JSONL file: %s with %d requests", file_path, len(requests),
        )
        return file_path

    def create_batch_job(self, requests: list[BatchRequest]) -> BatchJob:
        """Create a new batch job from requests.

        Args:
            requests: List of BatchRequest objects.

        Returns:
            BatchJob object with generated job_id and JSONL file.
        """
        job_id = f"batch-{uuid.uuid4().hex[:12]}"
        input_file = self.build_jsonl(requests)

        job = BatchJob(
            job_id=job_id,
            requests=requests,
            input_file_path=input_file,
            status=BatchJobStatus.PENDING,
        )

        self._active_jobs[job_id] = job
        self.logger.info(
            "Created batch job: %s with %d requests", job_id, len(requests),
        )
        return job

    async def submit_batch_job(
        self,
        job: BatchJob,
        on_complete: Callable[[BatchJob], None] | None = None,
    ) -> BatchJob:
        """Submit a batch job to the Gemini Batch API.

        Note: This is a mock implementation. In production, this would
        use the actual Gemini Batch API (genai.types.BatchJob).

        Args:
            job: The BatchJob to submit.
            on_complete: Optional callback when job completes.

        Returns:
            Updated BatchJob with submission status.
        """
        if job.input_file_path is None or not job.input_file_path.exists():
            job.status = BatchJobStatus.FAILED
            job.error_message = "Input file not found"
            return job

        try:
            # NOTE: This is a mock implementation for the batch submission workflow.
            # Production integration should use the actual Gemini Batch API when
            # available, following the official API documentation.

            job.status = BatchJobStatus.PROCESSING
            self.logger.info("Submitted batch job: %s", job.job_id)

            # Simulate async processing (production would poll the actual API)
            if on_complete:
                on_complete(job)

            return job
        except Exception as e:
            job.status = BatchJobStatus.FAILED
            job.error_message = str(e)
            self.logger.error("Failed to submit batch job %s: %s", job.job_id, e)
            return job

    async def poll_batch_job(
        self,
        job: BatchJob,
        interval_seconds: float = 10.0,
        max_wait_seconds: float = BATCH_MAX_WAIT_SECONDS,
    ) -> BatchJob:
        """Poll for batch job completion.

        Args:
            job: The BatchJob to poll.
            interval_seconds: Polling interval in seconds.
            max_wait_seconds: Maximum time to wait before timing out.

        Returns:
            Updated BatchJob with final status and results.
        """
        elapsed = 0.0

        while elapsed < max_wait_seconds:
            # NOTE: Mock implementation - production should use actual API polling

            # Mock implementation: simulate completion after first poll
            if job.status == BatchJobStatus.PROCESSING:
                job.status = BatchJobStatus.COMPLETED
                job.completed_at = datetime.now(timezone.utc)

                # Generate mock results
                job.results = [
                    BatchJobResult(
                        custom_id=req.custom_id,
                        status="success",
                        content=f"Batch response for: {req.text[:50]}...",
                        usage={"prompt_tokens": 10, "completion_tokens": 20},
                    )
                    for req in job.requests
                ]

                self.logger.info(
                    "Batch job %s completed with %d results",
                    job.job_id,
                    len(job.results),
                )
                break

            await asyncio.sleep(interval_seconds)
            elapsed += interval_seconds

        if job.status != BatchJobStatus.COMPLETED:
            job.status = BatchJobStatus.FAILED
            job.error_message = "Job timed out"

        return job

    def get_job(self, job_id: str) -> BatchJob | None:
        """Retrieve a batch job by ID.

        Args:
            job_id: The job identifier.

        Returns:
            BatchJob if found, None otherwise.
        """
        return self._active_jobs.get(job_id)

    def list_jobs(
        self,
        status: BatchJobStatus | None = None,
    ) -> list[BatchJob]:
        """List all batch jobs, optionally filtered by status.

        Args:
            status: Optional status filter.

        Returns:
            List of BatchJob objects.
        """
        jobs = list(self._active_jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        return jobs

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or processing batch job.

        Args:
            job_id: The job identifier.

        Returns:
            True if cancelled successfully, False otherwise.
        """
        job = self._active_jobs.get(job_id)
        if job is None:
            return False

        if job.status in (BatchJobStatus.PENDING, BatchJobStatus.PROCESSING):
            job.status = BatchJobStatus.CANCELLED
            self.logger.info("Cancelled batch job: %s", job_id)
            return True

        return False

    def cleanup_completed_jobs(self, delete_files: bool = False) -> int:
        """Remove completed jobs from tracking.

        Args:
            delete_files: If True, also delete associated JSONL files.

        Returns:
            Number of jobs cleaned up.
        """
        completed_ids = [
            job_id
            for job_id, job in self._active_jobs.items()
            if job.status
            in (
                BatchJobStatus.COMPLETED,
                BatchJobStatus.FAILED,
                BatchJobStatus.CANCELLED,
            )
        ]

        for job_id in completed_ids:
            job = self._active_jobs.pop(job_id)
            if delete_files and job.input_file_path and job.input_file_path.exists():
                job.input_file_path.unlink()
                self.logger.debug("Deleted input file: %s", job.input_file_path)

        self.logger.info("Cleaned up %d completed jobs", len(completed_ids))
        return len(completed_ids)


# ==================== Async batch processing with rate limiting ====================


@dataclass
class BatchResult(Generic[T, R]):
    """결과 집계용 배치 처리 결과."""

    successful: list[R]
    failed: list[tuple[T, Exception]]
    total: int

    @property
    def success_rate(self) -> float:
        """성공률 계산."""
        return len(self.successful) / self.total if self.total > 0 else 0.0


class AsyncRateLimiter:
    """간단한 비동기 Rate Limiter (분당 요청 수 기준)."""

    def __init__(self, requests_per_minute: int = 60):
        """Initialize the rate limiter with a per-minute quota."""
        self.rpm = max(1, requests_per_minute)
        self.interval = 60.0 / self.rpm
        self._last_request = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until the next allowed request slot is available."""
        async with self._lock:
            now = asyncio.get_event_loop().time()
            wait_time = self._last_request + self.interval - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self._last_request = asyncio.get_event_loop().time()


# ==================== Async batch processing with rate limiting ====================


class SmartBatchProcessor(Generic[T, R]):
    """Rate limit과 재시도를 고려한 배치 처리기."""

    def __init__(
        self,
        max_concurrent: int = 5,
        requests_per_minute: int = 60,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        on_progress: Callable[[int, int], None] | None = None,
    ):
        """Initialize the smart batch processor."""
        self.semaphore = asyncio.Semaphore(max(1, max_concurrent))
        self.rate_limiter = AsyncRateLimiter(requests_per_minute)
        self.max_retries = max(0, max_retries)
        self.retry_delay = max(0.0, retry_delay)
        self.on_progress = on_progress
        self.logger = logging.getLogger(__name__)

    async def process_batch(
        self,
        items: list[T],
        processor: Callable[[T], Awaitable[R]],
    ) -> BatchResult[T, R]:
        """배치 항목들을 처리."""
        failed: list[tuple[T, Exception]] = []
        completed = 0

        async def process_with_limits(index: int, item: T) -> R | None:
            nonlocal completed
            async with self.semaphore:
                await self.rate_limiter.acquire()
                for attempt in range(self.max_retries + 1):
                    try:
                        result = await processor(item)
                        completed += 1
                        if self.on_progress:
                            self.on_progress(completed, len(items))
                        return result
                    except Exception as exc:  # noqa: BLE001, PERF203
                        if attempt >= self.max_retries:
                            self.logger.error(
                                "Item %d failed after %d retries: %s",
                                index,
                                self.max_retries + 1,
                                exc,
                            )
                            failed.append((item, exc))
                            return None

                        delay = self.retry_delay * (2**attempt)
                        self.logger.warning(
                            "Item %d attempt %d failed, retrying in %.1fs: %s",
                            index,
                            attempt + 1,
                            delay,
                            exc,
                        )
                        await asyncio.sleep(delay)
                return None

        results = await asyncio.gather(
            *(process_with_limits(i, item) for i, item in enumerate(items)),
            return_exceptions=True,
        )

        successful: list[R] = [
            cast("R", result)
            for result in results
            if result is not None and not isinstance(result, Exception)
        ]

        return BatchResult(
            successful=successful,
            failed=failed,
            total=len(items),
        )
