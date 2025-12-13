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
| 1 | **PROMPT-001** | Fix Config File Concurrency | P2 | ✅ Done |
| 2 | **PROMPT-002** | Add Dashboard Unit Tests | P2 | ✅ Done |
| 3 | **PROMPT-003** | Integrate Build Pipeline | P3 | ✅ Done |
| 4 | **OPT-1** | Optimize Web API with Aiofiles | OPT | ✅ Done |
| 5 | **OPT-2** | Optimize LATS Workflow Performance | OPT | ✅ Done |

**Status Summary:** Total: 5 prompts | Completed: 5 | Remaining: 0

---

## 🔧 P2 Prompts (High Priority)

### [PROMPT-001] Fix Config File Concurrency

**Directive:** Execute this prompt now, then proceed to [PROMPT-002].

**Task:**
Implement file locking mechanisms to prevent race conditions when writing to configuration files (`settings.json` or `.env`) via the `config_api`.

**Target Files:**

- `src/utils/file_lock.py` (NEW)
- `src/web/routers/config_api.py`

**Steps:**

1. Create `src/utils/file_lock.py` containing a robust `FileLock` context manager.
   - You may use a simple lock file strategy (e.g., `filename.lock`) or `portalocker`/`fasteners` if available in the environment.
   - If utilizing external libs, attempt to import them; if missing, implement a simple `fcntl` (Linux) or `msvcrt` (Windows) based fallback, or just a generic `.lock` file with PID.
   - Ideally, keep it simple: a `.lock` file that waits for release.
2. Modify `src/web/routers/config_api.py`:
   - Import the `FileLock`.
   - Wrap the file writing logic (where `files.write_text` or `json.dump` happens) within the `with FileLock(...)` block.
   - Ensure exceptions are handled and the lock is released.

**Implementation Details:**

- The lock should have a timeout to prevent infinite deadlocks.
- The `config_api` is critical; ensure 500 errors are returned if the lock cannot be acquired after retries.

**Verification:**

- Create a temporary test script that spawns multiple threads attempting to write to the same dummy config file.
- Verify that the final file content is valid JSON and not corrupted.

**Transition:**
After completing this prompt, proceed to [PROMPT-002].

---

### [PROMPT-002] Add Dashboard Unit Tests

**Directive:** Execute this prompt now, then proceed to [PROMPT-003].

**Task:**
Create unit tests for the frontend components `LogViewer` and `ConfigEditor` to ensure reliability of log parsing and form validation.

**Target Files:**

- `src/web/tests/LogViewer.test.ts` (NEW)
- `src/web/tests/ConfigEditor.test.ts` (NEW)
- `package.json` (Verify test scripts)

**Steps:**

1. Ensure `vitest` and `jsdom` are available (they should be in `devDependencies`).
2. Create `src/web/tests/LogViewer.test.ts`:
   - Mock the WebSocket connection.
   - Simulate receiving a JSON log line.
   - Verify that the processed state (lines array) updates correctly.
3. Create `src/web/tests/ConfigEditor.test.ts`:
   - Test validation logic (e.g., ensure numeric fields reject non-numeric input).
   - Mock the API `fetch` calls for save operations.
4. Run `pnpm test:unit` (or `vitest run`) to verify they pass.

**Implementation Details:**

- Use `@testing-library/react` if available, or plain `vitest` assertions on logic functions if the internal logic is separated.
- Focus on the *logic* (WebSocket message handling), not just visual rendering.

**Verification:**

- Run `npm test` or `vitest run`.
- Confirm `LogViewer.test.ts` passes.

**Transition:**
After completing this prompt, proceed to [PROMPT-003].

---

## ✨ P3 Prompts (Feature Additions)

### [PROMPT-003] Integrate Build Pipeline

**Directive:** Execute this prompt now, then proceed to [OPT-1].

**Task:**
Create a unified build script that handles both Frontend building and Backend packaging to simplify the release process.

**Target Files:**

- `scripts/build_release.py` (NEW)
- `tasks.py` (if using invoke, optional)

**Steps:**

1. Create `scripts/build_release.py`.
2. Implement a sequence:
   - Run `npm install` and `npm run build` in the frontend directory.
   - Verify `dist/` is created.
   - Copy/Move `dist/` assets to the backend static file location (e.g., `src/web/static/`).
   - Run basic backend verification (`python -m src.main --version`).
3. Add a verbose flag to show/hide output.

**Verification:**

- Run `python scripts/build_release.py`.
- Check if `src/web/static/index.html` is updated.

**Transition:**
After completing this prompt, proceed to [OPT-1].

---

## 🚀 Optimization Prompts (OPT)

### [OPT-1] Optimize Web API with Aiofiles

**Directive:** Execute this prompt now, then proceed to [OPT-2].

**Task:**
Refactor `src/web/routers/logs_api.py` to use `aiofiles` for true non-blocking file I/O, replacing `run_in_executor`.

**Target Files:**

- `src/web/routers/logs_api.py`
- `requirements.txt` / `pyproject.toml`

**Steps:**

1. Add `aiofiles` to project dependencies.
2. In `logs_api.py`, import `aiofiles`.
3. Refactor the log reading logic:
   - Instead of `await loop.run_in_executor(None, path.read_text)`, use:

     ```python
     async with aiofiles.open(path, mode='r') as f:
         content = await f.read()
     ```

   - For the tailing logic, use `async with` context managers.
4. Ensure `encoding="utf-8"` is specified.

**Verification:**

- Verify log streaming still works in the Dashboard.
- High concurrency load should show lower thread usage compared to the executor pool approach.

**Transition:**
After completing this prompt, proceed to [OPT-2].

### [OPT-2] Optimize LATS Workflow Performance

**Directive:** Execute this prompt now, then proceed to Final Completion.

**Task:**
Parallelize node expansion in the LATS (Language Agent Tree Search) engine to reduce total execution time.

**Target Files:**

- `src/lats/search.py`
- `src/agent/gemini.py`

**Steps:**

1. Identify the loop in `src/lats/search.py` where child nodes are expanded.
2. Refactor to specific `asyncio.gather(*tasks)` pattern.
3. Add a safety semaphore (e.g., `asyncio.Semaphore(5)`) to prevent hitting API rate limits if expanding many nodes at once.

**Verification:**

- Run a designated benchmark script or a complex query.
- Confirm execution time is reduced.

**Transition:**
Proceed to Final Completion.

---

## 🏁 Final Completion

**Directive:** Execute the final verification and print the completion message.

**Actions:**

1. Run a full project verify command: `pnpm run test` (or `pytest`) to ensure no regressions.
2. Ensure all prompts from the checklist are marked as Done.
3. Print the following message:

> **ALL PROMPTS COMPLETED.**
> All pending improvement and optimization items from the latest report have been applied.
> The `shining-quasar` project is now optimized, tested, and feature-complete according to the plan.
