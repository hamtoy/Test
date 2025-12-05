import { apiCall, copyToClipboard, showToast } from "./utils.js";
import { loadOCR, saveOCR } from "./ocr.js";

const GLOBAL_EXPLANATION_KEY = "workspace_global_explanation";

interface WorkspaceMode {
    current: "full" | "query-only" | "answer-only";
    switchTo(mode: string): void;
    updateValidation(): void;
}

interface WorkspaceResult {
    workflow: string;
    query?: string;
    answer?: string;
}

interface WorkspacePayload {
    mode: string;
    query: string | null;
    answer: string | null;
    edit_request: string | null;
    ocr_text: string | null;
    query_type: string | null;
    global_explanation_ref: string | null;
}

const WorkspaceMode: WorkspaceMode = {
    current: "full",
    switchTo(mode: string) {
        this.current = mode as "full" | "query-only" | "answer-only";
        const queryField = document.getElementById("query") as HTMLTextAreaElement;
        const answerField = document.getElementById("answer") as HTMLTextAreaElement;
        const queryBadge = document.getElementById("query-badge") as HTMLElement;
        const answerBadge = document.getElementById("answer-badge") as HTMLElement;
        const queryHelp = document.getElementById("query-help") as HTMLElement;
        const answerHelp = document.getElementById("answer-help") as HTMLElement;
        const queryTypeSection = document.getElementById("query-type-section") as HTMLElement;
        const executeBtn = document.getElementById("execute-btn") as HTMLButtonElement;

        queryField.readOnly = false;
        answerField.readOnly = false;
        queryField.classList.remove("output-only", "required-input");
        answerField.classList.remove("output-only", "required-input");

        if (mode === "full") {
            queryBadge.textContent = "선택";
            queryBadge.className = "field-badge optional";
            answerBadge.textContent = "선택";
            answerBadge.className = "field-badge optional";
            queryHelp.textContent = "💡 비워두면 자동으로 생성됩니다";
            answerHelp.textContent = "💡 비워두면 자동으로 생성됩니다";
            queryField.placeholder = "질문을 입력하세요 (비우면 자동 생성)";
            answerField.placeholder = "답변을 입력하세요 (비우면 자동 생성)";
            queryTypeSection.style.display = "block";
            executeBtn.textContent = "🚀 실행";
        } else if (mode === "query-only") {
            queryBadge.textContent = "자동 생성";
            queryBadge.className = "field-badge output";
            answerBadge.textContent = "필수 입력";
            answerBadge.className = "field-badge required";
            queryHelp.innerHTML = "🤖 <strong>답변 기반으로 자동 생성됩니다</strong>";
            answerHelp.innerHTML = "✅ <strong>답변을 입력하세요</strong> (이 내용으로 질문 생성)";
            queryField.placeholder = "여기에 생성된 질문이 표시됩니다";
            answerField.placeholder = "질문을 생성할 답변을 입력하세요";
            queryField.readOnly = true;
            queryField.classList.add("output-only");
            answerField.classList.add("required-input");
            queryTypeSection.style.display = "none";
            executeBtn.textContent = "❓ 질문 생성";
        } else if (mode === "answer-only") {
            queryBadge.textContent = "필수 입력";
            queryBadge.className = "field-badge required";
            answerBadge.textContent = "자동 생성";
            answerBadge.className = "field-badge output";
            queryHelp.innerHTML = "✅ <strong>질문을 입력하세요</strong> (이 내용으로 답변 생성)";
            answerHelp.innerHTML = "🤖 <strong>질문 기반으로 자동 생성됩니다</strong>";
            queryField.placeholder = "답변을 생성할 질문을 입력하세요";
            answerField.placeholder = "여기에 생성된 답변이 표시됩니다";
            answerField.readOnly = true;
            answerField.classList.add("output-only");
            queryField.classList.add("required-input");
            queryTypeSection.style.display = "block";
            executeBtn.textContent = "💡 답변 생성";
        }

        this.updateValidation();
    },
    updateValidation() {
        const queryVal = (document.getElementById("query") as HTMLTextAreaElement).value.trim();
        const answerVal = (document.getElementById("answer") as HTMLTextAreaElement).value.trim();
        const ocrVal = (document.getElementById("ocr-input") as HTMLTextAreaElement).value.trim();
        const globalRefVal = (document.getElementById("global-explanation-ref") as HTMLTextAreaElement).value.trim();
        const executeBtn = document.getElementById("execute-btn") as HTMLButtonElement;

        let isValid = false;
        if (this.current === "query-only") {
            isValid = Boolean(answerVal || ocrVal);
        } else if (this.current === "answer-only") {
            isValid = Boolean(queryVal);
        } else {
            isValid = Boolean(ocrVal || globalRefVal || queryVal || answerVal);
        }

        executeBtn.disabled = !isValid;
        executeBtn.style.opacity = isValid ? "1" : "0.6";
    },
};

