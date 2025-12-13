import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../ocr.js", () => ({
    loadOCR: vi.fn(),
    saveOCR: vi.fn(),
}));

const showToastMock = vi.fn();

vi.mock("../utils.js", async () => {
    const actual = await vi.importActual<typeof import("../utils.js")>("../utils.js");
    return {
        ...actual,
        showToast: showToastMock,
        apiCallWithRetry: vi.fn(),
        copyToClipboard: vi.fn(),
        createRipple: vi.fn(),
    };
});

describe("static/workspace.ts", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        localStorage.clear();
        sessionStorage.clear();
        document.body.innerHTML = `
            <div class="workspace-mode-tabs">
                <button class="mode-tab active" data-mode="full">full</button>
                <button class="mode-tab" data-mode="query-only">query-only</button>
                <button class="mode-tab" data-mode="answer-only">answer-only</button>
            </div>
            <textarea id="ocr-input"></textarea>
            <textarea id="global-explanation-ref"></textarea>
            <button id="clear-reference-btn"></button>

            <div id="query-type-section" style="display: block;"></div>
            <select id="query-type"><option value="global_explanation">global_explanation</option></select>

            <span id="query-badge"></span>
            <span id="answer-badge"></span>
            <div id="query-help"></div>
            <div id="answer-help"></div>

            <textarea id="query"></textarea>
            <textarea id="answer"></textarea>
            <textarea id="edit-request"></textarea>
            <button id="execute-btn"></button>

            <div id="workspace-results"></div>
            <button id="save-ocr-btn"></button>
        `;
    });

    it("disables execute button in full mode until input exists", async () => {
        vi.useFakeTimers();

        const { initWorkspace } = await import("../workspace.js");
        initWorkspace();

        const executeBtn = document.getElementById("execute-btn") as HTMLButtonElement;
        expect(executeBtn.disabled).toBe(true);

        (document.getElementById("ocr-input") as HTMLTextAreaElement).value = "OCR";
        document.getElementById("ocr-input")!.dispatchEvent(
            new Event("input", { bubbles: true }),
        );

        await vi.advanceTimersByTimeAsync(200);
        expect(executeBtn.disabled).toBe(false);

        vi.useRealTimers();
    });

    it("switches to query-only mode and enforces required fields", async () => {
        vi.useFakeTimers();

        const { initWorkspace } = await import("../workspace.js");
        initWorkspace();

        const queryOnlyTab = document.querySelector<HTMLElement>(
            ".mode-tab[data-mode=\"query-only\"]",
        )!;
        queryOnlyTab.click();

        const queryField = document.getElementById("query") as HTMLTextAreaElement;
        const answerField = document.getElementById("answer") as HTMLTextAreaElement;
        const queryTypeSection = document.getElementById("query-type-section") as HTMLElement;
        const executeBtn = document.getElementById("execute-btn") as HTMLButtonElement;

        expect(queryField.readOnly).toBe(true);
        expect(queryField.classList.contains("output-only")).toBe(true);
        expect(answerField.classList.contains("required-input")).toBe(true);
        expect(queryTypeSection.style.display).toBe("none");
        expect(executeBtn.textContent).toBe("❓ 질문 생성");

        // Validation: query-only allows answer or OCR
        expect(executeBtn.disabled).toBe(true);
        answerField.value = "Answer";
        answerField.dispatchEvent(new Event("input", { bubbles: true }));
        await vi.advanceTimersByTimeAsync(200);
        expect(executeBtn.disabled).toBe(false);

        vi.useRealTimers();
    });
});

