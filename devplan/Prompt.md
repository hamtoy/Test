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
| 1 | PROMPT-001 | LLM Rate Limit Fallback Strategy | P2 | ⏸️ Skipped |
| 2 | PROMPT-002 | LATS Agent Verification Optimization | P3 | ✅ Complete |
| 3 | OPT-1 | FileLock Type Safety Improvements | OPT | ✅ Complete |

**Total: 3 prompts | Completed: 2 | Skipped: 1**

---

## 🟡 Priority 2 (High)

### [PROMPT-001] LLM Rate Limit Fallback Strategy

**Directive**: Execute this prompt now, then proceed to PROMPT-002.

**Task**: Implement a model fallback mechanism in `GeminiModelClient` to automatically switch to a secondary model (e.g., `gemini-flash`) when the primary model hits a rate limit (HTTP 429).

**Target Files**:

- [MODIFY] `src/llm/gemini.py`
- [NEW] `tests/unit/llm/test_gemini_fallback.py`

**Steps**:

1. Modify `src/llm/gemini.py`:
   - Update `GeminiModelClient` constructor to accept a list of `fallback_models`.
   - Update `generate` method to wrap the API call in a loop.
   - If `google_exceptions.ResourceExhausted` (429) occurs, log a warning and retry with the next model in the list.
   - If all models fail, raise the exception or return an error message.
2. Create `tests/unit/llm/test_gemini_fallback.py`:
   - Use `unittest.mock` to simulate a 429 error on the first call and success on the second.
   - Verify that the fallback model is actually used.

**Verification**:

- Run the new test: `uv run pytest tests/unit/llm/test_gemini_fallback.py`
- Ensure 2 passing tests (one for fallback success, one for exhaustion failure).

**Next**: After completing this prompt, proceed to [PROMPT-002].

---

## 🟢 Priority 3 (Medium)

### [PROMPT-002] LATS Agent Verification Optimization

**Directive**: Execute this prompt now, then proceed to OPT-1.

**Task**: Enhance the validation logic in the LATS (Language Agent Tree Search) module to improve reasoning accuracy by integrating `ActionExecutor` feedback.

**Target Files**:

- [MODIFY] `src/features/lats/lats.py` (or main LATS implementation file)
- [MODIFY] `src/features/action_executor.py`

**Steps**:

1. Locate the LATS evaluation/validation step in `src/features/lats`.
2. Integrate `ActionExecutor` to run a concrete validation check (e.g., checking if the generated answer satisfies constraints) at each leaf node expansion.
3. Improve the heuristic value function to penalize nodes that fail the concrete validation.
4. Add debug logging to trace tree pruning decisions.

**Verification**:

- Verify that the LATS agent can solve a complex query that requires validation.
- Run `uv run pytest tests/e2e/test_lats.py` (if available, or create a simple script `scripts/test_lats_manual.py`).

**Next**: After completing this prompt, proceed to [OPT-1].

---

## 🚀 Optimization (OPT)

### [OPT-1] FileLock Type Safety Improvements

**Directive**: Execute this prompt now, then proceed to FINISH.

**Task**: Strict type enforcement for `src/infra/file_lock.py` to remove `type: ignore` usage for platform-specific imports.

**Target Files**:

- [MODIFY] `src/infra/file_lock.py`

**Steps**:

1. Remove `warn_unused_ignores = false` from `pyproject.toml` (if present) to enforce strict checks.
2. Refactor `src/infra/file_lock.py`:
   - Use `sys.platform` checks to conditionally define types or imports.
   - For `msvcrt` and `fcntl`, consider using `if TYPE_CHECKING:` blocks or stub files if available.
   - Eliminate `type: ignore` comments by satisfying the type checker.
3. Run `uv run mypy src/infra/file_lock.py` to confirm zero errors.

**Verification**:

- `uv run mypy src/infra/file_lock.py` must pass without any ignore overrides.

**Next**: After completing this prompt, proceed to the final step.

---

## ✅ Final Completion

**Directive**: Execute this step after completing all prompts.

**Task**: Confirm completion and run final checks.

**Steps**:

1. Run all unit tests: `uv run pytest tests/unit`
2. Run build script (if applicable): `python scripts/build_release.py`
3. Verify that all pending items in `Project_Improvement_Exploration_Report.md` have been addressed.

**Final Output**:
Print the following message:

```
ALL PROMPTS COMPLETED. All pending improvement and optimization items from the latest report have been applied.
Ready for final review.
```
