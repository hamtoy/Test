# Frontend TypeScript Modules

This directory contains the TypeScript modules for the web application frontend.

## 📁 File Structure

```
static/
├── __tests__/          # Test files
│   ├── utils.test.ts
│   └── validation.test.ts
├── dist/               # Build output (generated)
│   ├── app.js
│   └── chunks/
│       ├── qa.js
│       ├── workspace.js
│       ├── eval.js
│       ├── ocr.js
│       └── validation.js
├── app.ts              # Main application entry point
├── qa.ts               # QA generation page logic
├── workspace.ts        # Workspace page logic
├── eval.ts             # Evaluation page logic
├── ocr.ts              # OCR text management
├── utils.ts            # Common utilities (API calls, toasts, etc.)
├── validation.ts       # Request validation helpers (NEW in v3.1)
└── style.css           # Global styles
```

## 🆕 New in v3.1: Request Validation

### validation.ts

Provides comprehensive request validation to prevent **422 Unprocessable Content** errors before sending API requests.

**Features:**
- ✅ Field name validation (detects camelCase vs snake_case mistakes)
- ✅ Type checking for all fields
- ✅ Required field validation
- ✅ Enum value validation
- ✅ Detailed error messages
- ✅ 422 error response parsing

**Usage:**

```typescript
import { validateRequest, ValidationError } from "./validation.js";

try {
    const payload = {
        mode: "single",
        ocr_text: "sample text",
        qtype: "explanation"
    };

    // Validate before sending
    validateRequest(payload, "/api/qa/generate");

    // If validation passes, send request
    const result = await apiCall("/api/qa/generate", "POST", payload);
} catch (error) {
    if (error instanceof ValidationError) {
        console.error("Validation failed:", error.message);
    }
}
```

See [VALIDATION_EXAMPLES.md](../docs/VALIDATION_EXAMPLES.md) for more examples.

## 📦 Core Modules

### app.ts
Main application entry point. Initializes the correct page module based on the current route.

### qa.ts
**QA Generation Page** (`/qa`)
- Batch and single mode QA generation
- OCR text input
- Query type selection
- Result display with copy-to-workspace functionality

### workspace.ts
**Workspace Page** (`/workspace`)
- Unified workflow execution
- Full/query-only/answer-only modes
- Global explanation reference management
- Edit request handling

### eval.ts
**Evaluation Page** (`/eval`)
- External answer evaluation
- 3-candidate answer comparison
- Feedback display

### ocr.ts
**OCR Text Management**
- Load OCR text from server
- Save OCR text to server
- Shared across all pages

### utils.ts
**Common Utilities**
- `apiCall()` - Fetch wrapper with error handling
- `apiCallWithRetry()` - Retry logic for failed requests
- `showToast()` - Toast notification system
- `copyToClipboard()` - Clipboard functionality
- `withRetry()` - Generic retry wrapper
- `parse422Error()` - NEW: Parse 422 validation errors (uses validation.ts)

## 🧪 Testing

Run tests with:

```bash
npm test
```

Test files are in `__tests__/`:
- `utils.test.ts` - Tests for utils.ts
- `validation.test.ts` - Tests for validation.ts (35 tests)

## 🏗️ Build

Build TypeScript to JavaScript:

```bash
npm run build
```

Output goes to `dist/` directory and is served by the web server.

## 🔧 Development

### Adding a New Page Module

1. Create `newpage.ts` in this directory
2. Export an `initNewPage()` function
3. Add routing logic in `app.ts`
4. Create corresponding HTML template in `templates/web/`
5. Build and test

### Adding Validation for New Endpoint

1. Define request interface in `validation.ts`
2. Add validation function (e.g., `validateNewRequest()`)
3. Add endpoint-specific logic to `validateRequest()`
4. Write tests in `__tests__/validation.test.ts`
5. Update page module to use validation

## 📚 Documentation

- [TROUBLESHOOTING_422_ERRORS.md](../docs/TROUBLESHOOTING_422_ERRORS.md) - How to fix 422 validation errors
- [VALIDATION_EXAMPLES.md](../docs/VALIDATION_EXAMPLES.md) - Validation usage examples
- [WEB_API_ENDPOINTS.md](../docs/WEB_API_ENDPOINTS.md) - API endpoint documentation

## 🎯 Code Quality Guidelines

### TypeScript Best Practices
- ✅ Use strict type checking
- ✅ Define interfaces for all data structures
- ✅ Avoid `any` type (use `unknown` instead)
- ✅ Use discriminated unions for variants
- ✅ Handle all error cases

### API Request Guidelines
- ✅ **Always validate requests** before sending (use `validateRequest()`)
- ✅ Use `apiCallWithRetry()` for better reliability
- ✅ Handle 422 errors with user-friendly messages
- ✅ Use snake_case for field names (backend convention)
- ✅ Check field types match backend Pydantic models

### Error Handling
- ✅ Catch specific error types (`ValidationError`, `ApiError`)
- ✅ Show user-friendly error messages
- ✅ Log errors to console for debugging
- ✅ Don't expose internal error details to users

## 🔐 Security

### Input Sanitization
All user inputs are sanitized before display:
- HTML content uses `DOMPurify.sanitize()`
- Text content uses `escapeHtml()`
- Avoid `innerHTML` with unsanitized data

### API Security
- All requests use JSON content type
- No sensitive data in URLs
- Validation prevents injection attacks

## 🚀 Performance

### Optimization Techniques
- Debounced input validation (150ms)
- Retry with exponential backoff
- Progress indicators for long operations
- Cached OCR text (with mtime check)

### Bundle Size
Current gzipped sizes:
- `app.js`: ~2.6 KB
- `qa.js`: ~2.9 KB
- `workspace.js`: ~3.1 KB
- `validation.js`: ~1.3 KB
- Total: ~10 KB (excellent!)

## 🔄 Version History

### v3.1 (2024-12-08)
- ✨ Added comprehensive request validation system
- ✨ Added 422 error handling and parsing
- ✨ Added field name validation (camelCase detection)
- 📝 Added TROUBLESHOOTING_422_ERRORS.md
- 📝 Added VALIDATION_EXAMPLES.md
- 🧪 Added 35 validation tests

### v3.0
- 🔄 Migrated to TypeScript
- 🔄 Unified workspace API
- ✨ Added retry logic
- ✨ Improved error handling

## 📞 Support

For issues or questions:
1. Check [TROUBLESHOOTING_422_ERRORS.md](../docs/TROUBLESHOOTING_422_ERRORS.md)
2. Check [VALIDATION_EXAMPLES.md](../docs/VALIDATION_EXAMPLES.md)
3. Check console for detailed error messages
4. Check Network tab in DevTools
5. Create GitHub issue with details
