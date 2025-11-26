# Deprecation Notice

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
- **v2.5**: Deprecation warnings become errors (optional)
- **v3.0**: Shim files removed, old imports fail
