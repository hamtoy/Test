# AI Agent Improvement Prompts

> [!IMPORTANT]
> **Execution Rules**
>
> 1. **No Chat-Only Responses**: You must always modify files using the provided tools. Do not just explain how to do it.
> 2. **Sequential Execution**: Execute the prompts in the order listed below. Do not skip prompts.
> 3. **Validation**: After each step, verify the changes (e.g., run tests or build scripts) as instructed.
> 4. **English Only**: This file and all your thought processes while executing it must be in English.

## 📋 Execution Checklist

| # | Prompt ID | Title | Priority | Status |
|:---:|:---|:---|:---:|:---:|
| 1 | PROMPT-001 | GitHub Actions CI Automation | P2 | ⬜ Pending |
| 2 | PROMPT-002 | LLM Rate Limit Fallback Strategy | P3 | ⬜ Pending |
| 3 | OPT-1 | FileLock Type Safety Improvements | OPT | ⬜ Pending |
| 4 | OPT-2 | Server Log Rotation Implementation | OPT | ⬜ Pending |

**Total: 4 prompts | Pending: 4**

---

## 🟡 Priority 2 (High)

### [PROMPT-001] GitHub Actions CI Automation

**Directive**: Execute this prompt now, then proceed to PROMPT-002.

**Task**: Create a GitHub Actions workflow to automate testing and build verification on every push and pull request.

**Target Files**:

- [NEW] `.github/workflows/ci.yml`

**Steps**:

1. Create the directory `.github/workflows` if it does not exist.
2. Create `.github/workflows/ci.yml` with the following jobs:
    - **Backend Test**: Run on `ubuntu-latest`.
        - Checkout code.
        - Set up Python 3.10.
        - Install dependencies (`pip install -e ".[dev]"`).
        - Run pytest (`pytest tests/unit`).
    - **Frontend Build**: Run on `ubuntu-latest`.
        - Checkout code.
        - Set up Node.js 18.
        - Install dependencies (`npm ci` or `pnpm install`).
        - Run build (`npm run build`).

**Implementation Details**:

- Ensure the workflow triggers on `push` to `main` and `pull_request`.
- Use `actions/checkout@v4`, `actions/setup-python@v5`, `actions/setup-node@v4`.
- For Python dependency installation, check `pyproject.toml` to confirm optional dependencies.

**Verification**:

- Since this is a CI file, you cannot run it locally without `act`. Instead, verify the file syntax by reading it back.
- Run `python -m py_compile scripts/build_release.py` to ensure no syntax errors in the build script referenced in the workflow (if applicable).

**Next**: After completing this prompt, proceed to [PROMPT-002].

---

## 🟢 Priority 3 (Medium)

### [PROMPT-002] LLM Rate Limit Fallback Strategy

**Directive**: Execute this prompt now, then proceed to OPT-1.

**Task**: Implement a model fallback mechanism in `GeminiClient` to switch to a cheaper/faster model (e.g., `gemini-flash`) when the primary model (`gemini-pro`) hits rate limits (HTTP 429).

**Target Files**:

- [MODIFY] `src/llm/gemini_client.py`

**Steps**:

1. Modify `GeminiClient` to accept a list of model names or a fallback configuration.
2. In the `generate_content` (or equivalent) method, wrap the API call in a retry loop that catches `429 Too Many Requests`.
3. If a 429 error occurs, switch the current model to the next available fallback model and retry immediately.
4. Log a warning when fallback occurs.

**Implementation Details**:

- Define a `FallbackStrategy` or simply extend the existing retry logic.
- Ensure the fallback persists for a short duration or resets for the next request depending on optimal strategy (simple fallback per request is fine).

**Verification**:

- Verify the changes by creating a test case in `tests/unit/test_gemini_client.py` (or similar) that mocks a 429 response from the first model and verifies the second model is called.
- Run `pytest tests/unit/test_gemini_client.py` (create this test file if it doesn't exist).

**Next**: After completing this prompt, proceed to [OPT-1].

---

## 🚀 Optimization (OPT)

### [OPT-1] FileLock Type Safety Improvements

**Directive**: Execute this prompt now, then proceed to OPT-2.

**Task**: Improve type safety in `src/infra/file_lock.py` by removing `Any` types and properly handling platform-specific imports (`msvcrt`, `fcntl`) using `sys.platform` checks or protocol definitions, to satisfy strict `mypy` checks.

**Target Files**:

- [MODIFY] `src/infra/file_lock.py`
- [MODIFY] `pyproject.toml`

**Steps**:

1. Remove the `warn_unused_ignores = false` override for `src.infra.file_lock` in `pyproject.toml`.
2. Refactor `src/infra/file_lock.py` to use `if sys.platform == "win32":` blocks for imports to better guide type checkers, or define a `LockProtocol` that both implementations satisfy.
3. Replace `type: ignore` with specific error codes if absolutely necessary, but aim to remove them.
4. Ensure `mypy` passes with strict settings.

**Verification**:

- Run `python -m mypy src/infra/file_lock.py` and ensure zero errors.

**Next**: After completing this prompt, proceed to [OPT-2].

---

### [OPT-2] Server Log Rotation Implementation

**Directive**: Execute this prompt now, then proceed to FINISH.

**Task**: Implement log rotation for the backend server to prevent `app.log` from growing indefinitely.

**Target Files**:

- [MODIFY] `src/infra/logging.py` (or where `setup_logging` is defined)

**Steps**:

1. Locate the logging configuration (likely in `src/infra/logging.py` or `src/main.py`).
2. Replace `FileHandler` with `logging.handlers.RotatingFileHandler`.
3. Configure it to rotate after 10MB (`maxBytes=10*1024*1024`) and keep 5 backup files (`backupCount=5`).
4. Ensure the log encoding is set to `utf-8`.

**Verification**:

- Run `python -m src.main --help` (or similar quick command) to verify the application starts and creates/writes to the log file without errors.
- Inspect the created log file to ensure content is written.

**Next**: After completing this prompt, proceed to the final step.

---

## ✅ Final Completion

**Directive**: Execute this step after completing all prompts.

**Task**: Confirm completion and run final checks.

**Steps**:

1. Run all unit tests: `python -m pytest tests/unit`.
2. Run the build script: `python scripts/build_release.py --skip-frontend` (to save time) or full build if environment allows.
3. Verify that all pending items in `Project_Improvement_Exploration_Report.md` have been addressed by the executed prompts.

**Final Output**:
Print the following message:

```
ALL PROMPTS COMPLETED. All pending improvement and optimization items from the latest report have been applied.
Ready for final review.
```
