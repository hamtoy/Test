import { describe, it, expect } from "vitest";
import {
    validateGenerateQARequest,
    validateUnifiedWorkspaceRequest,
    checkFieldNames,
    validateRequest,
    parse422Error,
    ValidationError,
} from "../validation.js";

describe("validateGenerateQARequest", () => {
    it("accepts valid single mode request", () => {
        const payload = {
            mode: "single",
            ocr_text: "sample OCR text",
            qtype: "explanation",
        };

        expect(() => validateGenerateQARequest(payload)).not.toThrow();
    });

    it("accepts valid batch mode request", () => {
        const payload = {
            mode: "batch",
            ocr_text: "sample OCR text",
        };

        expect(() => validateGenerateQARequest(payload)).not.toThrow();
    });

    it("accepts valid batch_three mode request", () => {
        const payload = {
            mode: "batch_three",
            ocr_text: "sample OCR text",
            batch_types: ["explanation", "reasoning", "target_long"],
        };

        expect(() => validateGenerateQARequest(payload)).not.toThrow();
    });

    it("rejects missing mode", () => {
        const payload = {
            ocr_text: "sample OCR text",
        };

        expect(() => validateGenerateQARequest(payload)).toThrow(ValidationError);
        expect(() => validateGenerateQARequest(payload)).toThrow(/mode/);
    });

    it("rejects invalid mode value", () => {
        const payload = {
            mode: "invalid",
            ocr_text: "sample OCR text",
        };

        expect(() => validateGenerateQARequest(payload)).toThrow(ValidationError);
        expect(() => validateGenerateQARequest(payload)).toThrow(/유효하지 않은 값/);
    });

    it("rejects missing qtype in single mode", () => {
        const payload = {
            mode: "single",
            ocr_text: "sample OCR text",
        };

        expect(() => validateGenerateQARequest(payload)).toThrow(ValidationError);
        expect(() => validateGenerateQARequest(payload)).toThrow(/qtype/);
    });

    it("rejects invalid qtype value", () => {
        const payload = {
            mode: "single",
            ocr_text: "sample OCR text",
            qtype: "invalid_type",
        };

        expect(() => validateGenerateQARequest(payload)).toThrow(ValidationError);
        expect(() => validateGenerateQARequest(payload)).toThrow(/유효하지 않은 값/);
    });

    it("rejects wrong ocr_text type", () => {
        const payload = {
            mode: "single",
            ocr_text: 123, // should be string
            qtype: "explanation",
        };

        expect(() => validateGenerateQARequest(payload)).toThrow(ValidationError);
        expect(() => validateGenerateQARequest(payload)).toThrow(/ocr_text/);
    });

    it("rejects batch_types as non-array", () => {
        const payload = {
            mode: "batch",
            ocr_text: "sample OCR text",
            batch_types: "not-an-array",
        };

        expect(() => validateGenerateQARequest(payload)).toThrow(ValidationError);
        expect(() => validateGenerateQARequest(payload)).toThrow(/배열/);
    });

    it("rejects batch_types with non-string elements", () => {
        const payload = {
            mode: "batch",
            ocr_text: "sample OCR text",
            batch_types: ["explanation", 123, "reasoning"],
        };

        expect(() => validateGenerateQARequest(payload)).toThrow(ValidationError);
        expect(() => validateGenerateQARequest(payload)).toThrow(/문자열/);
    });

    it("accepts null payload", () => {
        expect(() => validateGenerateQARequest(null)).toThrow(ValidationError);
        expect(() => validateGenerateQARequest(null)).toThrow(/객체/);
    });

    it("accepts all valid qtype values", () => {
        const validQTypes = ["global_explanation", "reasoning", "target_short", "target_long"];

        for (const qtype of validQTypes) {
            const payload = {
                mode: "single",
                ocr_text: "sample",
                qtype,
            };
            expect(() => validateGenerateQARequest(payload)).not.toThrow();
        }
    });
});

describe("validateUnifiedWorkspaceRequest", () => {
    it("accepts valid full request", () => {
        const payload = {
            mode: "full",
            query: "test query",
            answer: "test answer",
            edit_request: "edit this",
            ocr_text: "sample OCR",
            query_type: "explanation",
            global_explanation_ref: "reference text",
        };

        expect(() => validateUnifiedWorkspaceRequest(payload)).not.toThrow();
    });

    it("accepts request with all fields as null", () => {
        const payload = {
            mode: null,
            query: null,
            answer: null,
            edit_request: null,
            ocr_text: null,
            query_type: null,
            global_explanation_ref: null,
        };

        expect(() => validateUnifiedWorkspaceRequest(payload)).not.toThrow();
    });

    it("rejects non-string mode", () => {
        const payload = {
            mode: 123,
            query: "test",
        };

        expect(() => validateUnifiedWorkspaceRequest(payload)).toThrow(ValidationError);
        expect(() => validateUnifiedWorkspaceRequest(payload)).toThrow(/mode/);
    });

    it("rejects invalid query_type", () => {
        const payload = {
            query_type: "invalid_type",
        };

        expect(() => validateUnifiedWorkspaceRequest(payload)).toThrow(ValidationError);
        expect(() => validateUnifiedWorkspaceRequest(payload)).toThrow(/query_type/);
    });

    it("accepts valid query_type values", () => {
        const validTypes = ["global_explanation", "reasoning", "target_short", "target_long"];

        for (const query_type of validTypes) {
            const payload = { query_type };
            expect(() => validateUnifiedWorkspaceRequest(payload)).not.toThrow();
        }
    });

    it("rejects non-object payload", () => {
        expect(() => validateUnifiedWorkspaceRequest("not an object")).toThrow(ValidationError);
        expect(() => validateUnifiedWorkspaceRequest("not an object")).toThrow(/객체/);
    });
});

