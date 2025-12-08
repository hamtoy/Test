/**
 * API Request Validation Helper
 * 
 * Provides validation functions to prevent 422 validation errors
 * by checking request payloads before sending to the backend.
 */

/**
 * Validation error class
 */
export class ValidationError extends Error {
    constructor(public field: string, message: string) {
        super(`${field}: ${message}`);
        this.name = "ValidationError";
    }
}

/**
 * Required fields for /api/qa/generate endpoint
 */
interface GenerateQAPayload {
    mode: "single" | "batch" | "batch_three";
    ocr_text?: string;
    qtype?: string;
    batch_types?: string[];
}

/**
 * Required fields for /api/workspace/unified endpoint
 */
interface UnifiedWorkspacePayload {
    mode?: string;
    query?: string | null;
    answer?: string | null;
    edit_request?: string | null;
    ocr_text?: string | null;
    query_type?: string | null;
    global_explanation_ref?: string | null;
}

/**
 * Validate GenerateQA request payload
 * 
 * @param data Request payload to validate
 * @throws ValidationError if validation fails
 */
export function validateGenerateQARequest(data: unknown): asserts data is GenerateQAPayload {
    if (!data || typeof data !== "object") {
        throw new ValidationError("payload", "요청 데이터가 객체여야 합니다");
    }

    const payload = data as Record<string, unknown>;

    // Validate mode
    if (!payload.mode || typeof payload.mode !== "string") {
        throw new ValidationError("mode", "필수 필드 누락 또는 타입 오류 (문자열 필요)");
    }

    const validModes = ["single", "batch", "batch_three"];
    if (!validModes.includes(payload.mode)) {
        throw new ValidationError(
            "mode",
            `유효하지 않은 값: "${payload.mode}". 가능한 값: ${validModes.join(", ")}`
        );
    }

    // Validate ocr_text (optional, but must be string if provided)
    if (payload.ocr_text !== undefined && payload.ocr_text !== null) {
        if (typeof payload.ocr_text !== "string") {
            throw new ValidationError("ocr_text", "문자열이어야 합니다");
        }
    }

    // Validate qtype for single mode
    if (payload.mode === "single") {
        if (!payload.qtype || typeof payload.qtype !== "string") {
            throw new ValidationError(
                "qtype",
                "single 모드에서는 qtype이 필수입니다 (문자열)"
            );
        }

        // Accept both exact Pydantic values and common aliases that backend normalizes
        const validQTypes = [
            "global_explanation",
            "explanation",  // Alias for global_explanation
            "globalexplanation",  // Alias for global_explanation
            "reasoning",
            "target_short",
            "target_long",
            "target",  // Alias accepted by backend
        ];
        if (!validQTypes.includes(payload.qtype)) {
            throw new ValidationError(
                "qtype",
                `유효하지 않은 값: "${payload.qtype}". 가능한 값: ${validQTypes.slice(0, 6).join(", ")}`
            );
        }
    }

    // Validate batch_types (optional array)
    if (payload.batch_types !== undefined && payload.batch_types !== null) {
        if (!Array.isArray(payload.batch_types)) {
            throw new ValidationError("batch_types", "배열이어야 합니다");
        }

        for (let i = 0; i < payload.batch_types.length; i++) {
            if (typeof payload.batch_types[i] !== "string") {
                throw new ValidationError(
                    `batch_types[${i}]`,
                    "모든 요소가 문자열이어야 합니다"
                );
            }
        }
    }
}

/**
 * Validate UnifiedWorkspace request payload
 * 
 * @param data Request payload to validate
 * @throws ValidationError if validation fails
 */
export function validateUnifiedWorkspaceRequest(data: unknown): asserts data is UnifiedWorkspacePayload {
    if (!data || typeof data !== "object") {
        throw new ValidationError("payload", "요청 데이터가 객체여야 합니다");
    }

    const payload = data as Record<string, unknown>;

    // All fields are optional but must have correct types if provided
    const stringFields = ["mode", "query", "answer", "edit_request", "ocr_text", "query_type", "global_explanation_ref"];

    for (const field of stringFields) {
        const value = payload[field];
        if (value !== undefined && value !== null && typeof value !== "string") {
            throw new ValidationError(field, `문자열이어야 합니다. 받은 타입: ${typeof value}`);
        }
    }

    // Validate query_type values if provided
    if (payload.query_type && typeof payload.query_type === "string") {
        // Accept both exact Pydantic values and common aliases
        const validQTypes = [
            "global_explanation",
            "explanation",  // Alias
            "globalexplanation",  // Alias
            "reasoning",
            "target_short",
            "target_long",
            "target",  // Alias
        ];
        if (!validQTypes.includes(payload.query_type)) {
            throw new ValidationError(
                "query_type",
                `유효하지 않은 값: "${payload.query_type}". 가능한 값: ${validQTypes.slice(0, 6).join(", ")}`
            );
        }
    }
}

/**
 * Check for common field name errors (camelCase vs snake_case)
 * 
 * @param data Request payload to check
 * @returns Array of warnings about potential field name issues
 */
export function checkFieldNames(data: unknown): string[] {
    if (!data || typeof data !== "object") {
        return [];
    }

    const warnings: string[] = [];
    const payload = data as Record<string, unknown>;

    // Common mistakes: camelCase instead of snake_case
    const incorrectFields: Record<string, string> = {
        "ocrText": "ocr_text",
        "queryType": "query_type",
        "editRequest": "edit_request",
        "batchTypes": "batch_types",
        "globalExplanationRef": "global_explanation_ref",
    };

    for (const [incorrect, correct] of Object.entries(incorrectFields)) {
        if (incorrect in payload) {
            warnings.push(
                `⚠️ 필드명 오타: "${incorrect}" → 올바른 필드명: "${correct}" (snake_case 사용)`
            );
        }
    }

    return warnings;
}

/**
 * Normalize and validate request data before API call
 * 
 * @param data Request payload
 * @param endpoint API endpoint being called
 * @throws ValidationError if validation fails
 */
export function validateRequest(data: unknown, endpoint: string): void {
    // Check for field name issues first
    const warnings = checkFieldNames(data);
    if (warnings.length > 0) {
        throw new ValidationError("field_names", warnings.join("\n"));
    }

    // Validate based on endpoint
    if (endpoint.includes("/api/qa/generate")) {
        validateGenerateQARequest(data);
    } else if (endpoint.includes("/api/workspace/unified")) {
        validateUnifiedWorkspaceRequest(data);
    }
}

/**
 * Parse 422 validation error response from backend
 * 
 * @param errorData Error response from backend
 * @returns Human-readable error message
 */
export function parse422Error(errorData: unknown): string {
    if (!errorData || typeof errorData !== "object") {
        return "요청 데이터 검증 실패";
    }

    const data = errorData as Record<string, unknown>;

    // FastAPI validation error format
    if (Array.isArray(data.detail)) {
        const errors = data.detail as Array<{
            loc?: string[];
            msg?: string;
            type?: string;
        }>;

        const messages = errors.map((err) => {
            const field = err.loc?.slice(1).join(".") || "unknown";
            const message = err.msg || "validation error";
            return `• ${field}: ${message}`;
        });

        return `요청 데이터 검증 실패:\n${messages.join("\n")}`;
    }

    // Fallback
    if (typeof data.detail === "string") {
        return data.detail;
    }

    return "요청 데이터 검증 실패";
}
