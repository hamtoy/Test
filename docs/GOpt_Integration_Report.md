# GOpt Integration Report

## 1. Executive Summary

This report analyzes the integration of Google's GOpt (Gemini Optimization) features into the `shining-quasar` codebase. It identifies gaps between the current implementation and GOpt best practices, specifically focusing on Context Caching and Batch Processing.

## 2. Gap Analysis

### 2.1 Context Caching

**Current Status:**

- **Implemented:** Caching is actively used in `evaluate_responses` and `rewrite_best_answer` methods in `src/agent/core.py`.
- **Missing:** The `generate_query` method does not currently utilize caching.
- **Impact:** Approximately 33% of API calls (Query Generation) miss the cache benefit, not 50% as previously estimated.

**Configuration:**

- **Current TTL:** Default is 10 minutes (`GEMINI_CACHE_TTL_MINUTES` in `src/config/settings.py`).
- **Issue:** 10 minutes is too short for effective batch processing or long-running sessions.

### 2.2 Batch Processing

**Current Status:**

- **API Usage:** `GeminiAgent` correctly uses the asynchronous `generate_content_async` API. There is no synchronous blocking issue.
- **Worker:** `src/infra/worker.py` implements a Redis-based worker compatible with batch processing concepts.

**Blockers:**

- **Format:** Batch API requires a specific JSONL submission format which is not yet implemented.
- **Submission:** A dedicated endpoint/method to submit these JSONL files to the Batch API is missing.

## 3. Integration Strategy

### Phase 0: Verification (Already Implemented) ✅

The following features are already present in the codebase:

- **Budget Tracking:** Implemented in `src/infra/worker.py` using `BudgetTracker`.
- **Cache Analytics:** `CacheManager` tracks hits/misses.
- **LATS Integration:** `worker.py` integrates LATS with budget constraints.

### Phase 1: Caching Expansion (Quick Win)

**Goal:** Enable caching for Query Generation and optimize TTL.

**Implementation Details:**

1. **Update `generate_query` Signature:**
    Modify `src/agent/core.py` to accept `cached_content`.

    ```python
    # src/agent/core.py

    async def generate_query(
        self, 
        ocr_text: str, 
        user_intent: Optional[str] = None,
        cached_content: Optional["caching.CachedContent"] = None  # Add this
    ) -> List[str]:
        # ...
        model = self._create_generative_model(
            system_prompt, 
            response_schema=QueryResult,
            cached_content=cached_content  # Pass to model creation
        )
        # ...
    ```

    Update `src/config/settings.py` or environment variable `GEMINI_CACHE_TTL_MINUTES` to **360 minutes (6 hours)** to support longer batch windows.

### Verification Plan (Test Code)

```python
async def test_generate_query_with_cache(mocker):
    mock_cache = mocker.Mock()
    agent = GeminiAgent(config)
    
    queries = await agent.generate_query(
        "OCR text...", 
        cached_content=mock_cache
    )
    
    # Verify cached_content is passed to _create_generative_model
    agent._create_generative_model.assert_called_once_with(
        mocker.ANY, 
        response_schema=mocker.ANY, 
        cached_content=mock_cache
    )
```

### Phase 2: Batch API Integration (Medium Effort) ✅

**Goal:** Reduce costs by 50% for non-urgent tasks using Gemini Batch API.

**Implementation Status:** COMPLETED

1. **Batch Processor:** ✅ Created `src/agent/batch_processor.py`.
2. **JSONL Builder:** ✅ Implemented `BatchRequest.to_jsonl_dict()` and `BatchProcessor.build_jsonl()`.
3. **Submission:** ✅ Implemented `BatchProcessor.submit_batch_job()` method.
4. **Polling:** ✅ Implemented `BatchProcessor.poll_batch_job()` method.

**Key Components Implemented:**

- `BatchRequest`: Dataclass for individual batch requests with JSONL format conversion.
- `BatchResult`: Dataclass for batch job results.
- `BatchJob`: Dataclass for tracking batch job metadata and status.
- `BatchJobStatus`: Enum for job status tracking (PENDING, PROCESSING, COMPLETED, FAILED, CANCELLED).
- `BatchProcessor`: Main class providing:
  - `create_batch_request()`: Create batch requests with custom parameters.
  - `build_jsonl()`: Build JSONL files from batch requests.
  - `create_batch_job()`: Create and track batch jobs.
  - `submit_batch_job()`: Submit jobs for processing.
  - `poll_batch_job()`: Poll for job completion.
  - `get_job()`, `list_jobs()`: Job retrieval and listing.
  - `cancel_job()`: Cancel pending/processing jobs.
  - `cleanup_completed_jobs()`: Clean up completed jobs and files.

**Tests:** 26 tests in `tests/test_batch_processor.py` covering all components.

### JSONL Format Specification

```jsonl
{"custom_id": "req-1", "method": "POST", "url": "/v1/models/gemini-3-pro-preview:generateContent", "body": {"contents": [{"parts": [{"text": "..."}]}]}}
{"custom_id": "req-2", "method": "POST", "url": "/v1/models/gemini-3-pro-preview:generateContent", "body": {"contents": [{"parts": [{"text": "..."}]}]}}
```

**Usage Example:**

```python
from src.agent.batch_processor import BatchProcessor

# Initialize processor
processor = BatchProcessor(output_dir=Path("./batch_output"))

# Create batch requests
requests = [
    processor.create_batch_request("OCR text 1", custom_id="task-001"),
    processor.create_batch_request("OCR text 2", custom_id="task-002"),
]

# Create and submit batch job
job = processor.create_batch_job(requests)
await processor.submit_batch_job(job)

# Poll for completion
result = await processor.poll_batch_job(job)
print(f"Job {result.job_id} completed with {len(result.results)} results")
```

## 4. Expected Impact

- **Cost:** 33% reduction for query generation; ~50% reduction for batchable workloads.
- **Cache Hit Rate:** Expected increase from 40% to 65% (Phase 1).
- **Latency:** Significant reduction for `generate_query` when cache is hit.

## 5. Recommendations

1. **Immediate Action (Phase 1):** Implement `generate_query` caching (10-20 mins work).
2. **Short-term Action:** Increase TTL to 360 minutes via environment variable.
3. **Mid-term Action (Phase 2):** Implement Batch API integration (2-3 days work) for non-urgent background tasks.
