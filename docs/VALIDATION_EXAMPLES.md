# Frontend Request Validation Examples

This document demonstrates how the new validation system prevents 422 errors.

## Example 1: Valid Request (Single Mode)

```typescript
// ✅ This passes validation
const payload = {
    mode: "single",
    ocr_text: "마이크로소프트 주가 상승...",
    qtype: "explanation"
};

validateRequest(payload, "/api/qa/generate");
// No error thrown - request is valid
```

## Example 2: Missing Required Field

```typescript
// ❌ This fails validation
const payload = {
    mode: "single",
    ocr_text: "텍스트..."
    // Missing qtype!
};

validateRequest(payload, "/api/qa/generate");
// Throws: ValidationError: qtype: single 모드에서는 qtype이 필수입니다 (문자열)
```

## Example 3: Field Name Typo (camelCase instead of snake_case)

```typescript
// ❌ This fails validation
const payload = {
    mode: "single",
    ocrText: "텍스트...",  // Wrong! Should be ocr_text
    qtype: "explanation"
};

validateRequest(payload, "/api/qa/generate");
// Throws: ValidationError: field_names: ⚠️ 필드명 오타: "ocrText" → 올바른 필드명: "ocr_text" (snake_case 사용)
```

## Example 4: Wrong Data Type

```typescript
// ❌ This fails validation
const payload = {
    mode: "single",
    ocr_text: 123,  // Wrong! Should be string
    qtype: "explanation"
};

validateRequest(payload, "/api/qa/generate");
// Throws: ValidationError: ocr_text: 문자열이어야 합니다
```

## Example 5: Invalid Enum Value

```typescript
// ❌ This fails validation
const payload = {
    mode: "single",
    ocr_text: "텍스트...",
    qtype: "invalid_type"  // Not a valid qtype!
};

validateRequest(payload, "/api/qa/generate");
// Throws: ValidationError: qtype: 유효하지 않은 값: "invalid_type". 가능한 값: global_explanation, explanation, reasoning, target_short, target_long, target
```

## Example 6: Batch Mode with Custom Types

```typescript
// ✅ This passes validation
const payload = {
    mode: "batch",
    ocr_text: "텍스트...",
    batch_types: ["explanation", "reasoning", "target_long"]
};

validateRequest(payload, "/api/qa/generate");
// No error thrown - request is valid
```

## Example 7: Workspace Request

```typescript
// ✅ This passes validation
const payload = {
    mode: "full",
    query: "한국 증시 전망은?",
    answer: null,
    edit_request: null,
    ocr_text: "텍스트...",
    query_type: "explanation",
    global_explanation_ref: null
};

validateRequest(payload, "/api/workspace/unified");
// No error thrown - request is valid
```

## Example 8: Handling 422 Error Response

```typescript
try {
    const response = await fetch("/api/qa/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });

    if (!response.ok) {
        if (response.status === 422) {
            const errorData = await response.json();
            const message = parse422Error(errorData);
            console.error(message);
            // Output:
            // 요청 데이터 검증 실패:
            // • qtype: field required
        }
    }
} catch (error) {
    // Handle error
}
```

## Example 9: Backend Response Format (422)

When the backend returns a 422 error, the response looks like:

```json
{
  "detail": [
    {
      "loc": ["body", "qtype"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

The `parse422Error()` function converts this to a user-friendly message:

```
요청 데이터 검증 실패:
• qtype: field required
```

## Example 10: Checking Field Names Proactively

```typescript
const payload = {
    mode: "single",
    ocrText: "텍스트...",  // Wrong field name
    queryType: "explanation"  // Wrong field name
};

const warnings = checkFieldNames(payload);
// Returns:
// [
//   "⚠️ 필드명 오타: \"ocrText\" → 올바른 필드명: \"ocr_text\" (snake_case 사용)",
//   "⚠️ 필드명 오타: \"queryType\" → 올바른 필드명: \"query_type\" (snake_case 사용)"
// ]
```

## Integration in QA Page

The QA page (`static/qa.ts`) now validates requests before sending:

```typescript
async function generateQA(mode: GenerateMode, qtype: string | null): Promise<void> {
    // ... prepare payload ...

    try {
        // Validate before sending
        validateRequest(payload, "/api/qa/generate");

        // If validation passes, send request
        const result = await apiCall("/api/qa/generate", "POST", payload);
        displayResults(result);
    } catch (error) {
        if (error instanceof ValidationError) {
            // Show user-friendly error message
            showToast(`요청 검증 실패: ${error.message}`, "error");
            return;
        }
        // Handle other errors
    }
}
```

## Integration in Workspace Page

The workspace page (`static/workspace.ts`) also validates requests:

```typescript
async function executeWorkspace(...) {
    const body = { mode, query, answer, ocr_text, query_type, ... };

    try {
        // Validate before sending
        validateRequest(body, "/api/workspace/unified");

        // Send request
        const result = await apiCallWithRetry({
            url: "/api/workspace/unified",
            method: "POST",
            body
        });
        displayResult(result);
    } catch (error) {
        if (error instanceof ValidationError) {
            // Show error in results div
            resultsDiv.innerHTML = `
                <div class="error">
                    <h3>⚠️ 요청 데이터 오류</h3>
                    <p>${error.message}</p>
                </div>
            `;
            return;
        }
    }
}
```

## Benefits

1. **Early Error Detection**: Errors are caught before sending the request, saving network round-trip time
2. **Clear Error Messages**: Users see exactly what's wrong with their request
3. **Developer-Friendly**: Detects common mistakes like camelCase field names
4. **Type Safety**: Ensures all fields have correct types
5. **Enum Validation**: Validates that enum fields have valid values
6. **Documentation**: Serves as living documentation of API requirements

## Common Mistakes Prevented

| Mistake | Detection | Error Message |
|---------|-----------|---------------|
| `ocrText` instead of `ocr_text` | Field name check | `필드명 오타: "ocrText" → 올바른 필드명: "ocr_text"` |
| Missing `qtype` in single mode | Required field check | `qtype: single 모드에서는 qtype이 필수입니다` |
| `qtype: "invalid"` | Enum validation | `유효하지 않은 값: "invalid". 가능한 값: ...` |
| `ocr_text: 123` (number) | Type validation | `ocr_text: 문자열이어야 합니다` |
| `batch_types: "string"` (not array) | Type validation | `batch_types: 배열이어야 합니다` |

## See Also

- [TROUBLESHOOTING_422_ERRORS.md](./TROUBLESHOOTING_422_ERRORS.md) - Comprehensive troubleshooting guide
- [validation.ts](../static/validation.ts) - Implementation source code
- [validation.test.ts](../static/__tests__/validation.test.ts) - Test suite
