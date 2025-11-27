# Mypy Level 2 Best Practices

This guide documents best practices for maintaining Level 2 mypy compliance
in the core modules (`agent`, `core`, `config`).

## 📋 Overview

Level 2 applies strict type checking to critical modules:
- `src/agent/` - Gemini API agent and related components
- `src/core/` - Core models, interfaces, and adapters
- `src/config/` - Configuration and settings

### Level 2 Settings

```toml
[[tool.mypy.overrides]]
module = [
    "src.core.*",
    "src.agent.*",
    "src.config.*",
]
check_untyped_defs = true
warn_return_any = true
disallow_untyped_defs = true  # All functions require type hints
no_implicit_optional = true   # No implicit Optional types
```

---

## ✅ Best Practices

### 1. Function Signatures

**Always** include type hints for all function parameters and return types.

```python
# ❌ Bad: Missing type hints
def calculate_cost(usage):
    return usage * self.rate

# ✅ Good: Complete type hints
def calculate_cost(self, usage: dict[str, int]) -> float:
    """Calculate API usage cost."""
    input_cost = usage.get("input_tokens", 0) * self.input_rate
    output_cost = usage.get("output_tokens", 0) * self.output_rate
    return input_cost + output_cost
```

### 2. Explicit Optional Types

With `no_implicit_optional = true`, you must explicitly declare Optional types.

```python
# ❌ Bad: Implicit Optional (None default without Optional)
def get_cache(key: str, default=None):
    pass

# ✅ Good: Explicit Optional
from typing import Optional

def get_cache(key: str, default: Optional[str] = None) -> Optional[dict[str, Any]]:
    pass
```

### 3. Return Type Annotations

Always specify return types, even for methods returning None.

```python
# ❌ Bad: Missing return type
def log_metrics(self, data):
    self.logger.info(data)

# ✅ Good: Explicit None return
def log_metrics(self, data: dict[str, Any]) -> None:
    self.logger.info(data)
```

### 4. Using Generic Types

Use generic types from `typing` or Python 3.9+ built-in generics.

```python
from typing import Dict, List, Optional, Any

# For Python 3.10+, you can use built-in generics:
def process_items(items: list[str]) -> dict[str, int]:
    return {item: len(item) for item in items}

# For compatibility with Python 3.9, use typing module:
def process_items(items: List[str]) -> Dict[str, int]:
    return {item: len(item) for item in items}
```

### 5. Type Aliases

Create type aliases for complex types to improve readability.

```python
# In src/core/type_aliases.py
from typing import Any, Dict, List, Optional

TokenCount = Dict[str, int]
EvaluationScores = Dict[str, float]
CandidateResponse = Dict[str, Any]

# Usage in other modules
from src.core.type_aliases import TokenCount, EvaluationScores

def update_token_count(usage: TokenCount) -> None:
    pass
```

### 6. Pydantic Models

For Pydantic models, use proper Field definitions with types.

```python
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class WorkflowResult(BaseModel):
    """Complete workflow result (Level 2 compliant)."""
    
    original_query: str = Field(..., description="Original query text")
    rewritten_query: Optional[str] = Field(None, description="Rewritten query")
    candidates: List[Dict[str, Any]] = Field(default_factory=list)
    best_candidate: Optional[Dict[str, Any]] = Field(None)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def get_best_score(self) -> Optional[float]:
        """Get score of best candidate."""
        if self.best_candidate:
            return self.best_candidate.get("score")
        return None
```

### 7. Handling Any Types

Minimize use of `Any`. When necessary, use `cast()` to help mypy.

```python
from typing import Any, cast

# ❌ Avoid: Returning Any without validation
def get_data() -> Any:
    return external_api.fetch()

# ✅ Better: Use cast when you know the type
def get_data() -> dict[str, str]:
    result = external_api.fetch()
    return cast(dict[str, str], result)

# ✅ Best: Validate and convert
def get_data() -> dict[str, str]:
    result = external_api.fetch()
    if not isinstance(result, dict):
        raise TypeError("Expected dict from API")
    return result
```

### 8. Protocol Classes for Duck Typing

Use Protocol for structural subtyping (duck typing).

```python
from typing import Protocol

class Cacheable(Protocol):
    """Protocol for objects that can be cached."""
    
    def to_cache_key(self) -> str: ...
    def from_cache(self, data: dict[str, Any]) -> None: ...

# Now any class implementing these methods satisfies Cacheable
class UserSession:
    def to_cache_key(self) -> str:
        return f"session:{self.id}"
    
    def from_cache(self, data: dict[str, Any]) -> None:
        self.data = data
```

### 9. Async Functions

Async functions should have proper return type annotations.

```python
from typing import Optional

async def fetch_user(user_id: str) -> Optional[dict[str, Any]]:
    """Fetch user data asynchronously."""
    result = await db.query(user_id)
    return result
```

### 10. Class Attributes

Use class-level type annotations for instance attributes.

```python
class Agent:
    # Class-level type annotations
    logger: logging.Logger
    config: AppConfig
    cache_hits: int
    
    def __init__(self, config: AppConfig) -> None:
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.cache_hits = 0
```

---

## 🔧 Common Mypy Errors and Fixes

### Error: Missing return type

```
error: Function is missing a return type annotation [no-untyped-def]
```

**Fix:** Add explicit return type.

```python
def process() -> None:  # Add return type
    pass
```

### Error: Incompatible return value

```
error: Incompatible return value type (got "Optional[str]", expected "str")
```

**Fix:** Either handle the None case or update the return type.

```python
# Option 1: Handle None
def get_value(key: str) -> str:
    value = cache.get(key)
    if value is None:
        return ""  # or raise an exception
    return value

# Option 2: Update return type
def get_value(key: str) -> Optional[str]:
    return cache.get(key)
```

### Error: Argument has implicit Optional type

```
error: Argument "default" has implicit None default [implicit-optional]
```

**Fix:** Use explicit Optional.

```python
from typing import Optional

def get(key: str, default: Optional[str] = None) -> Optional[str]:
    pass
```

### Error: Cannot determine type of X

```
error: Cannot determine type of "items" [has-type]
```

**Fix:** Add type annotation.

```python
items: list[str] = []
```

---

## 📊 Validation Commands

Run these commands to validate Level 2 compliance:

```bash
# Check Level 2 modules only
mypy src/agent/ src/core/ src/config/ --config-file pyproject.toml

# Check with detailed error codes
mypy src/agent/ src/core/ src/config/ --show-error-codes

# Generate HTML report
python scripts/check_mypy_baseline.py --html

# Track progress
python scripts/track_mypy_progress.py
```

---

## 📚 References

- [Mypy Documentation](https://mypy.readthedocs.io/)
- [PEP 484 - Type Hints](https://peps.python.org/pep-0484/)
- [PEP 544 - Protocols](https://peps.python.org/pep-0544/)
- [Pydantic Type Hints](https://docs.pydantic.dev/latest/concepts/types/)
