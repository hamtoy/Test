# AI Agent Improvement Prompts

> **EXECUTION RULES:**
>
> 1. **No Talk:** Do not respond with text-only explanations.
> 2. **Action Only:** Always modify files using the provided tools.
> 3. **Sequential:** Execute all prompts strictly in order (PROMPT-001 → OPT-001).
> 4. **Verification:** You must verify every step with `uv run mypy` or `uv run pytest`.

---

## Execution Checklist

| # | Prompt ID | Title | Priority | Status |
|:---:|:---|:---|:---:|:---:|
| 1 | PROMPT-001 | Enhance Type Safety in QA Tools | P2 | ✅ Complete |
| 2 | OPT-1 | Enforce Strict Types in Utilities | OPT | ✅ Complete |

**Total: 2 prompts | Completed: 2 | Remaining: 0**

---

## 1. High Priority Improvements (P2)

### [PROMPT-001] Enhance Type Safety in QA Tools

**Directive:** Execute this prompt now, then proceed to [OPT-1].

**Task:**
Refactor `src/web/routers/qa_tools.py` and `src/qa/rag_system.py` to eliminate `type: ignore[arg-type]` usage by ensuring correct type compatibility between `QAKnowledgeGraph` and consumers.

**Target Files:**

- `src/web/routers/qa_tools.py`
- `src/qa/rag_system.py`

**Steps:**

1. **Analyze**: Check `src/web/routers/qa_tools.py` to see where `kg` is passed with `type: ignore`.
2. **Refactor Interface**: Update `CrossValidationSystem`, `GraphEnhancedRouter`, and `SmartAutocomplete` `__init__` methods to accept `QAKnowledgeGraph` (or a protocol) explicitly, instead of `Any` or mismatched types.
3. **Refactor Injection**: Ensure `src/qa/rag_system.py` defines `QAKnowledgeGraph` in a way that is compatible with these tools.
4. **Cleanup**: Remove the `type: ignore[arg-type]` comments.

**Implementation Constraint:**

- Do not use `Any` if possible. Use `from src.qa.rag_system import QAKnowledgeGraph`.

**Verification:**

- Run `uv run mypy src/web/routers/qa_tools.py` and ensure no errors.
- Run `uv run pytest tests/` to ensure no regression.

---

## 2. Code Optimization (OPT)

### [OPT-1] Enforce Strict Types in Utilities

**Directive:** Execute this prompt now, then proceed to Final Verification.

**Task:**
Refactor `src/validation/rule_parser.py` and `src/monitoring/metrics.py` to fix specific type errors (`no-any-return`, `no-redef`) and improve type strictness.

**Target Files:**

- `src/validation/rule_parser.py`
- `src/monitoring/metrics.py`

**Steps:**

1. **Analyze `rule_parser.py`**: Identify the `no-any-return` supression. The issue is likely that `_cache` is `dict[str, Any]` but methods return concrete types.
2. **Fix `rule_parser.py`**: Define a `TypedDict` or correct the type signatures to return explicit types (e.g. `dict[str, str]`) instead of opaque Any, removing the `type: ignore`.
3. **Analyze `metrics.py`**: Identify `no-redef`. This usually happens when conditional imports or branches define the same class name.
4. **Fix `metrics.py`**: Refactor using an `if TYPE_CHECKING:` block or unified class definition to satisfy mypy without `type: ignore`.

**Verification:**

- Run `uv run mypy src/validation/rule_parser.py src/monitoring/metrics.py` and ensure 0 errors.

---

## Final Verification & Completion

**Directive:** Run this step after completing all prompts.

**Task:**
Verify the integrity of the entire project after all changes.

**Steps:**

1. Run `uv run mypy .` to check project-wide type safety.
2. Run `uv run pytest tests/` to ensure no regressions.
3. If all checks pass, output the final completion message.

**Completion Message:**
"ALL PROMPTS COMPLETED. All pending improvement and optimization items from the latest report have been applied."
