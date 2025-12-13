# v3.0 Shim Removal - Comprehensive Guide

## Issue Summary

This document provides a comprehensive 5-step checklist for removing all 24 backward-compatibility shim files in preparation for v3.0 release. The shim files were introduced in v2.0 to provide a gradual migration path from the flat module structure to the new package-based architecture.

### Background

In v2.0, we introduced a modular package structure while maintaining backward compatibility through shim files. These shim files:
- Re-export functionality from the new package locations
- Emit deprecation warnings when used
- Will be **completely removed** in v3.0

### Shim Files to Remove (24 total)

| Priority | File | New Location |
|----------|------|--------------|
| **P0** | `config.py` | `config/settings.py` |
| **P0** | `exceptions.py` | `config/exceptions.py` |
| **P0** | `models.py` | `core/models.py` |
| **P0** | `qa_rag_system.py` | `qa/rag_system.py` |
| **P1** | `constants.py` | `config/constants.py` |
| **P1** | `utils.py` | `infra/utils.py` |
| **P1** | `logging_setup.py` | `infra/logging.py` |
| **P1** | `neo4j_utils.py` | `infra/neo4j.py` |
| **P2** | `adaptive_difficulty.py` | `features/difficulty.py` |
| **P2** | `advanced_context_augmentation.py` | `processing/context_augmentation.py` |
| **P2** | `cache_analytics.py` | `caching/analytics.py` |
| **P2** | `caching_layer.py` | `caching/layer.py` |
| **P2** | `data_loader.py` | `processing/loader.py` |
| **P2** | `dynamic_template_generator.py` | `processing/template_generator.py` |
| **P2** | `graph_enhanced_router.py` | `routing/graph_router.py` |
| **P2** | `graph_schema_builder.py` | `graph/schema_builder.py` |
| **P2** | `integrated_qa_pipeline.py` | `qa/pipeline.py` |
| **P2** | `lats_searcher.py` | `features/lats.py` |
| **P2** | `list_models.py` | `llm/list_models.py` |
| **P2** | `memory_augmented_qa.py` | `qa/memory_augmented.py` |
| **P2** | `multi_agent_qa_system.py` | `qa/multi_agent.py` |
| **P2** | `multimodal_understanding.py` | `features/multimodal.py` |
| **P2** | `qa_generator.py` | `qa/generator.py` |
| **P2** | `qa_system_factory.py` | `qa/factory.py` |
| **P2** | `real_time_constraint_enforcer.py` | `infra/constraints.py` |
| **P2** | `self_correcting_chain.py` | `features/self_correcting.py` |
| **P2** | `worker.py` | `infra/worker.py` |

---

## 5-Step Shim Removal Checklist

### Step 1: Audit Current Usage 📊

Before removing shims, identify all deprecated import usages in your codebase.

**Run the verification script:**

```bash
python scripts/validation/verify_v3_readiness.py
```

**Example Output:**

```text
🔍 v3.0 Readiness Verification
============================================================

📋 Deprecated Import (5):
  ❌ examples/basic_usage.py:3
      Deprecated import detected. Use: from src.core.models import
  ❌ tests/integration/test_pipeline.py:7
      Deprecated import detected. Use: from src.infra.utils import
  ❌ scripts/run_pipeline.py:2
      Deprecated import detected. Use: from src.config.constants import

📋 Shim File (24):
  ⚠️  src/utils.py
      Shim file exists (should be removed in v3.0 or later)
  ⚠️  src/models.py
      Shim file exists (should be removed in v3.0 or later)
  ...

============================================================
📊 Summary:
  Errors:   5
  Warnings: 24
  Info:     2

❌ v3.0 readiness check FAILED
```

**Alternative: Use strict mode in CI:**

```yaml
# .github/workflows/ci.yml
env:
  DEPRECATION_LEVEL: strict
```

This will cause any deprecated import to raise an `ImportError` immediately.

---

### Step 2: Migrate All Imports 🔄

Update all deprecated imports to use the new package paths.

**Option A: Automatic migration (recommended)**

