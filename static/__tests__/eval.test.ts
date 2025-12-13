/**
 * Tests for eval.ts module
 * @module static/__tests__/eval.test
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock dependencies
vi.mock("../utils.js", () => ({
    apiCall: vi.fn(),
    showToast: vi.fn(),
}));

vi.mock("../ocr.js", () => ({
    loadOCR: vi.fn(),
    saveOCR: vi.fn(),
}));

import { initEval } from "../eval";
import { apiCall, showToast } from "../utils.js";
import { loadOCR, saveOCR } from "../ocr.js";

describe("eval module", () => {
    let queryTextArea: HTMLTextAreaElement;
    let answerA: HTMLTextAreaElement;
    let answerB: HTMLTextAreaElement;
    let answerC: HTMLTextAreaElement;
    let evalBtn: HTMLButtonElement;
    let saveOcrBtn: HTMLButtonElement;
    let resultsDiv: HTMLDivElement;

    beforeEach(() => {
        // Set up DOM elements
        queryTextArea = document.createElement("textarea");
        queryTextArea.id = "query";
        document.body.appendChild(queryTextArea);

        answerA = document.createElement("textarea");
        answerA.id = "answer-a";
        document.body.appendChild(answerA);

        answerB = document.createElement("textarea");
        answerB.id = "answer-b";
        document.body.appendChild(answerB);

        answerC = document.createElement("textarea");
        answerC.id = "answer-c";
        document.body.appendChild(answerC);

        evalBtn = document.createElement("button");
        evalBtn.id = "eval-btn";
        document.body.appendChild(evalBtn);

        saveOcrBtn = document.createElement("button");
        saveOcrBtn.id = "save-ocr-btn";
        document.body.appendChild(saveOcrBtn);

        resultsDiv = document.createElement("div");
        resultsDiv.id = "eval-results";
        document.body.appendChild(resultsDiv);

        // Reset mocks
        vi.clearAllMocks();
    });

    afterEach(() => {
        document.body.innerHTML = "";
    });

    describe("initEval", () => {
        it("should call loadOCR on initialization", () => {
            initEval();
            expect(loadOCR).toHaveBeenCalled();
        });

        it("should attach click handler to save-ocr-btn", () => {
            initEval();
            saveOcrBtn.click();
            expect(saveOCR).toHaveBeenCalled();
        });

        it("should attach click handler to eval-btn", async () => {
            queryTextArea.value = "Test query";
            answerA.value = "Answer A";
            answerB.value = "Answer B";
            answerC.value = "Answer C";

            vi.mocked(apiCall).mockResolvedValue({
                best: "A",
                results: [
                    { candidate_id: "A", score: 90, feedback: "Good" },
                    { candidate_id: "B", score: 80, feedback: "OK" },
                    { candidate_id: "C", score: 70, feedback: "Fair" },
                ],
            });

            initEval();
            await evalBtn.click();

            // Wait for async operation
            await new Promise((resolve) => setTimeout(resolve, 10));

            expect(apiCall).toHaveBeenCalledWith("/api/eval/external", "POST", {
                query: "Test query",
                answers: ["Answer A", "Answer B", "Answer C"],
            });
        });

        it("should show error toast when fields are empty", async () => {
            queryTextArea.value = "";
            answerA.value = "";
            answerB.value = "";
            answerC.value = "";

            initEval();
            await evalBtn.click();

            expect(showToast).toHaveBeenCalledWith(
                "모든 필드를 입력해주세요.",
                "error"
            );
            expect(apiCall).not.toHaveBeenCalled();
        });
    });

    describe("evaluateAnswers (via initEval)", () => {
        beforeEach(() => {
            queryTextArea.value = "Test query";
            answerA.value = "Answer A";
            answerB.value = "Answer B";
            answerC.value = "Answer C";
        });

        it("should display loading indicator during evaluation", async () => {
            vi.mocked(apiCall).mockImplementation(
                () =>
                    new Promise((resolve) =>
                        setTimeout(
                            () =>
                                resolve({
                                    best: "A",
                                    results: [],
                                }),
                            100
                        )
                    )
            );

            initEval();
            evalBtn.click();

            // Check loading state
            await new Promise((resolve) => setTimeout(resolve, 10));
            expect(resultsDiv.querySelector(".loading")).toBeTruthy();
        });

        it("should display evaluation results table", async () => {
            vi.mocked(apiCall).mockResolvedValue({
                best: "A",
                results: [
                    { candidate_id: "A", score: 95, feedback: "Excellent" },
                    { candidate_id: "B", score: 85, feedback: "Good" },
                    { candidate_id: "C", score: 75, feedback: "Average" },
                ],
            });

            initEval();
            await evalBtn.click();
            await new Promise((resolve) => setTimeout(resolve, 10));

            expect(resultsDiv.querySelector("table")).toBeTruthy();
            expect(resultsDiv.querySelector("thead")).toBeTruthy();
            expect(resultsDiv.querySelector("tbody")).toBeTruthy();
        });

        it("should highlight best answer with special class", async () => {
            vi.mocked(apiCall).mockResolvedValue({
                best: "B",
                results: [
                    { candidate_id: "A", score: 80, feedback: "Good" },
                    { candidate_id: "B", score: 95, feedback: "Best" },
                    { candidate_id: "C", score: 70, feedback: "OK" },
                ],
            });

            initEval();
            await evalBtn.click();
            await new Promise((resolve) => setTimeout(resolve, 10));

            const bestRow = resultsDiv.querySelector(".best-answer");
            expect(bestRow).toBeTruthy();
            expect(bestRow?.textContent).toContain("B");
            expect(bestRow?.textContent).toContain("⭐");
        });

        it("should display error message when API fails", async () => {
            vi.mocked(apiCall).mockRejectedValue(new Error("API Error"));

            initEval();
            await evalBtn.click();
            await new Promise((resolve) => setTimeout(resolve, 10));

            const errorMsg = resultsDiv.querySelector(".eval-error-message");
            expect(errorMsg).toBeTruthy();
            expect(errorMsg?.textContent).toContain("평가 실패");
        });
    });
});
