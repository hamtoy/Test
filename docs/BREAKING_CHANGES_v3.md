# Breaking Changes in v3.0

## Overview

Version 3.0 represents a major architectural upgrade that completes the migration to a pure package-based structure. **All backward-compatibility shim files have been removed.**

## ⚠️ Removed Shim Files (24)

The following deprecated import paths **no longer work** in v3.0:

| Removed Path | New Path (Required) |
|--------------|---------------------|
| `from src.adaptive_difficulty import ...` | `from src.features.difficulty import ...` |
| `from src.advanced_context_augmentation import ...` | `from src.processing.context_augmentation import ...` |
| `from src.cache_analytics import ...` | `from src.caching.analytics import ...` |
| `from src.caching_layer import ...` | `from src.caching.layer import ...` |
| `from src.config import AppConfig` | `from src.config.settings import AppConfig` |
| `from src.constants import ...` | `from src.config.constants import ...` |
| `from src.data_loader import ...` | `from src.processing.loader import ...` |
| `from src.dynamic_template_generator import ...` | `from src.processing.template_generator import ...` |
| `from src.exceptions import ...` | `from src.config.exceptions import ...` |
| `from src.graph_enhanced_router import ...` | `from src.routing.graph_router import ...` |
| `from src.graph_schema_builder import ...` | `from src.graph import ...` |
| `from src.integrated_qa_pipeline import ...` | `from src.qa.pipeline import ...` |
| `from src.lats_searcher import ...` | `from src.features.lats import ...` |
| `from src.list_models import ...` | `from src.llm.list_models import ...` |
| `from src.logging_setup import ...` | `from src.infra.logging import ...` |
| `from src.memory_augmented_qa import ...` | `from src.qa.memory_augmented import ...` |
| `from src.models import ...` | `from src.core.models import ...` |
| `from src.multi_agent_qa_system import ...` | `from src.qa.multi_agent import ...` |
| `from src.multimodal_understanding import ...` | `from src.features.multimodal import ...` |
| `from src.neo4j_utils import ...` | `from src.infra.neo4j import ...` |
| `from src.qa_generator import ...` | `from src.qa.generator import ...` |
| `from src.qa_rag_system import ...` | `from src.qa.rag_system import ...` |
| `from src.qa_system_factory import ...` | `from src.qa.factory import ...` |
| `from src.real_time_constraint_enforcer import ...` | `from src.infra.constraints import ...` |
| `from src.self_correcting_chain import ...` | `from src.features.self_correcting import ...` |
| `from src.utils import ...` | `from src.infra.utils import ...` |
| `from src.worker import ...` | `from src.infra.worker import ...` |

## Migration Checklist

Before upgrading to v3.0, follow these steps:

### 1. Check Readiness

Run the readiness verification script:

```bash
python scripts/validation/verify_v3_readiness.py
```

If any deprecated imports are found, you'll see a detailed report.

### 2. Fix Deprecated Imports

Use the migration tool to automatically fix imports:

```bash
python scripts/migrate_imports.py --fix
```

Or manually update imports following the table above.

### 3. Test Your Code

```bash
pytest tests/ -v
```

### 4. Update Dependencies

Update your project dependencies to require v3.0+:

```toml
[project]
dependencies = [
    "shining-quasar>=3.0.0",
]
```

## Rollback to v2.5

If you encounter issues after upgrading to v3.0 and cannot immediately update your imports:

### Option 1: Pin to Last v2.x Release

```bash
pip install shining-quasar==2.5.9
```

### Option 2: Restore Shim Files from Backup

If you used the removal script with backups:

```bash
cp backup_v3_*/* src/
```

## Python Version Requirements

- **v3.0+**: Requires Python 3.10 or later
- **v2.x**: Supports Python 3.9+

## Package Structure

v3.0 uses a clean package-based structure:

```
src/
├── __init__.py           # Public API exports
├── main.py               # Entry point
├── cli.py                # CLI interface
│
├── agent/                # Agent components
├── analysis/             # Analysis tools
├── caching/              # Caching infrastructure
├── config/               # Configuration (settings, constants, exceptions)
├── core/                 # Core models and interfaces
├── features/             # Feature modules
├── graph/                # Graph operations
├── infra/                # Infrastructure utilities
├── llm/                  # LLM integrations
├── processing/           # Data processing
├── qa/                   # Q&A system components
├── routing/              # Routing logic
├── ui/                   # User interface
└── workflow/             # Workflow orchestration
```

## Support Timeline

| Version | Status | Support Until |
|---------|--------|---------------|
| v3.0.x | **Active** | Full support |
| v2.5.x | Maintenance | Security fixes until 2026-06-30 |
| v2.0-v2.4 | End of Life | No longer supported |

## Questions?

If you have questions about the migration:

1. Check the [MIGRATION.md](../MIGRATION.md) for detailed migration guidance
2. Review [DEPRECATION.md](../DEPRECATION.md) for deprecation history
3. Open an issue on GitHub