```bash
# Preview changes (dry run)
python scripts/migrate_imports.py --check --show-diff

# Apply changes
python scripts/migrate_imports.py --fix
```

**Example diff output:**

```diff
--- a/examples/basic_usage.py
+++ b/examples/basic_usage.py
@@ -1,5 +1,5 @@
-from src.models import WorkflowResult, EvaluationResultSchema
-from src.utils import clean_markdown_code_block
+from src.core.models import WorkflowResult, EvaluationResultSchema
+from src.infra.utils import clean_markdown_code_block
```

**Option B: Manual migration**

Use the import mapping table above to manually update imports:

```python
# ❌ Before (deprecated)
from src.constants import ERROR_MESSAGES, LOG_MESSAGES
from src.exceptions import BudgetExceededError, ValidationFailedError
from src.models import WorkflowResult, EvaluationResultSchema
from src.utils import clean_markdown_code_block, safe_json_parse
from src.logging_setup import setup_logging, log_metrics
from src.neo4j_utils import SafeDriver, create_sync_driver
from src.qa_rag_system import QAKnowledgeGraph
from src.data_loader import load_input_data, validate_candidates

# ✅ After (new paths)
from src.config.constants import ERROR_MESSAGES, LOG_MESSAGES
from src.config.exceptions import BudgetExceededError, ValidationFailedError
from src.core.models import WorkflowResult, EvaluationResultSchema
from src.infra.utils import clean_markdown_code_block, safe_json_parse
from src.infra.logging import setup_logging, log_metrics
from src.infra.neo4j import SafeDriver, create_sync_driver
from src.qa.rag_system import QAKnowledgeGraph
from src.processing.loader import load_input_data, validate_candidates
```

---

### Step 3: Verify Migration ✅

After migrating imports, verify that no deprecated imports remain.

**Run verification again:**

```bash
python scripts/validation/verify_v3_readiness.py
```

**Expected successful output:**

```text
🔍 v3.0 Readiness Verification
============================================================

📋 Shim File (24):
  ⚠️  src/utils.py
      Shim file exists (should be removed in v3.0 or later)
  ...

============================================================
📊 Summary:
  Errors:   0
  Warnings: 24
  Info:     0

✅ v3.0 readiness check PASSED
   (with 24 warning(s) to address)
```

**Run tests to confirm functionality:**

```bash
# Run full test suite
pytest tests/ -v

# Run with strict deprecation checking
DEPRECATION_LEVEL=strict pytest tests/ -v
```

**If tests fail with `ImportError`:**

```text
ImportError: Cannot import from deprecated path 'src.models' 
(DEPRECATION_LEVEL=strict). Use 'src.core.models' instead.
```

This indicates that migration is incomplete. Fix the remaining imports and re-run.

---

### Step 4: Remove Shim Files 🗑️

Once all imports are migrated and tests pass, remove the shim files.

**Option A: Staged removal by priority**

Remove shims in phases based on usage priority:

```bash
# Preview P0 (high usage) files to remove
python scripts/migration/remove_shims_v3.py --priority P0 --dry-run

# Remove P0 files with backup
python scripts/migration/remove_shims_v3.py --priority P0 --execute

# Preview P1 (mid usage) files
python scripts/migration/remove_shims_v3.py --priority P1 --dry-run

# Remove P1 files
python scripts/migration/remove_shims_v3.py --priority P1 --execute

# Finally, remove P2 (low usage) files
python scripts/migration/remove_shims_v3.py --priority P2 --execute
```

**Option B: Remove all at once**

```bash
# Preview all shim files to be removed
python scripts/migration/remove_shims_v3.py --dry-run

# Remove all shim files (creates backup first)
python scripts/migration/remove_shims_v3.py --execute
```

**Example output:**

