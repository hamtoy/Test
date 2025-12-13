import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../ocr.js", () => ({
    loadOCR: vi.fn(),
    saveOCR: vi.fn(),
}));

vi.mock("../validation.js", () => ({
    validateRequest: vi.fn(),
    ValidationError: class ValidationError extends Error {},
}));

const apiCallMock = vi.fn();
const showToastMock = vi.fn();
const showProgressMock = vi.fn();
const withRetryMock = vi.fn();

vi.mock("../utils.js", async () => {
    const actual = await vi.importActual<typeof import("../utils.js")>("../utils.js");
    return {
        ...actual,
        apiCall: apiCallMock,
        showToast: showToastMock,
        showProgressWithEstimate: showProgressMock,
        withRetry: withRetryMock,
    };
});

describe("static/qa.ts", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        document.body.innerHTML = `
            <div id="type-selector" style="display: block;"></div>
            <textarea id="ocr-input"></textarea>
            <select id="qtype">
                <option value="global_explanation" selected>global_explanation</option>
            </select>
            <div id="results"></div>
            <button id="generate-btn"></button>
            <button id="save-ocr-btn"></button>
            <label><input type="radio" name="mode" value="single" checked /></label>
            <label><input type="radio" name="mode" value="batch" /></label>
        `;
        // @ts-expect-error - test-only clipboard mock
        navigator.clipboard = { writeText: vi.fn().mockResolvedValue(undefined) };
    });

    it("toggles type selector on mode change", async () => {
        const { initQA } = await import("../qa.js");

        initQA();

        const typeSelector = document.getElementById("type-selector") as HTMLElement;
        const batchRadio = document.querySelector<HTMLInputElement>(
            "input[name=\"mode\"][value=\"batch\"]",
        )!;
        const singleRadio = document.querySelector<HTMLInputElement>(
            "input[name=\"mode\"][value=\"single\"]",
        )!;

        batchRadio.checked = true;
        batchRadio.dispatchEvent(new Event("change", { bubbles: true }));
        expect(typeSelector.style.display).toBe("none");

        singleRadio.checked = true;
        singleRadio.dispatchEvent(new Event("change", { bubbles: true }));
        expect(typeSelector.style.display).toBe("block");
    });

    it("generates QA in single mode and renders results", async () => {
        vi.useFakeTimers();

        showProgressMock.mockReturnValue(vi.fn());
        withRetryMock.mockImplementation(async (fn: () => Promise<unknown>) => fn());
        apiCallMock.mockResolvedValue({
            success: true,
            data: {
                pairs: [
                    {
                        type: "global_explanation",
                        query: "Q1",
                        answer: "A1",
                    },
                ],
            },
        });

        const { initQA } = await import("../qa.js");
        initQA();

        (document.getElementById("ocr-input") as HTMLTextAreaElement).value = "OCR";
        (document.getElementById("generate-btn") as HTMLButtonElement).click();

        await vi.runAllTimersAsync();
        await Promise.resolve();

        const results = document.getElementById("results")!;
        expect(results.querySelectorAll(".qa-card")).toHaveLength(1);
        expect(results.querySelector(".qa-type-badge")?.textContent).toContain("전반 설명");

        vi.useRealTimers();
    });
});

