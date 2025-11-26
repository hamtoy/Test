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

## 📋 Session Workflow

### Session Start (5 min)

```powershell
# 1. Get latest code
git pull origin main

# 2. Save current error snapshot
uv run mypy src/ --strict 2>&1 | Out-File mypy_errors.txt

# 3. Check progress
.\scripts\check_mypy_progress.ps1

# 4. Count errors
(Get-Content mypy_errors.txt | Select-String "error:").Count
```

### Work Loop (20-30 min cycles)

**Repeat until target reached:**

1. **Pick error pattern** (e.g., all `no-untyped-def` in agent/)
2. **Fix 10-15 files** (use templates below)
3. **Verify**: `uv run mypy src/ --strict`
4. **Test**: `uv run pytest tests/ -q`
5. **Commit**: `git add . && git commit -m "fix(types): add return types to agent/"`
6. **Progress check**: `.\scripts\check_mypy_progress.ps1`

### Session End (10 min)

```powershell
# 1. Final check
uv run mypy src/ --strict

# 2. Push
git push origin main

# 3. Record progress
# Update: 155 → X errors (Y fixed, Z% complete)
```

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