```text
======================================================================
v3.0 Shim File Removal
======================================================================

Files to process: 24
✅ Backed up: config.py
✅ Backed up: exceptions.py
✅ Backed up: models.py
...

📦 Backup location: backup_v3_20250115_143022

✅ Deleted: config.py
✅ Deleted: exceptions.py
✅ Deleted: models.py
...

✅ Updated .gitignore with backup folder pattern

======================================================================
EXECUTION SUMMARY
Deleted 24 shim file(s)
======================================================================

🎉 v3.0 shim removal complete!
To rollback, copy files from the backup directory:
  cp backup_v3_*/* src/
```

---

### Step 5: Final Validation & Release 🚀

Perform final validation before releasing v3.0.

**Run full test suite:**

```bash
pytest tests/ -v --tb=short
```

**Verify import structure:**

```python
# test_v3_imports.py - Add to tests/
"""Verify v3.0 import structure works correctly."""

def test_new_import_paths():
    """Test that new import paths work correctly."""
    # Core imports
    from src.core.models import WorkflowResult, EvaluationResultSchema
    
    # Config imports
    from src.config.constants import ERROR_MESSAGES
    from src.config.exceptions import BudgetExceededError
    
    # Infrastructure imports
    from src.infra.utils import clean_markdown_code_block
    from src.infra.logging import setup_logging
    from src.infra.neo4j import SafeDriver
    
    # Q&A imports
    from src.qa.rag_system import QAKnowledgeGraph
    
    # Processing imports
    from src.processing.loader import load_input_data
    
    assert WorkflowResult is not None
    assert EvaluationResultSchema is not None


def test_old_import_paths_fail():
    """Test that old import paths no longer work."""
    import pytest
    
    with pytest.raises(ModuleNotFoundError):
        from src.models import WorkflowResult  # noqa: F401
    
    with pytest.raises(ModuleNotFoundError):
        from src.utils import clean_markdown_code_block  # noqa: F401
    
    with pytest.raises(ModuleNotFoundError):
        from src.constants import ERROR_MESSAGES  # noqa: F401
```

**Update version in `src/__init__.py`:**

```python
# src/__init__.py
__version__ = "3.0.0"
```

**Update documentation:**

- [ ] Update README.md with v3.0 import examples
- [ ] Verify MIGRATION.md is current
- [ ] Add v3.0 release notes to CHANGELOG.md

**Create release:**

```bash
git tag -a v3.0.0 -m "v3.0.0 - Pure package architecture"
git push origin v3.0.0
```

---

## Rollback Procedure

If issues are discovered after shim removal:

**Option 1: Restore from backup**

```bash
# Restore all shim files from backup
cp backup_v3_*/* src/
```

**Option 2: Pin to last v2.x release**

```bash
pip install shining-quasar==2.5.9
```

**Option 3: Revert git commits**

```bash
git revert HEAD~1  # Revert the shim removal commit
```

---

## Code Examples

### Example 1: Migrating a simple script

**Before (v2.x compatible):**

```python
#!/usr/bin/env python3
"""Example script using deprecated imports."""
from src.models import WorkflowResult
from src.utils import clean_markdown_code_block
from src.logging_setup import setup_logging

setup_logging()

result = WorkflowResult(
    success=True,
    output=clean_markdown_code_block("```python\nprint('hello')\n```")
)
print(result)
```

**After (v3.0 compatible):**

```python
#!/usr/bin/env python3
"""Example script using new import paths."""
from src.core.models import WorkflowResult
from src.infra.utils import clean_markdown_code_block
from src.infra.logging import setup_logging

setup_logging()

result = WorkflowResult(
    success=True,
    output=clean_markdown_code_block("```python\nprint('hello')\n```")
)
print(result)
```

### Example 2: Migrating a test file

**Before:**

```python
import pytest
from src.exceptions import BudgetExceededError, ValidationFailedError
from src.constants import ERROR_MESSAGES

def test_budget_exceeded():
    with pytest.raises(BudgetExceededError) as exc_info:
        raise BudgetExceededError(ERROR_MESSAGES["budget_exceeded"])
    assert "budget" in str(exc_info.value).lower()
```

**After:**

