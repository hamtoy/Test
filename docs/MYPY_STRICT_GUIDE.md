# mypy Strict Mode Guide for Contributors

This guide explains how to write code that passes mypy strict mode checks in this project.

## Quick Reference

### Strict Mode Configuration

```toml
[tool.mypy]
strict = true
ignore_missing_imports = false
```

Strict mode enables all strict checks including:
- `disallow_untyped_defs` - All functions need type hints
- `disallow_any_generics` - Generic types need parameters
- `disallow_untyped_calls` - Can't call untyped functions
- `no_implicit_reexport` - Explicit exports required in `__init__.py`
- And more...

## Writing Strict-Compatible Code

### 1. Type All Functions

```python
# ✅ DO: Full type annotations
def process_data(items: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in items:
        result[item] = len(item)
    return result

# ❌ DON'T: Missing types
def process_data(items):
    result = {}
    for item in items:
        result[item] = len(item)
    return result
```

### 2. Use Generic Types with Parameters

```python
# ✅ DO: Explicit generic parameters
from typing import List, Dict, Optional

items: List[str] = []
cache: Dict[str, int] = {}
value: Optional[str] = None

# ❌ DON'T: Bare generics
items = []  # Inferred as list[Unknown]
cache = {}  # Inferred as dict[Unknown, Unknown]
```

### 3. Handle External Libraries Without Stubs

```python
# ✅ DO: Use type: ignore with specific error code and comment
import untyped_lib  # Library docs: https://...

# When calling untyped functions:
response = untyped_lib.call()  # type: ignore[attr-defined]

# ❌ DON'T: Silence all errors globally
# mypy: ignore-errors
```

### 4. Use Custom Type Wrappers for Complex Libraries

For libraries like google-generativeai that lack stubs, use the provided wrappers:

```python
# ✅ DO: Use typed wrappers
from src.llm.gemini_types import (
    configure_genai,
    create_generative_model,
    GenerationConfig,
)

configure_genai(api_key="your-key")
config: GenerationConfig = {"temperature": 0.7}
model = create_generative_model("gemini-1.5-pro", generation_config=config)

# ❌ DON'T: Use raw library without type handling
import google.generativeai as genai
genai.configure(api_key="key")  # Will cause mypy error
```

### 5. Explicit Re-exports in `__init__.py`

```python
# ✅ DO: Explicit __all__ list
from .module import MyClass, my_function

__all__ = ["MyClass", "my_function"]

# ❌ DON'T: Implicit re-exports (strict mode rejects this)
from .module import *
```

## Project-Specific Exceptions

### Packages with Relaxed Checking

These packages are temporarily excluded from strict mode:
- `src.analysis.*`
- `src.features.*`
- `src.ui.*`
- `tests.*`

### External Libraries with Overrides

These libraries have `ignore_missing_imports = true`:
- `google.generativeai` - No type stubs
- `langchain*` - Incomplete stubs
- `tenacity` - No type stubs
- `aiolimiter` - No type stubs
- `pytesseract` - No type stubs

## Running Type Checks

```bash
# Run mypy with project configuration
mypy src/ --config-file pyproject.toml

# Check a specific file
mypy src/your_module.py --config-file pyproject.toml

# Show error codes for debugging
mypy src/ --show-error-codes
```

## Troubleshooting Common Errors

### "Module has no attribute" (attr-defined)

```python
# This usually means the library lacks type stubs
import some_lib
some_lib.function()  # error: Module has no attribute "function"

# Fix: Add type: ignore with the specific error code
some_lib.function()  # type: ignore[attr-defined]
```

### "Function is missing a type annotation" (no-untyped-def)

```python
# Fix: Add return type
def my_function() -> None:  # or appropriate return type
    pass
```

### "Implicit reexport of X" (no-implicit-reexport)

```python
# Fix: Add to __all__
from .module import X

__all__ = ["X"]
```

## Adding New Dependencies

When adding new dependencies:

1. Check for available type stubs:
   ```bash
   python scripts/validation/check_missing_stubs.py
   ```

2. If stubs are available, add them to `pyproject.toml`:
   ```toml
   [project.optional-dependencies]
   dev = [
       "types-your-package>=1.0.0",
   ]
   ```

3. If no stubs exist, add to mypy overrides if needed:
   ```toml
   [[tool.mypy.overrides]]
   module = ["your_package.*"]
   ignore_missing_imports = true
   ```