function setButtonLoading(button: HTMLButtonElement | null, isLoading: boolean): void {
    if (!button) return;
    button.disabled = isLoading;
    button.setAttribute("aria-busy", String(isLoading));
    if (isLoading) {
        button.dataset.originalText =
            button.dataset.originalText || button.textContent || "";
        button.setAttribute("aria-label", "처리 중입니다. 잠시만 기다려주세요.");
        button.textContent = "⏳ 처리 중...";
        button.style.opacity = "0.6";
    } else {
        button.textContent = button.dataset.originalText || button.textContent;
        button.setAttribute("aria-label", "실행");
        button.style.opacity = "1";
        button.removeAttribute("aria-busy");
    }
}

function handleResultHighlight(field: HTMLElement): void {
    field.style.borderColor = "var(--primary, #21808d)";
    field.style.boxShadow = "0 0 0 3px rgba(33, 128, 141, 0.2)";
    setTimeout(() => {
        field.style.borderColor = "";
        field.style.boxShadow = "";
    }, 2000);
}

function getWorkflowLabel(workflow: string): string {
    const labels: Record<string, string> = {
        full_generation: "🎯 전체 생성",
        query_generation: "❓ 질의 생성",
        answer_generation: "💡 답변 생성",
        edit_query: "✏️ 질의 수정",
        edit_answer: "✏️ 답변 수정",
        edit_both: "✏️ 질의+답변 수정",
        rewrite: "✅ 재작성/검수",
    };
    return labels[workflow] || workflow;
}

function displayResult(data: WorkspaceResult): void {
    const currentMode = WorkspaceMode.current;
    const canUpdateQuery = [
        "full_generation",
        "query_generation",
        "edit_query",
        "edit_both",
    ].includes(data.workflow);

    if (data.query && currentMode !== "answer-only" && canUpdateQuery) {
        const queryField = document.getElementById("query") as HTMLTextAreaElement;
        queryField.value = data.query;
        handleResultHighlight(queryField);
    }

    if (data.answer) {
        const answerField = document.getElementById("answer") as HTMLTextAreaElement;
        answerField.value = data.answer;
        handleResultHighlight(answerField);
    }

    const resultsDiv = document.getElementById("workspace-results");
    if (!resultsDiv) return;
    resultsDiv.innerHTML = `
        <div style="text-align: center; padding: 20px; background: #e8f5e9; border-radius: 8px; border: 1px solid #4caf50; margin-top: 20px; animation: fadeIn 0.3s;">
            <h3 style="margin: 0 0 10px 0; color: #4caf50;">✅ ${getWorkflowLabel(data.workflow)} 완료</h3>
            <p style="margin: 0; color: #666; font-size: 0.9em;">
                ${data.query ? "질의" : ""}${data.query && data.answer ? "와 " : ""}${data.answer ? "답변" : ""}이 입력 필드에 자동으로 채워졌습니다.
            </p>
        </div>
    `;

    setTimeout(() => {
        resultsDiv.innerHTML = "";
    }, 3000);
}

function copyFieldContent(fieldId: string, buttonEl: HTMLElement): void {
    const field = document.getElementById(fieldId) as HTMLTextAreaElement;
    const text = field.value.trim();
    if (!text) {
        showToast("복사할 내용이 없습니다.", "error");
        return;
    }
    copyToClipboard(text, buttonEl);
}

function restoreSession(): void {
    const savedQuery = sessionStorage.getItem("workspace_query");
    const savedAnswer = sessionStorage.getItem("workspace_answer");
    if (savedQuery) {
        (document.getElementById("query") as HTMLTextAreaElement).value = savedQuery;
        sessionStorage.removeItem("workspace_query");
    }
    if (savedAnswer) {
        (document.getElementById("answer") as HTMLTextAreaElement).value = savedAnswer;
        sessionStorage.removeItem("workspace_answer");
    }
}

function restoreReference(): void {
    const savedRef = localStorage.getItem(GLOBAL_EXPLANATION_KEY);
    if (savedRef) {
        (document.getElementById("global-explanation-ref") as HTMLTextAreaElement).value = savedRef;
    }
}

function setupReferenceAutoSave(): void {
    let saveRefTimeout: number; // Browser setTimeout returns number
    const refElement = document.getElementById("global-explanation-ref") as HTMLTextAreaElement;
    refElement.addEventListener("input", (e) => {
        clearTimeout(saveRefTimeout);
        const value = (e.target as HTMLTextAreaElement).value;
        saveRefTimeout = setTimeout(() => {
            localStorage.setItem(GLOBAL_EXPLANATION_KEY, value);
        }, 300);
    });

    document.getElementById("clear-reference-btn")?.addEventListener("click", () => {
        refElement.value = "";
        localStorage.removeItem(GLOBAL_EXPLANATION_KEY);
    });
}

