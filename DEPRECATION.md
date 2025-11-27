# Deprecation Notice

## v2.5 Enhancements ⚠️

Version 2.5 introduces an enhanced deprecation warning system with improved visibility and control.

### Environment Variables

| Variable | Values | Description |
|----------|--------|-------------|
| `DEPRECATION_LEVEL` | `normal` (default) | Always show deprecation warnings |
| | `strict` | Raise `ImportError` for deprecated imports |
| | `verbose` | Include full stack trace in warnings |

#### Examples

```bash
# Normal mode (default) - shows warnings
python your_script.py

# Strict mode - fails on deprecated imports
DEPRECATION_LEVEL=strict python your_script.py

# Verbose mode - shows detailed stack traces
DEPRECATION_LEVEL=verbose python your_script.py
```

### Pre-commit Hook

A new pre-commit hook detects deprecated imports at commit time:

```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: check-deprecated-imports
      name: Deprecated Import Scanner
      entry: python scripts/check_deprecated_imports.py
      language: system
      types: [python]
      pass_filenames: true
```

---

## v2.x → v3.0 Breaking Changes

The following deprecated import paths will be **removed in v3.0**.
Please refer to [MIGRATION.md](MIGRATION.md) for detailed migration guides.

### Removed Shim Files

| Deprecated Import | New Import | Remove in |
|-------------------|------------|-----------|
| `from src.utils import ...` | `from src.infra.utils import ...` | v3.0 |
| `from src.logging_setup import ...` | `from src.infra.logging import ...` | v3.0 |
| `from src.config import AppConfig` | `from src.config import AppConfig` | ✅ Same |
| `from src.constants import ...` | `from src.config.constants import ...` | v3.0 |
| `from src.exceptions import ...` | `from src.config.exceptions import ...` | v3.0 |
| `from src.models import ...` | `from src.core.models import ...` | v3.0 |
| `from src.neo4j_utils import ...` | `from src.infra.neo4j import ...` | v3.0 |
| `from src.worker import ...` | `from src.infra.worker import ...` | v3.0 |
| `from src.data_loader import ...` | `from src.processing.loader import ...` | v3.0 |
| `from src.qa_rag_system import ...` | `from src.qa.rag_system import ...` | v3.0 |
| `from src.caching_layer import ...` | `from src.caching.layer import ...` | v3.0 |
| `from src.graph_enhanced_router import ...` | `from src.routing.graph_router import ...` | v3.0 |

### Migration Script

We provide an automated script to migrate your imports:

```bash
# Auto-migrate imports
migrate-imports --check  # Dry run
migrate-imports --fix    # Apply changes
```

### Timeline

- **v2.0**: Deprecated imports work with warnings
- **v2.5**: Enhanced deprecation warnings with visibility improvements
- **v3.0**: Shim files removed, old imports fail

### FAQ

**Q: Why am I seeing more deprecation warnings in v2.5?**

A: Version 2.5 uses `EnhancedDeprecationWarning` which bypasses Python's default warning filter that typically shows each warning only once. This ensures you see all deprecated import usages.

**Q: How do I make my CI fail on deprecated imports?**

A: Set `DEPRECATION_LEVEL=strict` in your CI environment:

```yaml
# GitHub Actions example
env:
  DEPRECATION_LEVEL: strict
```

**Q: Can I suppress the warnings temporarily?**

A: Yes, but we recommend migrating instead. If needed:

```python
import warnings
from src._deprecation import EnhancedDeprecationWarning
warnings.filterwarnings("ignore", category=EnhancedDeprecationWarning)
```
