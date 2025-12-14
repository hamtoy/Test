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
| 1 | PROMPT-001 | LLM Rate Limit Fallback Strategy | P2 | ✅ Complete |
| 2 | OPT-1 | Optimize Config Loading (LRU Cache) | OPT | ✅ Complete |

**Total: 2 prompts | Completed: 2 | Skipped: 0**

---

## 🟡 Priority 2 (High)

### [PROMPT-001] LLM Rate Limit Fallback Strategy

**Directive**: Execute this prompt now, then proceed to OPT-1.

**Task**: Implement a model fallback mechanism in `GeminiModelClient` to automatically switch to a secondary model (e.g., `gemini-1.5-flash`) when the primary model hits a rate limit (HTTP 429).

**Target Files**:

- [MODIFY] `src/llm/gemini.py`
- [NEW] `tests/unit/llm/test_gemini_fallback.py`

**Steps**:

1. Modify `GeminiModelClient.__init__` in `src/llm/gemini.py`:
   - Accept a new optional argument `fallback_models: list[str] | None`.
   - Store it as an instance variable.
2. Refactor `GeminiModelClient.generate` and `generate_content_async`:
   - Wrap the API call in a loop that iterates through `[self.model_name] + (self.fallback_models or [])`.
   - Catch `google.api_core.exceptions.ResourceExhausted` (429).
   - If caught, log a warning with `logger.warning(f"Rate limit hit for {model}, switching to fallback...")` and continue to the next model.
   - If all models fail, re-raise the last exception.
3. Create a unit test `tests/unit/llm/test_gemini_fallback.py`:
   - Mock `genai.GenerativeModel.generate_content`.
   - Simulate a scenario where the first call raises `ResourceExhausted` and the second call succeeds.
   - Verify that the fallback mechanism worked as expected.

**Verification**:

- Run the new test: `uv run pytest tests/unit/llm/test_gemini_fallback.py`
- Ensure the test passes and covers the fallback scenario.

**Next**: After completing this prompt, proceed to [OPT-1].

---

## 🚀 Optimization (OPT)

### [OPT-1] Optimize Config Loading (LRU Cache)

**Directive**: Execute this prompt now, then proceed to FINISH.

**Task**: Apply `functools.lru_cache` to the configuration loading logic to prevent redundant environment variable parsing and file I/O during runtime.

**Target Files**:

- [MODIFY] `src/config/app_config.py` (or the file containing `load_config` or equivalent)

**Steps**:

1. Identify the configuration loading function (e.g., `load_config`, `get_settings`, or `AppConfig` instantiation).
2. Decorate the function with `@functools.lru_cache(maxsize=1)`.
   - Ensure that the function signature allows caching (i.e., arguments are hashable, or use no arguments if possible).
3. If the function takes mutable arguments or non-hashable types, refactor it to use hashable configuration identifiers or remove arguments if they are not needed for the singleton behavior.
4. Verify that `os.getenv` or `.env` file reading happens only once even when the function is called multiple times.

**Verification**:

- Create a temporary test script `scripts/verify_config_cache.py`:
  - Call `load_config()` twice.
  - Assert that the returned objects are identical (`is` operator).
  - Print "Config caching works!" if successful.
- Run the script: `python scripts/verify_config_cache.py`

**Next**: After completing this prompt, proceed to the final step.

---

## ✅ Final Completion

**Directive**: Execute this step after completing all prompts.

**Task**: Confirm completion and run final checks.

**Steps**:

1. Run all unit tests: `uv run pytest tests/unit`
2. Run build script (if applicable): `python scripts/build_release.py` or `uv run build`
3. Verify that all pending items in `Project_Improvement_Exploration_Report.md` have been addressed.

**Final Output**:
Print the following message:

```
ALL PROMPTS COMPLETED. All pending improvement and optimization items from the latest report have been applied.
Ready for final review.
```
