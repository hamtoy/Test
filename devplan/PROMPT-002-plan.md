## PROMPT-002 — Agent Core Module Split (WIP)

### Goal
- Break down `src/agent/core.py` (≈1k lines) into focused components to improve maintainability and testing.

### References
- `Project_Evaluation_Report.md`: Core file size flagged as P2 refactor target.
- `Project_Improvement_Exploration_Report.md`: P2-2 `refactor-agent-core-split` (code quality).

### Target Structure (proposed)
- `src/agent/client.py` — Gemini API client wrapper (request/response, retries).
- `src/agent/context_manager.py` — context caching, budget tracking, metrics.
- `src/agent/retry_handler.py` — tenacity/backoff policies, rate-limit handling.
- `src/agent/core.py` — thin facade (`GeminiAgent`) orchestrating the above.

### Incremental Steps
1) Extract low-level API call logic (current `_call_api_with_retry`, budgeting, telemetry) into `client.py`, keep interfaces stable.
2) Extract cache/budget/context handling helpers into `context_manager.py`; route existing cache-hit/miss metrics through this layer.
3) Isolate retry/backoff policies into `retry_handler.py`; import into client.
4) Trim `GeminiAgent` to composition of the above; keep public methods and signatures unchanged to protect tests.
5) Add unit tests for each new component (API client, context manager, retry handler) with lightweight mocks.
6) Update imports/usages across agents, routers, and tests; ensure mypy/pytest pass.

### Acceptance
- No public API breakage for `GeminiAgent`.
- mypy strict + pytest all pass.
- Core file reduced significantly; responsibilities isolated.
