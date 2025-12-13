/**
 * Tests for ocr.ts module
 * @module static/__tests__/ocr.test
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock the utils module
vi.mock("../utils.js", () => ({
    apiCall: vi.fn(),
    showToast: vi.fn(),
}));

import { loadOCR, saveOCR } from "../ocr";
import { apiCall, showToast } from "../utils.js";

describe("ocr module", () => {
    let mockTextArea: HTMLTextAreaElement;
    let mockDiv: HTMLDivElement;
    let mockStatusEl: HTMLSpanElement;

    beforeEach(() => {
        // Set up DOM elements
        mockTextArea = document.createElement("textarea");
        mockTextArea.id = "ocr-input";
        document.body.appendChild(mockTextArea);

        mockDiv = document.createElement("div");
        mockDiv.id = "ocr-preview";
        document.body.appendChild(mockDiv);

        mockStatusEl = document.createElement("span");
        mockStatusEl.id = "ocr-save-status";
        document.body.appendChild(mockStatusEl);

        // Reset mocks
        vi.clearAllMocks();
    });

    afterEach(() => {
        // Clean up DOM
        document.body.innerHTML = "";
    });

    describe("loadOCR", () => {
        it("should load OCR text into textarea when data exists", async () => {
            const mockOcrText = "This is test OCR content";
            vi.mocked(apiCall).mockResolvedValue({ ocr: mockOcrText });

            await loadOCR("ocr-input");

            expect(apiCall).toHaveBeenCalledWith("/api/ocr");
            expect(mockTextArea.value).toBe(mockOcrText);
        });

        it("should set placeholder when no OCR data exists", async () => {
            vi.mocked(apiCall).mockResolvedValue({ ocr: "" });

            await loadOCR("ocr-input");

            expect(mockTextArea.value).toBe("");
            expect(mockTextArea.placeholder).toContain("OCR 파일이 없습니다");
        });

        it("should handle div elements differently than textareas", async () => {
            const mockOcrText = "Div OCR content";
            vi.mocked(apiCall).mockResolvedValue({ ocr: mockOcrText });

            // Remove textarea and use div as target
            mockTextArea.remove();
            mockDiv.id = "ocr-input";

            await loadOCR("ocr-input");

            expect(mockDiv.textContent).toBe(mockOcrText);
        });

        it("should show error toast when API call fails", async () => {
            const errorMessage = "Network error";
            vi.mocked(apiCall).mockRejectedValue(new Error(errorMessage));

            await loadOCR("ocr-input");

            expect(showToast).toHaveBeenCalledWith(
                expect.stringContaining("OCR 로드 실패"),
                "error"
            );
        });

        it("should handle non-existent element gracefully", async () => {
            const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => { });

            await loadOCR("non-existent-id");

            expect(consoleSpy).toHaveBeenCalledWith("OCR element not found");
            consoleSpy.mockRestore();
        });

        it("should fallback to ocr-preview when target not found", async () => {
            vi.mocked(apiCall).mockResolvedValue({ ocr: "Fallback content" });

            // Keep ocr-preview but remove ocr-input
            mockTextArea.remove();

            await loadOCR("ocr-input");

            expect(mockDiv.textContent).toBe("Fallback content");
        });
    });

    describe("saveOCR", () => {
        it("should save OCR text via API", async () => {
            mockTextArea.value = "Text to save";
            vi.mocked(apiCall).mockResolvedValue({ status: "success" });

            await saveOCR("ocr-input", "ocr-save-status");

            expect(apiCall).toHaveBeenCalledWith("/api/ocr", "POST", {
                text: "Text to save",
            });
        });

        it("should show success status after saving", async () => {
            mockTextArea.value = "Text to save";
            vi.mocked(apiCall).mockResolvedValue({ status: "success" });

            await saveOCR("ocr-input", "ocr-save-status");

            expect(mockStatusEl.textContent).toContain("저장됨");
            expect(mockStatusEl.className).toContain("success");
        });

        it("should show error status when save fails", async () => {
            mockTextArea.value = "Text to save";
            vi.mocked(apiCall).mockRejectedValue(new Error("Save failed"));

            await saveOCR("ocr-input", "ocr-save-status");

            expect(mockStatusEl.textContent).toContain("저장 실패");
            expect(mockStatusEl.className).toContain("error");
        });

        it("should handle missing source element gracefully", async () => {
            const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => { });
            mockTextArea.remove();

            await saveOCR("missing-element", "ocr-save-status");

            expect(consoleSpy).toHaveBeenCalledWith("OCR source not found");
            consoleSpy.mockRestore();
        });

        it("should show toast when status element is missing", async () => {
            mockStatusEl.remove();
            mockTextArea.value = "Text to save";
            vi.mocked(apiCall).mockRejectedValue(new Error("Custom error"));

            await saveOCR("ocr-input", "missing-status");

            expect(showToast).toHaveBeenCalledWith(
                expect.stringContaining("OCR 저장 실패"),
                "error"
            );
        });
    });
});
