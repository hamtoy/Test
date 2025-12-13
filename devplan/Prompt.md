# AI Agent Improvement Prompts

> **MANDATORY RULES:**
>
> 1. Execute all prompts sequentially. Do not skip any prompt.
> 2. Use file modification tools (`replace_string_in_file`, `write_to_file`) to apply changes.
> 3. Do not simply output code in chat; you must physically modify the files.
> 4. If a file does not exist, create it.
> 5. **Everything in this file must be in English.**

## ✅ Execution Checklist

| # | Prompt ID | Title | Priority | Status |
|:---:|:---|:---|:---:|:---:|
| 1 | **PROMPT-001** | Implement End-to-End Workflow Tests | P2 | ✅ Done |
| 2 | **PROMPT-002** | Enhance Dashboard UI Features | P3 | ✅ Done |
| 3 | **OPT-1** | Optimize Web API for Async I/O | OPT | ✅ Done |
| 4 | **OPT-2** | Optimize LATS Workflow Performance | OPT | ✅ Done |

**Status Summary:** Total: 4 prompts | Completed: 4 | Remaining: 0

---

## 🔧 P1 & P2 Prompts (Critical/High)

### [PROMPT-001] Implement End-to-End Workflow Tests

**Directive:** Execute this prompt now, then proceed to [PROMPT-002].

**Task:**
Create a comprehensive End-to-End (E2E) test suite that verifies the full `src.main` execution flow, from CLI invocation to output generation.

**Target Files:**

- `tests/e2e/test_cli_flow.py` (NEW)
- `tests/e2e/conftest.py` (NEW)

**Steps:**

1. Create a new directory `tests/e2e`.
2. Create `tests/e2e/conftest.py` to handle any necessary fixtures (e.g., temporary output directories).
3. Create `tests/e2e/test_cli_flow.py` using `pytest` and `subprocess` to:
   - Run the application in non-interactive mode: `python -m src.main --non-interactive --config test_config.yaml`.
   - Mock necessary external calls (LLM) if possible, or use a "dry-run" mode if available. If neither, implement utilizing `unittest.mock` to patch `src.agent.gemini.GeminiAgent.generate`.
   - Verify that the process exits with code 0.
   - Verify that output files (e.g., reports in `output/`) are actually created.
4. Ensure these tests are excluded from normal unit tests if they allow external network calls, or mark them clearly.

**Implementation Details:**

- Use `subprocess.run` to trigger the actual entry point.
- Implement a robust mock for the LLM response to ensure deterministic tests and avoid API costs.
- Check for common error cases (missing config, invalid args).

**Verification:**

- Run `pytest tests/e2e` and confirm the test passes.
- Ensure `pytest tests/unit` still passes without interference.

**Transition:**
After completing this prompt, proceed to [PROMPT-002].

---

## ✨ P3 Prompts (Medium)

### [PROMPT-002] Enhance Dashboard UI Features

**Directive:** Execute this prompt now, then proceed to [OPT-1].

**Task:**
Implement advanced controls in the Web Dashboard, specifically a Configuration Editor and a Real-time Log Viewer.

**Target Files:**

- `src/web/routers/config_api.py` (NEW)
- `src/web/routers/logs_api.py` (NEW)
- `static/src/pages/ConfigEditor.tsx` (NEW)
- `static/src/pages/LogViewer.tsx` (NEW)

**Steps:**

1. **Backend Implementation**:
   - Create `src/web/routers/config_api.py`: Implement `GET /api/config` (read settings) and `POST /api/config` (update `config/settings.yaml` or `.env`, ensuring validation).
   - Create `src/web/routers/logs_api.py`: Implement a WebSocket endpoint `/api/ws/logs` that tails the application log file and streams lines to the client.
   - Register these routers in `src/web/app.py`.

2. **Frontend Implementation** (Vite/React):
   - Create `ConfigEditor.tsx`: A form to edit key settings (LLM Model, Temperatures, Paths). Use a secure approach (password fields for implementation of API keys).
   - Create `LogViewer.tsx`: A terminal-like view that connects to the WebSocket and displays logs.
   - Update `App.tsx` or Sidebar to include links to these new pages.

**Implementation Details:**

- Ensure robust error handling for file writes (Configuration).
- Use `pydantic` models to validate incoming configuration updates.
- For the log viewer, keep a limited buffer (e.g., last 1000 lines) in the frontend to avoid browser crashes.

**Verification:**

- Start the server (`python -m src.main --web`).
- Visit the dashboard and verify you can read/write config (check file change on disk).
- Verify logs appear in real-time when actions are performed.

**Transition:**
After completing this prompt, proceed to [OPT-1].

---

## 🚀 Optimization Prompts (OPT)

### [OPT-1] Optimize Web API for Async I/O

**Directive:** Execute this prompt now, then proceed to [OPT-2].

**Task:**
Refactor synchronous file I/O operations within `src/web` routers to use improved asynchronous patterns, preventing event loop blocking.

**Target Files:**

- `src/web/routers/` (All relevant router files)
- `src/utils/file_io.py` (Helper if exists)

**Steps:**

1. Identify all occurrences of `open()`, `Path.read_text()`, or `Path.write_text()` inside `async def` route handlers.
2. Refactor them to use `aiofiles` (if installed) or `loop.run_in_executor`.
3. Example pattern:

   ```python
   # Before
   content = path.read_text()

   # After
   import asyncio
   loop = asyncio.get_running_loop()
   content = await loop.run_in_executor(None, path.read_text)
   ```

4. Update `requirements.txt` if adding `aiofiles`.

**Verification:**

- Run load tests (using `locust` or simple `ab`) to confirm that high concurrency does not block requests (e.g., `/health` should remain responsive while a large file is being read).

**Transition:**
After completing this prompt, proceed to [OPT-2].

---

### [OPT-2] Optimize LATS Workflow Performance

**Directive:** Execute this prompt now, then proceed to the Final Completion step.

**Task:**
Optimize the LATS (Language Agent Tree Search) engine by parallelizing node expansion steps.

**Target Files:**

- `src/lats/search.py`
- `src/agent/gemini.py`

**Steps:**

1. Analyze `src/lats/search.py` for loops where child nodes are expanded or evaluated sequentially.
   - Look for: `for child in nodes: await evaluate(child)`
2. Refactor to use `asyncio.gather`.
   - Change to: `await asyncio.gather(*[evaluate(child) for child in nodes])`
3. Ensure that rate limits or concurrency semaphores are respected (add a `asyncio.Semaphore` if necessary to prevent API rate limit errors).

**Verification:**

- Run the LATS performance benchmark or a sample LATS workflow.
- Measure execution time before and after for the same depth/width settings.
- Ensure no "Rate Limit Exceeded" errors occur (mock API if needed).

**Transition:**
Proceed to Final Completion.

---

## 🏁 Final Completion

**Directive:** Execute the final verification and print the completion message.

**Actions:**

1. Run a full project verify command: `pnpm run verify` (or `pytest` + `npm run build`).
2. Ensure all prompts from the checklist are marked as Done.
3. Print the following message:

> **ALL PROMPTS COMPLETED.**
> All pending improvement and optimization items from the latest report have been applied.
> The `shining-quasar` project is now optimized, tested, and feature-complete according to the plan.

<!-- END_OF_FILE -->
