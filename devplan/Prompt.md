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
| 1 | PROMPT-001 | RAG System Additional Module Split | P2 | ✅ Done |
| 2 | PROMPT-002 | Sphinx Documentation CI Integration | P3 | ✅ Done |
| 3 | PROMPT-003 | Complete Docstring Standardization | P3 | ✅ Done |

**Total: 3 prompts** | **Completed: 3** | **Remaining: 0**

---

## 🟡 Priority 2 (High) - Execute First

### [PROMPT-001] RAG System Additional Module Split

> **🚨 REQUIRED: Use `replace_string_in_file` or `create_file` to make changes. Do NOT just show code.**

**⏱️ Execute this prompt now, then proceed to PROMPT-002**

**Task**: Further reduce `src/qa/rag_system.py` from 1022 lines to under 500 lines by extracting more functionality to the existing `src/qa/graph/` modules.

**Files to Modify**: 
- Update `src/qa/graph/connection.py` - Add more connection methods from rag_system.py
- Update `src/qa/graph/rule_extractor.py` - Add upsert and validation methods
- Create `src/qa/graph/query_executor.py` - Extract query execution logic
- Update `src/qa/rag_system.py` - Import from new modules and reduce code

#### Instructions:

1. Analyze `src/qa/rag_system.py` to identify extractable methods
2. Extract `upsert_auto_generated_rules` method to `rule_extractor.py`
3. Extract query execution helper methods to new `query_executor.py`
4. Update imports in `rag_system.py` to use the new modules
5. Ensure all existing tests still pass

#### Implementation Code:

**File: src/qa/graph/query_executor.py**
```python
"""Query execution utilities for Neo4j graph operations.

Provides helper functions for executing Cypher queries with proper
async/sync handling and error management.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from typing import Any, Coroutine, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def run_async_safely(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine from sync context safely.
    
    Handles the case where an event loop is already running by
    executing the coroutine in a separate thread.
    
    Args:
        coro: The coroutine to execute
        
    Returns:
        The result of the coroutine execution
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, create one and run
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    # Loop is already running - run in a separate thread
    def run_in_thread() -> T:
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()
            asyncio.set_event_loop(None)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_in_thread)
        return future.result()


class QueryExecutor:
    """Executes Cypher queries against Neo4j with async support.
    
    Provides a unified interface for executing queries regardless of
    whether a sync driver or async graph provider is being used.
    
    Args:
        graph_driver: Sync Neo4j driver instance
        graph_provider: Async graph provider instance (optional)
    """
    
    def __init__(
        self,
        graph_driver: Optional[Any] = None,
        graph_provider: Optional[Any] = None,
    ) -> None:
        """Initialize the query executor."""
        self._graph = graph_driver
        self._graph_provider = graph_provider
        
    def execute(
        self,
        cypher: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results.
        
        Args:
            cypher: The Cypher query string
            params: Query parameters
            
        Returns:
            List of result records as dictionaries
        """
        params = params or {}
        
        if self._graph_provider is None:
            if self._graph is None:
                raise RuntimeError("No graph driver or provider available")
            with self._graph.session() as session:
                records = session.run(cypher, **params)
                return [dict(r) for r in records]
        
        prov = self._graph_provider
        
        async def _run() -> List[Dict[str, Any]]:
            async with prov.session() as session:
                records = await session.run(cypher, **params)
                return [dict(r) for r in records]
        
        return run_async_safely(_run())
        
    def execute_write(
        self,
        cypher: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a write query and return summary.
        
        Args:
            cypher: The Cypher write query
            params: Query parameters
            
        Returns:
            Summary of the write operation
        """
        params = params or {}
        
        if self._graph_provider is None:
            if self._graph is None:
                raise RuntimeError("No graph driver or provider available")
            with self._graph.session() as session:
                result = session.run(cypher, **params)
                summary = result.consume()
                return {
                    "nodes_created": summary.counters.nodes_created,
                    "nodes_deleted": summary.counters.nodes_deleted,
                    "relationships_created": summary.counters.relationships_created,
                    "properties_set": summary.counters.properties_set,
                }
        
        prov = self._graph_provider
        
        async def _run() -> Dict[str, Any]:
            async with prov.session() as session:
                result = await session.run(cypher, **params)
                # Async providers may have different summary handling
                return {"executed": True}
        
        return run_async_safely(_run())
```

