# 🤖 AI Agent Improvement Prompts

> ## 🚨 MANDATORY: FILE MODIFICATION REQUIRED
>
> **⛔ DO NOT just respond with text or code blocks.**
> **⛔ DO NOT say "you can modify like this" without actually modifying.**
> **⛔ DO NOT explain what needs to be done without doing it.**
>
> **✅ YOU MUST use file editing tools (`replace_string_in_file`, `create_file`, `multi_replace_string_in_file`) to directly modify files.**
> **✅ After each prompt, confirm "I have modified the file(s)" with the actual changes made.**
>
> ---
>
> **Process ALL prompts below SEQUENTIALLY. Do NOT stop after completing one prompt.**

---

## 📋 Execution Checklist

| # | Prompt ID | Title | Priority | Status |
|:---:|:---|:---|:---:|:---:|
| 1 | PROMPT-001 | Complete Docstring Standardization | P3 | ✅ Completed |

**Total: 1 prompt** | **Completed: 1** | **Remaining: 0**

---

## 🟢 Priority 3 (Medium) - Execute Now

### [PROMPT-001] Complete Docstring Standardization

> **🚨 REQUIRED: Use `replace_string_in_file` or `create_file` to make changes. Do NOT just show code.**

**⏱️ Execute this prompt now. This is the ONLY remaining improvement.**

**Task**: Run the docstring checker and fix identified style inconsistencies across the codebase to ensure all docstrings follow Google style conventions.

**Files to Modify**: Various files in `src/` based on `scripts/check_docstrings.py` output

#### Instructions:

1. Run `python scripts/check_docstrings.py src/` to identify style inconsistencies
2. Fix any NumPy or Sphinx style docstrings to Google style
3. Focus on high-priority modules: `src/agent/`, `src/core/`, `src/qa/`, `src/workflow/`
4. Verify ruff D rules are properly configured in pyproject.toml (already done)
5. Ensure all public functions, classes, and methods have proper docstrings

#### Implementation Code:

**Step 1: Verify pyproject.toml configuration (already correct, no changes needed)**

The `[tool.ruff.lint]` section already has docstring linting enabled:

```toml
[tool.ruff.lint]
extend-select = ["PERF", "FURB", "SIM", "D"]
ignore = [
    "D100",   # Missing docstring in public module
    "D101",   # Missing docstring in public class
    "D102",   # Missing docstring in public method
    "D103",   # Missing docstring in public function
    "D104",   # Missing docstring in public package
    "D105",   # Missing docstring in magic method
    "D107",   # Missing docstring in __init__
    "D200",   # One-line docstring should fit on one line
    "D205",   # 1 blank line required between summary line and description
    "D415",   # First line should end with a period, question mark, or exclamation point
]

[tool.ruff.lint.pydocstyle]
convention = "google"
```

**Step 2: Example docstring conversions**

1. **NumPy style to Google style:**

    Before (NumPy):
    ```python
    def example_function(param1, param2):
        """Short description.
        
        Parameters
        ----------
        param1 : str
            Description of param1.
        param2 : int
            Description of param2.
            
        Returns
        -------
        bool
            Description of return value.
        """
    ```

    After (Google):
    ```python
    def example_function(param1: str, param2: int) -> bool:
        """Short description.
        
        Args:
            param1: Description of param1.
            param2: Description of param2.
            
        Returns:
            Description of return value.
        """
    ```

2. **Sphinx style to Google style:**

    Before (Sphinx):
    ```python
    def another_function(name):
        """Short description.
        
        :param name: The name parameter
        :type name: str
        :returns: The result
        :rtype: str
        """
    ```

    After (Google):
    ```python
    def another_function(name: str) -> str:
        """Short description.
        
        Args:
            name: The name parameter
            
        Returns:
            The result
        """
    ```

**Step 3: Priority files to check and fix**

Run the following command to identify files with docstring issues:

```bash
python scripts/check_docstrings.py src/ --missing-only
```

Then focus on these high-priority modules:

1. `src/agent/core.py` - Main agent class docstrings
2. `src/agent/cost_tracker.py` - Cost tracking docstrings
3. `src/core/models.py` - Pydantic model docstrings
4. `src/qa/rag_system.py` - RAG system docstrings
5. `src/qa/graph/rule_upsert.py` - RuleUpsertManager docstrings
6. `src/workflow/executor.py` - Workflow execution docstrings
7. `src/web/api.py` - API route docstrings

**Step 4: Automated check integration**

After manual fixes, verify with:

```bash
# Check docstring style issues
ruff check src/ --select D --statistics

# Run full linting
ruff check src/ --fix

# Verify no style violations remain
python scripts/check_docstrings.py src/ --missing-only | wc -l
```

#### Verification:
- Run: `python scripts/check_docstrings.py src/ --missing-only | head -20`
- Run: `ruff check src/ --select D --statistics`
- Expected: Minimal or zero style issues, all critical modules using Google style consistently

**🎉 ALL PROMPTS COMPLETED! Run final verification:**

```bash
# Verify docstring consistency
python scripts/check_docstrings.py src/ --missing-only

# Check for any remaining ruff D violations
ruff check src/ --select D --statistics | head -10

# Verify all tests still pass
pytest tests/ -v --tb=short

echo '✅ Docstring standardization completed!'
echo '✅ All improvement prompts executed successfully!'
```

---

## 🎊 Completion Summary

**Total Prompts**: 1  
**Priority Breakdown**: P1: 0, P2: 0, P3: 1  

### Recently Completed Improvements

The following major improvements were completed in recent sessions:

1. **RAG System Module Separation** ✅ (2025-12-01)
   - Extracted RuleUpsertManager to `src/qa/graph/rule_upsert.py`
   - Reduced rag_system.py from 1005 lines to 504 lines
   - Added Cypher injection prevention
   - Created comprehensive test suite for graph modules

2. **Test Coverage Enhancement** ✅ (2025-12-01)
   - Added 6 new test files for graph and web modules
   - Improved overall test coverage to 94%

3. **Web Dependency Injection** ✅ (2025-11-30)
   - Implemented FastAPI DI pattern in `src/web/dependencies.py`
   - Enhanced testability and modularity

4. **Sphinx CI Integration** ✅ (2025-11-30)
   - GitHub Actions workflow for automatic documentation builds

**Current Status**: Only P3 docstring standardization remains, which is a low-priority cleanup task focused on consistency rather than functionality.