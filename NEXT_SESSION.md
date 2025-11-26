# Next Session: Mypy Strict Type Enhancement

## 📍 Current Status

- **Errors**: 155 remaining (down from 180)
- **Commits**: 3 pushed to main
- **Completion**: 14% (Phase 1 partially complete)

## 🎯 Next Session Goals

### Priority 1: Complete Phase 1 (Remaining 155 errors)

**Target Packages** (in order):

1. **agent/** (34 errors) - Already started
   - `core.py` - Add return types to methods
   - `cost_tracker.py` - Add return types
   - `cache_manager.py` - Type annotations
   - `rate_limiter.py` - Type annotations

2. **infra/** (32 errors) - Already started
   - `neo4j.py` - Add function type annotations
   - `worker.py` - Fix dict type parameters
   - `budget.py` - Add annotations

3. **analysis/** (15 errors)
   - `semantic.py` - Add Counter[str] type parameters
   - `document_compare.py` - Add Dict[str, Any] parameters

4. **llm/** (14 errors)
   - Add type annotations to generate(), evaluate(), rewrite()

5. **processing/** (9 errors)
   - `template_generator.py` - Add return types

### Common Error Patterns to Fix

**Pattern 1: Missing Function Return Types**

```python
# Before
def method(self):
    ...

# After
def method(self) -> None:
    ...
```

**Pattern 2: Missing Generic Type Parameters**

```python
# Before
def func() -> Dict:
    ...

# After
def func() -> Dict[str, Any]:
    ...
```

**Pattern 3: Missing Counter Type Parameters**

```python
# Before
from collections import Counter
counts: Counter = Counter()

# After
from collections import Counter
counts: Counter[str] = Counter()
```

## 📋 Verification Commands

After each batch of fixes:

```bash
# Check specific package
uv run mypy src/agent/ --strict

# Check all Phase 1 packages
uv run mypy src/{main.py,config,core,agent,infra} --strict

# Full check
uv run mypy src/ --strict
```

## 🚀 Phase 2 Preview (After Phase 1)

Once Phase 1 is complete:

- llm/ (14 errors)
- qa/ (13 errors)
- analysis/ (15 errors)
- processing/ (9 errors)

## 💡 Tips for Next Session

1. **Batch Processing**: Group similar error types together
2. **Test Frequently**: Run mypy after every 5-10 file changes
3. **Use Patterns**: Most errors follow the 3 patterns above
4. **Commit Often**: Commit every 20-30 fixes

## 📂 Files to Focus On

High-impact files (fixing these resolves many errors):

- `src/agent/core.py` (10+ errors)
- `src/infra/neo4j.py` (5+ errors)
- `src/analysis/semantic.py` (8+ errors)
- `src/processing/template_generator.py` (5+ errors)
