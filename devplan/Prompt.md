# 🤖 Project Auto-Improvement Prompts

> **Usage Guide:**
> Copy and paste the prompts below **one by one** into your AI agent session.
> Do **NOT** skip steps. Execute strictly in order.
>
> ⚠️ **IMPORTANT:** Before starting, ensure you have read `devplan/Project_Improvement_Exploration_Report.md`.

## 📋 Execution Checklist

| ID | Task Name | Priority | Status |
|:--:|:---|:---:|:---:|
| **PROMPT-001** | Fix Skipped Web API Tests (`test-webapi-no-key-001`) | 🟡 P2 | [ ] Ready |
| **PROMPT-002** | Sync Docs with Scripts (`docs-scripts-sync-001`) | 🟡 P2 | [ ] Ready |
| **PROMPT-003** | Refactor Settings (`refactor-settings-split-001`) | 🟢 P3 | [ ] Ready |
| **PROMPT-004** | Async File I/O (`opt-async-file-io-001`) | 🚀 OPT | [ ] Ready |
| **FINISH** | Final Verification & Cleanup | - | [ ] Ready |

---

## 🟡 [PROMPT-001] Fix Skipped Web API Tests

**Title:** Remove `@pytest.mark.skip` from Web API tests by injecting robust mocks
**Target:** `tests/test_web_api.py`, `tests/conftest.py`

**Context:**
Several Web API tests (e.g., `TestQAGeneration`, `TestWorkspace`) are currently skipped because they rely on actual LLM keys or complex async mocks that were missing. This creates a testing gap.

**Task:**

1. Analyze `tests/test_web_api.py` to identify skipped tests.
2. Update `tests/conftest.py` (or creating a new `tests/mock_web_dependencies.py`) to provide a `MockAgent` and `MockPipeline` that simulate the `GeminiAgent` interface (returning fixed JSON/Strings) without making network calls.
3. Inject these mocks into the FastAPI app using `app.dependency_overrides` or by patching the router's `agent`/`pipeline` dependencies.
4. Remove `@pytest.mark.skip` and ensure tests pass.

**Verification:**

```bash
pytest tests/test_web_api.py -v
# EXPECTED: All tests passing, 0 skipped (or significantly fewer).
```

---

## 🟡 [PROMPT-002] Sync Docs with Scripts

**Title:** Update README and docs to reflect current `scripts/` status
**Target:** `README.md`, `docs/*.md`, `scripts/`

**Context:**
The `scripts/` directory content has changed (some scripts removed/renamed), but `README.md` and other documentation files still reference old scripts (e.g., `auto_profile.py`).

**Task:**

1. List files in `scripts/` to confirm what exists.
2. Search for `python scripts/` in `README.md` and `docs/`.
3. Remove references to non-existent scripts.
4. If a script was renamed or moved (e.g., to CLI commands), update the instruction.

**Verification:**

```bash
# Manual check:
grep "python scripts/" README.md
# Ensure listed commands point to existing files.
```

---

## 🟢 [PROMPT-003] Refactor Settings

**Title:** Split `AppConfig` into modular settings classes
**Target:** `src/config/settings.py`

**Context:**
`src/config/settings.py` contains a monolithic `AppConfig` class handling LLM, DB, Web, CI, and Path settings. It is over 500 lines long and hard to maintain.

**Task:**

1. Create separate Pydantic models in `src/config/settings.py` (or new files if preferred, but keeping single file is fine for now):
    - `LLMSettings`: API keys, models, timeouts.
    - `DatabaseSettings`: Neo4j, Redis.
    - `WebSettings`: CORS, Host, Port.
2. Refactor `AppConfig` to compose these settings (e.g., `self.llm = LLMSettings()`).
3. Ensure backward compatibility (properties on `AppConfig` that proxy to sub-settings) so existing code doesn't break immediately.

**Verification:**

```bash
pytest tests/unit/config/test_config.py
# Verify no regression in config loading.
```

---

## 🚀 [PROMPT-004] Async File I/O

**Title:** Convert blocking File I/O in Async Handlers to Non-blocking
**Target:** `src/web/routers/ocr.py`, `src/web/utils.py`

**Context:**
The `api_save_ocr` endpoint allows `async def` but calls functions using `open()` or `path.write_text()`. This blocks the event loop.

**Task:**

1. Identify blocking I/O in `src/web/routers/ocr.py` (lines ~71) and `log_review_session` in `src/web/utils.py`.
2. Use `aiofiles` (if available in pyproject.toml, otherwise add it) OR usage `asyncio.to_thread` / `loop.run_in_executor` to wrap these calls.
3. Update the functions to be `async def` if necessary (and update callers).

**Verification:**

```bash
pytest tests/test_web_api.py
# Ensure OCR and Review logging endpoints still work.
```

---

## 🏁 Final Completion

**Task:**

1. Run the full test suite one last time: `pytest`.
2. Print the following success message:
    > "🎉 All pending improvements have been successfully implemented! Please review the changes."

---