function setupTabs(): void {
    const tabs = document.querySelectorAll(".workspace-mode-tabs .mode-tab");
    tabs.forEach((btn) => {
        const htmlBtn = btn as HTMLElement;
        htmlBtn.addEventListener("click", () => {
            tabs.forEach((b) => b.classList.remove("active"));
            htmlBtn.classList.add("active");
            if (htmlBtn.dataset.mode) {
                WorkspaceMode.switchTo(htmlBtn.dataset.mode);
            }
        });

        // 키보드 네비게이션
        htmlBtn.addEventListener("keydown", (e: KeyboardEvent) => {
            const index = Array.from(tabs).indexOf(htmlBtn);
            let newIndex = index;
            if (e.key === "ArrowRight") newIndex = (index + 1) % tabs.length;
            if (e.key === "ArrowLeft")
                newIndex = (index - 1 + tabs.length) % tabs.length;
            if (e.key === "Home") newIndex = 0;
            if (e.key === "End") newIndex = tabs.length - 1;
            if (newIndex !== index) {
                e.preventDefault();
                (tabs[newIndex] as HTMLElement).click();
                (tabs[newIndex] as HTMLElement).focus();
            }
        });
    });
}

function setupValidationInputs(): void {
    let validationTimeout: number;
    const debouncedValidation = () => {
        clearTimeout(validationTimeout);
        validationTimeout = setTimeout(() => WorkspaceMode.updateValidation(), 150);
    };

    ["query", "answer", "ocr-input", "global-explanation-ref"].forEach((id) => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener("input", debouncedValidation);
        }
    });
}

async function executeWorkspace(
    mode: string,
    query: string | null,
    answer: string | null,
    editRequest: string | null,
    signal: AbortSignal
): Promise<void> {
    const resultsDiv = document.getElementById("workspace-results");
    if (!resultsDiv) return;
    resultsDiv.innerHTML = `
        <div style="text-align: center; padding: 20px; background: var(--bg-secondary, #f5f5f5); border-radius: 8px; margin-top: 20px;">
            <p style="color: var(--text-primary, #1f2121); margin: 0;">⏳ 처리 중...</p>
        </div>
    `;

    const body: WorkspacePayload = {
        mode,
        query: query || null,
        answer: answer || null,
        edit_request: editRequest || null,
        ocr_text: (document.getElementById("ocr-input") as HTMLTextAreaElement).value || null,
        query_type: (document.getElementById("query-type") as HTMLSelectElement).value || null,
        global_explanation_ref:
            (document.getElementById("global-explanation-ref") as HTMLTextAreaElement).value.trim() || null,
    };

    if (mode === "query-only" && !editRequest) {
        body.query = null;
    } else if (mode === "answer-only" && !editRequest) {
        body.answer = null;
    }

    const result = await apiCall("/api/workspace/unified", "POST", body, signal);
    displayResult(result);
}

export function initWorkspace(): void {
    loadOCR();
    document.getElementById("save-ocr-btn")?.addEventListener("click", () => saveOCR());
    restoreSession();
    restoreReference();
    setupReferenceAutoSave();
    setupTabs();
    setupValidationInputs();
    WorkspaceMode.switchTo("full");

    // 복사 버튼들
    document.querySelectorAll("[data-copy-target]").forEach((btn) => {
        const htmlBtn = btn as HTMLElement;
        htmlBtn.addEventListener("click", () => {
            if (htmlBtn.dataset.copyTarget) {
                copyFieldContent(htmlBtn.dataset.copyTarget, htmlBtn);
            }
        });
    });

    let isExecuting = false;
    let abortController: AbortController | null = null;

    document.getElementById("execute-btn")?.addEventListener("click", async () => {
        if (isExecuting) return;
        if (abortController) abortController.abort();
        abortController = new AbortController();
        const executeBtn = document.getElementById("execute-btn") as HTMLButtonElement;
        isExecuting = true;
        setButtonLoading(executeBtn, true);

        const query = (document.getElementById("query") as HTMLTextAreaElement).value.trim();
        const answer = (document.getElementById("answer") as HTMLTextAreaElement).value.trim();
        const editRequest = (document.getElementById("edit-request") as HTMLTextAreaElement).value.trim();

        try {
            await executeWorkspace(
                WorkspaceMode.current,
                query,
                answer,
                editRequest,
                abortController.signal,
            );
        } catch (error: any) {
            const resultsDiv = document.getElementById("workspace-results");
            if (resultsDiv) {
                resultsDiv.innerHTML = `
                    <div style="text-align: center; padding: 20px; background: #ffebee; border-radius: 8px; border: 1px solid #f44336; margin-top: 20px;">
                        <p style="color: #f44336; margin: 0;">❌ 작업 실패: ${error.message}</p>
                    </div>
                `;
            }
        } finally {
            isExecuting = false;
            setButtonLoading(executeBtn, false);
        }
    });
}
