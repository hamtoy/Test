# 🤖 Project Auto-Improvement Prompts

> **Usage Guide:**
> These prompts should be executed **sequentially** by an AI agent.
> Execute all prompts from start to finish. Do **NOT** skip any steps.
>
> ⚠️ **IMPORTANT:** Before starting, read `devplan/Project_Improvement_Exploration_Report.md`.

## 📋 Execution Checklist

| # | Prompt ID | Title | Priority | Status |
|:---:|:---|:---|:---:|:---:|
| 1 | PROMPT-001 | LATS Module Documentation Guide | P2 | ✅ Done |
| 2 | PROMPT-002 | Frontend-Backend Integration Guide | P2 | ✅ Done |
| 3 | PROMPT-003 | Frontend Vitest Test Coverage | P3 | ✅ Done |
| 4 | OPT-1 | Frontend Bundle Optimization | OPT | ✅ Done |
| 5 | FINISH | Final Verification and Cleanup | - | ✅ Done |

Total: 4 prompts | Completed: 4 | Remaining: 0

---

## 🟡 [PROMPT-001] LATS Module Documentation Guide

**Title:** Create comprehensive LATS/Self-Correction module documentation
**Target:** `docs/LATS_GUIDE.md`, `README.md`

**Context:**
The LATS (Language Agent Tree Search) and self-correction modules exist in `src/lats/` but lack operational documentation. Users cannot easily understand how to enable, configure, or tune these features.

**Task:**

1. Create `docs/LATS_GUIDE.md` with the following sections:
   - Overview of LATS functionality
   - Configuration options (`ENABLE_LATS`, search depth, etc.)
   - Usage examples (CLI and programmatic)
   - Performance tuning recommendations
2. Add a link to this guide in `README.md` under the "Advanced Features" section.
3. Include at least one complete usage example with code snippets.

**Verification:**

```bash
# Check file exists
test -f docs/LATS_GUIDE.md && echo "OK"
# Verify README link
grep -q "LATS_GUIDE" README.md && echo "OK"
```

After completing this prompt, proceed to **[PROMPT-002]**.

---

## 🟡 [PROMPT-002] Frontend-Backend Integration Guide

**Title:** Create frontend-backend integration documentation
**Target:** `docs/FRONTEND_INTEGRATION.md`, `packages/frontend/`

**Context:**
A Vite/Vitest-based frontend exists in `packages/frontend/`, but there is no documentation on how to connect it to the FastAPI backend. Frontend developers lack clarity on API endpoints, authentication, and CORS configuration.

**Task:**

1. Create `docs/FRONTEND_INTEGRATION.md` with:
   - List of available API endpoints (from `src/web/routers/`)
   - Environment variable setup for frontend (API base URL, etc.)
   - CORS configuration guide
   - Development workflow (running both frontend and backend)
2. Document the following key endpoints:
   - `GET /api/ocr` - OCR text retrieval
   - `POST /api/ocr` - OCR text save
   - `GET /api/cache/summary` - Cache statistics
   - Health check endpoints
3. Include example fetch/axios calls for frontend usage.

**Verification:**

```bash
# Check file exists
test -f docs/FRONTEND_INTEGRATION.md && echo "OK"
```

After completing this prompt, proceed to **[PROMPT-003]**.

---

## 🟢 [PROMPT-003] Frontend Vitest Test Coverage

**Title:** Expand Vitest test coverage for frontend components
**Target:** `packages/frontend/src/`, `packages/frontend/tests/`

**Context:**
The Vitest testing environment is set up in `packages/frontend/`, but component test coverage is low. Frontend changes may introduce regression bugs that go undetected.

**Task:**

1. Analyze existing components in `packages/frontend/src/` to identify untested components.
2. Create unit tests for at least 3 major components:
   - Test component rendering
   - Test user interactions (clicks, input)
   - Test prop variations
3. Update `packages/frontend/package.json` if needed to ensure test scripts work.
4. Verify tests pass locally.

**Verification:**

```bash
cd packages/frontend
pnpm run test
# EXPECTED: All tests passing
```

After completing this prompt, proceed to **[OPT-1]**.

---

## 🚀 [OPT-1] Frontend Bundle Optimization

**Title:** Optimize frontend bundle size and loading performance
**Target:** `packages/frontend/vite.config.ts`, `packages/frontend/src/`

**Context:**
The frontend bundle may not be optimized for production, leading to longer initial load times. Code splitting and tree-shaking improvements can enhance user experience.

**Task:**

1. Analyze current bundle size using `vite-bundle-analyzer` or similar tool.
2. Implement optimizations in `vite.config.ts`:
   - Enable code splitting for routes
   - Configure tree-shaking for unused exports
   - Add chunk naming for better caching
3. Document bundle size before and after optimization.
4. Verify production build works correctly.

**Implementation Details:**

```typescript
// vite.config.ts optimizations
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          // Add other chunks as needed
        },
      },
    },
  },
});
```

**Verification:**

```bash
cd packages/frontend
pnpm run build
# Check bundle size in dist/
```

After completing this prompt, proceed to **[FINISH]**.

---

## 🏁 Final Completion

**Task:**

1. Run the full test suite to ensure no regressions:

   ```bash
   uv run python -m pytest
   cd packages/frontend && pnpm run test
   ```

2. Verify all documentation files were created:

   ```bash
   test -f docs/LATS_GUIDE.md && echo "LATS Guide OK"
   test -f docs/FRONTEND_INTEGRATION.md && echo "Frontend Guide OK"
   ```

3. Print the following success message:
   > "🎉 ALL PROMPTS COMPLETED. All pending improvement and optimization items from the latest report have been applied."

---
