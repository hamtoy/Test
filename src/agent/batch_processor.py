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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from src.config import AppConfig


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
     "url": "/v1/models/gemini-3-pro-preview:generateContent",
     "body": {"contents": [{"parts": [{"text": "..."}]}]}}
    """

    custom_id: str
    text: str
    model_name: str = "gemini-3-pro-preview"
    system_instruction: Optional[str] = None
    temperature: float = 0.2
    max_output_tokens: int = 2048

    def to_jsonl_dict(self) -> Dict[str, Any]:
        """Convert to JSONL format for batch submission."""
        contents = [{"parts": [{"text": self.text}]}]

        body: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_output_tokens,
            },
        }

        if self.system_instruction:
            body["systemInstruction"] = {
                "parts": [{"text": self.system_instruction}]
            }

        return {
            "custom_id": self.custom_id,
            "method": "POST",
            "url": f"/v1/models/{self.model_name}:generateContent",
            "body": body,
        }


@dataclass
class BatchResult:
    """Result of a single request in a batch job."""

    custom_id: str
    status: str
    content: Optional[str] = None
    error: Optional[str] = None
    usage: Optional[Dict[str, int]] = None


@dataclass
class BatchJob:
    """Represents a batch job and its metadata."""

    job_id: str
    status: BatchJobStatus = BatchJobStatus.PENDING
    requests: List[BatchRequest] = field(default_factory=list)
    results: List[BatchResult] = field(default_factory=list)
    input_file_path: Optional[Path] = None
    output_file_path: Optional[Path] = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the batch job to a dictionary."""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "request_count": len(self.requests),
            "result_count": len(self.results),
            "input_file_path": str(self.input_file_path) if self.input_file_path else None,
            "output_file_path": str(self.output_file_path) if self.output_file_path else None,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
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
        config: Optional["AppConfig"] = None,
        output_dir: Optional[Path] = None,
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
        self._active_jobs: Dict[str, BatchJob] = {}

        # Model name from config or default
        self.model_name = (
            getattr(config, "model_name", None)
            if config
            else "gemini-3-pro-preview"
        ) or "gemini-3-pro-preview"

    def create_batch_request(
        self,
        text: str,
        custom_id: Optional[str] = None,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
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
                getattr(self.config, "max_output_tokens", 2048)
                if self.config
                else 2048
            )

        return BatchRequest(
            custom_id=custom_id,
            text=text,
            model_name=self.model_name,
            system_instruction=system_instruction,
            temperature=temp,
            max_output_tokens=max_tokens,
        )

    def build_jsonl(self, requests: List[BatchRequest]) -> Path:
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

        self.logger.info("Created JSONL file: %s with %d requests", file_path, len(requests))
        return file_path

    def create_batch_job(self, requests: List[BatchRequest]) -> BatchJob:
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
        self.logger.info("Created batch job: %s with %d requests", job_id, len(requests))
        return job

    async def submit_batch_job(
        self,
        job: BatchJob,
        on_complete: Optional[Callable[[BatchJob], None]] = None,
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
            # In production, this would call the actual Gemini Batch API:
            # batch_job = genai.types.BatchJob.create(
            #     model=self.model_name,
            #     input_config={"jsonl_file": str(job.input_file_path)},
            # )

            job.status = BatchJobStatus.PROCESSING
            self.logger.info("Submitted batch job: %s", job.job_id)

            # Simulate async processing (in production, this would poll the API)
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
        max_wait_seconds: float = 3600.0,
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
            # In production, this would check the actual job status:
            # status = genai.types.BatchJob.get(job.job_id)

            # Mock implementation: simulate completion after first poll
            if job.status == BatchJobStatus.PROCESSING:
                job.status = BatchJobStatus.COMPLETED
                job.completed_at = datetime.now(timezone.utc)

                # Generate mock results
                job.results = [
                    BatchResult(
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

    def get_job(self, job_id: str) -> Optional[BatchJob]:
        """Retrieve a batch job by ID.

        Args:
            job_id: The job identifier.

        Returns:
            BatchJob if found, None otherwise.
        """
        return self._active_jobs.get(job_id)

    def list_jobs(
        self,
        status: Optional[BatchJobStatus] = None,
    ) -> List[BatchJob]:
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
            if job.status in (BatchJobStatus.COMPLETED, BatchJobStatus.FAILED, BatchJobStatus.CANCELLED)
        ]

        for job_id in completed_ids:
            job = self._active_jobs.pop(job_id)
            if delete_files and job.input_file_path and job.input_file_path.exists():
                job.input_file_path.unlink()
                self.logger.debug("Deleted input file: %s", job.input_file_path)

        self.logger.info("Cleaned up %d completed jobs", len(completed_ids))
        return len(completed_ids)