**Update src/qa/graph/__init__.py to export new class:**
```python
"""Graph-based QA components for RAG system.

This package provides modular components for Neo4j-based knowledge graph operations:
- connection: Neo4j connection management
- vector_search: Vector similarity search
- rule_extractor: Rule extraction and QA generation
- query_executor: Query execution utilities
"""

from src.qa.graph.connection import Neo4jConnectionManager
from src.qa.graph.query_executor import QueryExecutor, run_async_safely
from src.qa.graph.rule_extractor import RuleExtractor
from src.qa.graph.vector_search import VectorSearchEngine

__all__ = [
    "Neo4jConnectionManager",
    "QueryExecutor",
    "RuleExtractor",
    "VectorSearchEngine",
    "run_async_safely",
]
```

#### Verification:
- Run: `python -c "from src.qa.graph import QueryExecutor, run_async_safely; print('Import successful')"`
- Run: `wc -l src/qa/rag_system.py` (should be reduced)
- Expected: No import errors, line count reduced

**✅ After completing this prompt, proceed to [PROMPT-002]**

---

## 🟢 Priority 3 (Medium) - Execute Last

### [PROMPT-002] Sphinx Documentation CI Integration

> **🚨 REQUIRED: Use `replace_string_in_file` or `create_file` to make changes. Do NOT just show code.**

**⏱️ Execute this prompt now, then proceed to PROMPT-003**

**Task**: Create GitHub Actions workflow for automatic documentation build and deployment.

**Files to Create**: `.github/workflows/docs.yml`

#### Instructions:

1. Create a GitHub Actions workflow file
2. Configure Sphinx build on push to main
3. Deploy to GitHub Pages
4. Add PR preview comments (optional)

#### Implementation Code:

**File: .github/workflows/docs.yml**
```yaml
name: Documentation

on:
  push:
    branches: [main]
    paths:
      - 'docs/**'
      - 'src/**/*.py'
      - '.github/workflows/docs.yml'
  pull_request:
    branches: [main]
    paths:
      - 'docs/**'
      - 'src/**/*.py'
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install sphinx sphinx-rtd-theme sphinx-autodoc-typehints
          pip install -e .

      - name: Generate API documentation
        run: |
          sphinx-apidoc -f -o docs/api src/ \
            --separate \
            --module-first \
            -H "API Reference" \
            -A "shining-quasar Team"

      - name: Build documentation
        run: |
          cd docs
          make html

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: docs/_build/html

  deploy:
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    needs: build
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

#### Verification:
- Run: `cat .github/workflows/docs.yml`
- Expected: Valid YAML workflow file exists

**✅ After completing this prompt, proceed to [PROMPT-003]**

---

### [PROMPT-003] Complete Docstring Standardization

> **🚨 REQUIRED: Use `replace_string_in_file` or `create_file` to make changes. Do NOT just show code.**

**⏱️ Execute this prompt now, then ALL PROMPTS ARE COMPLETED.**

**Task**: Run the docstring checker and fix identified style inconsistencies.

**Files to Modify**: Various files in `src/` based on check_docstrings.py output

#### Instructions:

1. Run `python scripts/check_docstrings.py src/` to identify issues
2. Fix any NumPy or Sphinx style docstrings to Google style
3. Add missing docstrings to public functions/classes
4. Enable ruff D rules in pyproject.toml

#### Implementation Code:

**Update pyproject.toml to enable docstring linting:**

Find the `[tool.ruff.lint]` section and add "D" to the select list:

```toml
[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
    "D",      # pydocstyle (docstring checks)
]
ignore = [
    "D100",   # Missing docstring in public module
    "D104",   # Missing docstring in public package
    "D105",   # Missing docstring in magic method
    "D107",   # Missing docstring in __init__
]

[tool.ruff.lint.pydocstyle]
convention = "google"
```

**Example docstring fix (NumPy to Google):**

Before (NumPy style):
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

After (Google style):
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

#### Verification:
- Run: `python scripts/check_docstrings.py src/ --missing-only`
- Run: `ruff check src/ --select D --statistics` (after enabling D rules)
- Expected: Minimal or no style issues reported

**🎉 ALL PROMPTS COMPLETED! Run final verification:**

```bash
# Verify all changes
python -c "
from src.qa.graph import QueryExecutor, run_async_safely
print('QueryExecutor import: OK')
"

# Check documentation workflow
cat .github/workflows/docs.yml | head -5

# Run docstring check
python scripts/check_docstrings.py src/config --missing-only

echo 'All prompts completed successfully!'
```