```python
import pytest
from src.config.exceptions import BudgetExceededError, ValidationFailedError
from src.config.constants import ERROR_MESSAGES

def test_budget_exceeded():
    with pytest.raises(BudgetExceededError) as exc_info:
        raise BudgetExceededError(ERROR_MESSAGES["budget_exceeded"])
    assert "budget" in str(exc_info.value).lower()
```

### Example 3: Migrating a module with multiple imports

**Before:**

```python
"""QA Pipeline module using deprecated imports."""
from src.qa_rag_system import QAKnowledgeGraph
from src.data_loader import load_input_data, validate_candidates
from src.caching_layer import CacheManager
from src.graph_enhanced_router import GraphRouter
from src.neo4j_utils import SafeDriver, create_sync_driver

class QAPipeline:
    def __init__(self, config):
        self.driver = create_sync_driver(config.neo4j_uri)
        self.cache = CacheManager()
        self.router = GraphRouter()
        self.qa_graph = QAKnowledgeGraph(self.driver)
    
    def run(self, input_path):
        data = load_input_data(input_path)
        candidates = validate_candidates(data)
        return self.qa_graph.query(candidates)
```

**After:**

```python
"""QA Pipeline module using new import paths."""
from src.qa.rag_system import QAKnowledgeGraph
from src.processing.loader import load_input_data, validate_candidates
from src.caching.layer import CacheManager
from src.routing.graph_router import GraphRouter
from src.infra.neo4j import SafeDriver, create_sync_driver

class QAPipeline:
    def __init__(self, config):
        self.driver = create_sync_driver(config.neo4j_uri)
        self.cache = CacheManager()
        self.router = GraphRouter()
        self.qa_graph = QAKnowledgeGraph(self.driver)
    
    def run(self, input_path):
        data = load_input_data(input_path)
        candidates = validate_candidates(data)
        return self.qa_graph.query(candidates)
```

---

## FAQ

### Q: What happens if I don't migrate before v3.0?

A: Your code will fail with `ModuleNotFoundError` when trying to import from removed shim paths:

```python
>>> from src.models import WorkflowResult
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
ModuleNotFoundError: No module named 'src.models'
```

### Q: Can I use both old and new paths during migration?

A: Yes, during v2.x, both paths work (old paths emit deprecation warnings). This allows gradual migration.

### Q: How do I silence deprecation warnings temporarily?

A: Not recommended, but if needed:

```python
import warnings
from src._deprecation import EnhancedDeprecationWarning
warnings.filterwarnings("ignore", category=EnhancedDeprecationWarning)
```

### Q: How do I know which files to prioritize?

A: Use the priority classifications:
- **P0 (High)**: Core files used by most of the codebase
- **P1 (Mid)**: Common utilities and infrastructure
- **P2 (Low)**: Specialized modules with limited usage

### Q: Can I automate this in CI/CD?

A: Yes! Add to your CI pipeline:

```yaml
# .github/workflows/migration-check.yml
name: Migration Check

on: [push, pull_request]

jobs:
  check-deprecated:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      
      - name: Check for deprecated imports
        run: python scripts/validation/verify_v3_readiness.py --strict
```

---

## Timeline

| Milestone | Date | Status |
|-----------|------|--------|
| v2.0 - Deprecation warnings introduced | Completed | ✅ |
| v2.5 - Enhanced deprecation warnings | Completed | ✅ |
| v3.0 - Shim files removed | Upcoming | ⏳ |

---

## Related Documentation

- [MIGRATION.md](../MIGRATION.md) - Detailed migration guide
- [DEPRECATION.md](../DEPRECATION.md) - Deprecation policy and environment variables
- [BREAKING_CHANGES_v3.md](BREAKING_CHANGES_v3.md) - Full list of breaking changes
- [CHANGELOG.md](../CHANGELOG.md) - Version history

---

## Support

If you encounter issues during migration:

1. Check existing [Issues](https://github.com/hamtoy/Test/issues) for similar problems
2. Run `python scripts/validation/verify_v3_readiness.py --json` for detailed diagnostics
3. Open a new issue with the verification output

---

*Last updated: 2025-11-27*