describe("checkFieldNames", () => {
    it("detects camelCase field names", () => {
        const payload = {
            ocrText: "sample",
            queryType: "explanation",
        };

        const warnings = checkFieldNames(payload);
        expect(warnings).toHaveLength(2);
        expect(warnings[0]).toContain("ocrText");
        expect(warnings[0]).toContain("ocr_text");
        expect(warnings[1]).toContain("queryType");
        expect(warnings[1]).toContain("query_type");
    });

    it("returns empty array for correct field names", () => {
        const payload = {
            ocr_text: "sample",
            query_type: "explanation",
        };

        const warnings = checkFieldNames(payload);
        expect(warnings).toHaveLength(0);
    });

    it("detects editRequest field", () => {
        const payload = {
            editRequest: "edit this",
        };

        const warnings = checkFieldNames(payload);
        expect(warnings).toHaveLength(1);
        expect(warnings[0]).toContain("editRequest");
        expect(warnings[0]).toContain("edit_request");
    });

    it("detects batchTypes field", () => {
        const payload = {
            batchTypes: ["explanation"],
        };

        const warnings = checkFieldNames(payload);
        expect(warnings).toHaveLength(1);
        expect(warnings[0]).toContain("batchTypes");
        expect(warnings[0]).toContain("batch_types");
    });

    it("detects globalExplanationRef field", () => {
        const payload = {
            globalExplanationRef: "reference",
        };

        const warnings = checkFieldNames(payload);
        expect(warnings).toHaveLength(1);
        expect(warnings[0]).toContain("globalExplanationRef");
        expect(warnings[0]).toContain("global_explanation_ref");
    });

    it("handles non-object input", () => {
        expect(checkFieldNames(null)).toEqual([]);
        expect(checkFieldNames(undefined)).toEqual([]);
        expect(checkFieldNames("string")).toEqual([]);
        expect(checkFieldNames(123)).toEqual([]);
    });
});

describe("validateRequest", () => {
    it("validates QA generate endpoint", () => {
        const payload = {
            mode: "single",
            ocr_text: "sample",
            qtype: "explanation",
        };

        expect(() => validateRequest(payload, "/api/qa/generate")).not.toThrow();
    });

    it("validates workspace endpoint", () => {
        const payload = {
            mode: "full",
            query: "test",
        };

        expect(() => validateRequest(payload, "/api/workspace/unified")).not.toThrow();
    });

    it("detects field name issues before validation", () => {
        const payload = {
            mode: "single",
            ocrText: "sample", // camelCase
            qtype: "explanation",
        };

        expect(() => validateRequest(payload, "/api/qa/generate")).toThrow(ValidationError);
        expect(() => validateRequest(payload, "/api/qa/generate")).toThrow(/ocrText/);
    });

    it("handles unknown endpoint gracefully", () => {
        const payload = { test: "data" };
        expect(() => validateRequest(payload, "/api/unknown")).not.toThrow();
    });
});

describe("parse422Error", () => {
    it("parses FastAPI validation error", () => {
        const errorData = {
            detail: [
                {
                    loc: ["body", "qtype"],
                    msg: "field required",
                    type: "value_error.missing",
                },
                {
                    loc: ["body", "mode"],
                    msg: "invalid value",
                    type: "value_error.const",
                },
            ],
        };

        const message = parse422Error(errorData);
        expect(message).toContain("qtype");
        expect(message).toContain("field required");
        expect(message).toContain("mode");
        expect(message).toContain("invalid value");
    });

    it("handles simple detail string", () => {
        const errorData = {
            detail: "Validation failed",
        };

        const message = parse422Error(errorData);
        expect(message).toBe("Validation failed");
    });

    it("handles missing detail", () => {
        const errorData = {};
        const message = parse422Error(errorData);
        expect(message).toContain("검증 실패");
    });

    it("handles null input", () => {
        const message = parse422Error(null);
        expect(message).toContain("검증 실패");
    });

    it("handles nested field locations", () => {
        const errorData = {
            detail: [
                {
                    loc: ["body", "batch_types", "0"],
                    msg: "not a valid string",
                },
            ],
        };

        const message = parse422Error(errorData);
        expect(message).toContain("batch_types.0");
        expect(message).toContain("not a valid string");
    });
});

describe("ValidationError", () => {
    it("creates error with field and message", () => {
        const error = new ValidationError("test_field", "test message");
        expect(error.field).toBe("test_field");
        expect(error.message).toBe("test_field: test message");
        expect(error.name).toBe("ValidationError");
    });

    it("is an instance of Error", () => {
        const error = new ValidationError("field", "message");
        expect(error).toBeInstanceOf(Error);
    });
});
