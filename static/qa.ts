import { apiCall, showToast, showProgressWithEstimate, withRetry } from "./utils.js";
import { loadOCR, saveOCR } from "./ocr.js";
import { validateRequest, ValidationError } from "./validation.js";

declare global {
    interface Window {
        DOMPurify: {
            sanitize: (text: string) => string;
        };
    }
}

interface QAPair {
    type: string;
    query: string;
    answer: string;
}

interface QAData {
    success?: boolean;
    data?: {
        pairs?: QAPair[];
        pair?: QAPair;
    };
    pairs?: QAPair[]; // flatten access
    pair?: QAPair;
}

let activeController: AbortController | null = null;

function getModeLabels(mode: string): { title: string; eta: string } {
    if (mode === "batch") {
        return { title: "⚡ 4개 타입 동시 생성 중...", eta: "30초~2분" };
    }
    if (mode === "batch_three") {
        return { title: "⚡ 3개 타입 동시 생성 중...", eta: "20초~90초" };
    }
    return { title: "🚀 답변 생성 중...", eta: "15초~1분" };
}

function renderProgress(mode: string): string {
    const { title, eta } = getModeLabels(mode);
    return `
        <div class="progress-container" style="text-align: center; padding: 40px 20px; background: var(--bg-secondary, #f5f5f5); border-radius: 8px;">
            <h3 style="margin-bottom: 20px; color: var(--text-primary, #333);">${title}</h3>
            <div style="margin: 25px auto; width: 320px; height: 10px; background: #e0e0e0; border-radius: 5px; overflow: hidden; box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);">
                <div class="progress-fill" style="width: 0%; height: 100%; background: linear-gradient(90deg, var(--primary, #21808d) 0%, var(--primary-dark, #1a6673) 100%); transition: width 0.5s ease;"></div>
            </div>
            <p style="color: var(--text-secondary, #666); font-size: 0.95em; margin-top: 20px; font-weight: 500;">예상 소요 시간: <strong>${eta}</strong></p>
            <p style="color: var(--text-secondary, #666); font-size: 0.85em; margin-top: 8px;">병렬 처리로 빠르게 완료됩니다 ✨</p>
        </div>
    `;
}

function escapeHtml(text: string): string {
    const div = document.createElement("div");
    div.textContent = text || "";
    return div.innerHTML;
}

function formatAnswer(text: string): string {
    // 마크다운 렌더링 없이 raw 텍스트로 표시 (워크스페이스와 동일)
    const escaped = escapeHtml(text);
    const formatted = escaped
        .replaceAll("\n\n", "<br><br>")  // 문단 구분
        .replaceAll("\n", "<br>")         // 일반 줄바꿈
        .replaceAll(" - ", "<br><br>- "); // 불릿 포인트 앞에 줄바꿈 추가
    return window.DOMPurify ? window.DOMPurify.sanitize(formatted) : formatted;
}

function getTypeBadge(type: string): string {
    const badges: Record<string, string> = {
        explanation: "🌍 전반 설명",
        global_explanation: "🌍 전반 설명",
        reasoning: "🧠 추론",
        target_short: "🎯 타겟 단답",
        target_long: "📝 타겟 장답",
    };
    return badges[type] || type;
}

function copyToWorkspace(query: string, answer: string): void {
    sessionStorage.setItem("workspace_query", query);
    sessionStorage.setItem("workspace_answer", answer);
    window.location.href = "/workspace";
}

function isQAPair(value: unknown): value is QAPair {
    if (!value || typeof value !== "object") return false;
    const candidate = value as Record<string, unknown>;
    return (
        typeof candidate.type === "string" &&
        typeof candidate.query === "string" &&
        typeof candidate.answer === "string"
    );
}

function extractPairs(raw: unknown): QAPair[] {
    if (!raw || typeof raw !== "object") return [];

    const payload = raw as QAData;
    const candidates: unknown[] = [];

    if (payload.pairs) candidates.push(...payload.pairs);
    if (payload.pair) candidates.push(payload.pair);
    if (payload.data?.pairs) candidates.push(...payload.data.pairs);
    if (payload.data?.pair) candidates.push(payload.data.pair);

    return candidates.filter(isQAPair);
}

function displayResults(raw: unknown): void {
    let pairs = extractPairs(raw);
    const resultsDiv = document.getElementById("results");
    if (!resultsDiv) return;
    resultsDiv.setAttribute("role", "status");
    resultsDiv.setAttribute("aria-live", "polite");
    resultsDiv.innerHTML = "";

    const selectedMode = (document.querySelector("input[name=\"mode\"]:checked") as HTMLInputElement)?.value;
    if (selectedMode === "batch_three") {
        const allowed = new Set(["global_explanation", "reasoning", "target_long"]);
        pairs = pairs.filter((p) => allowed.has(p.type));
    }
    if (!pairs.length) {
        const emptyCard = document.createElement("div");
        emptyCard.className = "qa-card";
        const emptyText = document.createElement("p");
        emptyText.className = "qa-empty-message";
        emptyText.textContent = "결과가 없습니다.";
        emptyCard.appendChild(emptyText);
        resultsDiv.appendChild(emptyCard);
        return;
    }

    pairs.forEach((item, index) => {
        const card = document.createElement("div");
        card.className = "qa-card";
        card.style.animation = `slideIn 0.3s ease-out ${index * 0.05}s both`;

        // Header with type badge
        const header = document.createElement("div");
        header.className = "qa-header";
        const badge = document.createElement("span");
        badge.className = "qa-type-badge";
        badge.textContent = getTypeBadge(item.type);
        header.appendChild(badge);
        card.appendChild(header);

        // Query section
        const querySection = document.createElement("div");
        querySection.className = "qa-section";
        const queryLabel = document.createElement("strong");
        queryLabel.textContent = "💬 질의";
        const queryContent = document.createElement("div");
        queryContent.className = "qa-content";
        queryContent.textContent = item.query;
        querySection.appendChild(queryLabel);
        querySection.appendChild(queryContent);
        card.appendChild(querySection);

        // Answer section
        const answerSection = document.createElement("div");
        answerSection.className = "qa-section";
        const answerLabel = document.createElement("strong");
        answerLabel.textContent = "✨ 답변";
        const answerContent = document.createElement("div");
        answerContent.className = "qa-content";
        // Use innerHTML with sanitized content for answer formatting
        answerContent.innerHTML = formatAnswer(item.answer);
        answerSection.appendChild(answerLabel);
        answerSection.appendChild(answerContent);
        card.appendChild(answerSection);

        // Button row
        const btnRow = document.createElement("div");
        btnRow.className = "btn-row qa-btn-row";
        const copyBtn = document.createElement("button");
        copyBtn.className = "btn-small qa-copy-btn";
        copyBtn.textContent = "📝 워크스페이스로 복사";
        copyBtn.addEventListener("click", () => {
            copyToWorkspace(item.query || "", item.answer || "");
        });
        btnRow.appendChild(copyBtn);
        card.appendChild(btnRow);

        resultsDiv.appendChild(card);
    });
}

type GenerateMode = "single" | "batch" | "batch_three";

interface GeneratePayload {
    mode: "single" | "batch";
    ocr_text: string;
    qtype?: string;
    batch_types?: string[];
}

async function generateQA(mode: GenerateMode, qtype: string | null): Promise<void> {
    const resultsDiv = document.getElementById("results");
    if (!resultsDiv) return;
    const ocrInput = document.getElementById("ocr-input") as HTMLTextAreaElement;
    const ocrText = ocrInput.value;

    if (!ocrText.trim()) {
        showToast("OCR 텍스트를 먼저 입력하세요.", "error");
        return;
    }

    resultsDiv.innerHTML = renderProgress(mode);
    const stopProgress = showProgressWithEstimate(mode === "batch" || mode === "batch_three" ? "batch" : "single");
    const progressBar = document.querySelector(".progress-fill") as HTMLElement;

    try {
        const payload: GeneratePayload =
            mode === "single"
                ? {
                    mode: "single",
                    ocr_text: ocrText,
                    qtype: qtype || "global_explanation",
                }
                : {
                    mode: "batch",
                    ocr_text: ocrText,
                };

        if (mode === "batch_three") {
            payload.batch_types = [
                "global_explanation",
                "reasoning",
                "target_long",
            ];
        }

        // Validate request payload before sending
        try {
            validateRequest(payload, "/api/qa/generate");
        } catch (validationError) {
            if (validationError instanceof ValidationError) {
                showToast(`요청 검증 실패: ${validationError.message}`, "error");
                stopProgress();
                resultsDiv.innerHTML = `
                    <div style="text-align: center; padding: 30px; background: #ffebee; border-radius: 8px; border: 1px solid #f44336; margin-top: 20px;">
                        <h3 style="color: #f44336; margin-bottom: 10px;">⚠️ 요청 데이터 오류</h3>
                        <p style="color: #666; margin: 0; white-space: pre-line;">${validationError.message}</p>
                        <p style="color: #999; margin-top: 15px; font-size: 0.9em;">💡 필드명과 데이터 타입을 확인하세요</p>
                    </div>
                `;
                return;
            }
            throw validationError;
        }

        if (activeController) {
            activeController.abort();
        }
        activeController = new AbortController();
        const result = await withRetry(
            () => apiCall<QAData>("/api/qa/generate", "POST", payload, activeController!.signal),
            2,
            800,
        );
        activeController = null;
        stopProgress();
        if (progressBar) progressBar.style.width = "100%";
        await new Promise((resolve) => setTimeout(resolve, 300));
        displayResults(result);
    } catch (error: unknown) {
        activeController = null;
        stopProgress();
        const message =
            error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다.";
        resultsDiv.innerHTML = `
            <div style="text-align: center; padding: 30px; background: #ffebee; border-radius: 8px; border: 1px solid #f44336; margin-top: 20px;">
                <h3 style="color: #f44336; margin-bottom: 10px;">❌ 생성 실패</h3>
                <p style="color: #666; margin: 0;">${message}</p>
            </div>
        `;
    }
}

// Streaming helpers
function createSkeletonCard(type: string): HTMLElement {
    const card = document.createElement("div");
    card.className = "qa-card";
    card.id = `qa-card-${type}`;
    card.setAttribute("aria-busy", "true");
    const badge = document.createElement("div");
    badge.className = "qa-type-badge";
    badge.textContent = getTypeBadge(type);
    card.appendChild(badge);
    const skeletonQuery = document.createElement("div");
    skeletonQuery.className = "skeleton skeleton-text";
    skeletonQuery.style.cssText = "height: 1.5em; width: 80%; margin: 16px 0";
    card.appendChild(skeletonQuery);
    const skeletonAnswer = document.createElement("div");
    skeletonAnswer.className = "skeleton skeleton-block";
    skeletonAnswer.style.cssText = "height: 100px; margin: 16px 0";
    card.appendChild(skeletonAnswer);
    return card;
}

function updateCardWithData(type: string, data: QAPair): void {
    const card = document.getElementById(`qa-card-${type}`);
    if (!card) return;
    card.removeAttribute("aria-busy");
    card.innerHTML = "";
    const badge = document.createElement("div");
    badge.className = "qa-type-badge";
    badge.textContent = getTypeBadge(type);
    card.appendChild(badge);
    const querySection = document.createElement("div");
    querySection.className = "qa-section";
    const queryLabel = document.createElement("strong");
    queryLabel.textContent = "💬 질의";
    const queryContent = document.createElement("div");
    queryContent.className = "qa-content";
    queryContent.textContent = data.query;
    querySection.appendChild(queryLabel);
    querySection.appendChild(queryContent);
    card.appendChild(querySection);
    const answerSection = document.createElement("div");
    answerSection.className = "qa-section";
    const answerLabel = document.createElement("strong");
    answerLabel.textContent = "✨ 답변";
    const answerContent = document.createElement("div");
    answerContent.className = "qa-content";
    answerContent.innerHTML = formatAnswer(data.answer);
    answerSection.appendChild(answerLabel);
    answerSection.appendChild(answerContent);
    card.appendChild(answerSection);
    const btnRow = document.createElement("div");
    btnRow.className = "btn-row qa-btn-row";
    const copyBtn = document.createElement("button");
    copyBtn.className = "btn-small qa-copy-btn";
    copyBtn.textContent = "📝 워크스페이스로 복사";
    copyBtn.addEventListener("click", () => copyToWorkspace(data.query, data.answer));
    btnRow.appendChild(copyBtn);
    card.appendChild(btnRow);
}

function showErrorInCard(type: string, error: string): void {
    const card = document.getElementById(`qa-card-${type}`);
    if (!card) return;
    card.removeAttribute("aria-busy");
    card.innerHTML = "";
    card.className = "qa-card error-state";
    card.setAttribute("role", "alert");
    const icon = document.createElement("div");
    icon.className = "error-state__icon";
    icon.textContent = "⚠️";
    card.appendChild(icon);
    const heading = document.createElement("h3");
    heading.style.cssText = "margin: 0 0 8px 0; color: var(--accent-danger);";
    heading.textContent = `${getTypeBadge(type)} 생성 실패`;
    card.appendChild(heading);
    const text = document.createElement("p");
    text.className = "error-state__text";
    text.textContent = error;
    card.appendChild(text);
}

async function generateQAStreaming(mode: "batch" | "batch_three"): Promise<void> {
    const resultsDiv = document.getElementById("results");
    if (!resultsDiv) return;
    const ocrInput = document.getElementById("ocr-input") as HTMLTextAreaElement;
    const ocrText = ocrInput.value;
    if (!ocrText.trim()) {
        showToast("OCR 텍스트를 먼저 입력하세요.", "error");
        return;
    }
    resultsDiv.innerHTML = "";
    try {
        const response = await fetch("/api/qa/generate/batch/stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode, ocr_text: ocrText }),
            signal: activeController?.signal
        });
        if (!response.ok) {
            const detail = await response.text();
            throw new Error(`HTTP ${response.status}: ${response.statusText}${detail ? " :: " + detail : ""}`);
        }
        if (!response.body) throw new Error("No response body");
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const events = buffer.split("\n\n");
            buffer = events.pop() || "";
            for (const event of events) {
                if (!event.startsWith("data: ")) continue;
                const payload = event.slice(6).trim();
                try {
                    const data = JSON.parse(payload);
                    if (data.event === "started") {
                        const batchTypes = mode === "batch_three" ? ["global_explanation", "reasoning", "target_long"] : ["global_explanation", "reasoning", "target_short", "target_long"];
                        batchTypes.forEach(type => resultsDiv.appendChild(createSkeletonCard(type)));
                    } else if (data.event === "progress") {
                        updateCardWithData(data.type, data.data);
                    } else if (data.event === "error") {
                        if (data.type) showErrorInCard(data.type, data.error);
                        else showToast(`오류: ${data.error}`, "error");
                    } else if (data.event === "done") {
                        const summary = data.success ? `✅ 완료: ${data.completed}/${data.total} 성공` : "⚠️ 일부 실패";
                        showToast(summary, data.success ? "success" : "warning");
                    }
                } catch (parseError) {
                    console.error("Failed to parse SSE event:", payload, parseError);
                }
            }
        }
    } catch (error) {
        console.error("Streaming error:", error);
        const message = error instanceof Error ? error.message : "알 수 없는 오류";
        resultsDiv.innerHTML = `<div class="error-state"><div class="error-state__icon">⚠️</div><h3 style="margin: 0 0 8px 0; color: var(--accent-danger);">스트리밍 실패</h3><p class="error-state__text">${message}</p></div>`;
        showToast(`스트리밍 오류: ${message}`, "error");
    }
}

function setupModeKeyboardNavigation(): void {
    const radios = Array.from(document.querySelectorAll<HTMLInputElement>("input[name=\"mode\"]"));
    if (!radios.length) return;

    const focusRadio = (index: number) => {
        const target = radios[index];
        target.focus();
        target.checked = true;
        target.dispatchEvent(new Event("change", { bubbles: true }));
    };

    radios.forEach((radio, idx) => {
        radio.addEventListener("keydown", (e: KeyboardEvent) => {
            let nextIndex = idx;
            if (e.key === "ArrowRight" || e.key === "ArrowDown") {
                nextIndex = (idx + 1) % radios.length;
                e.preventDefault();
                focusRadio(nextIndex);
            } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
                nextIndex = (idx - 1 + radios.length) % radios.length;
                e.preventDefault();
                focusRadio(nextIndex);
            } else if (e.key === "Home") {
                e.preventDefault();
                focusRadio(0);
            } else if (e.key === "End") {
                e.preventDefault();
                focusRadio(radios.length - 1);
            }
        });
    });
}

export function initQA(): void {
    loadOCR();
    document.getElementById("save-ocr-btn")?.addEventListener("click", () => saveOCR());

    document.querySelectorAll("input[name=\"mode\"]").forEach((radio) => {
        radio.addEventListener("change", (e) => {
            const selector = document.getElementById("type-selector");
            if (selector) {
                selector.style.display = (e.target as HTMLInputElement).value === "single" ? "block" : "none";
            }
        });
    });

    document.getElementById("generate-btn")?.addEventListener("click", async () => {
        const modeInput = document.querySelector("input[name=\"mode\"]:checked") as HTMLInputElement;
        const mode = (modeInput?.value || "single") as GenerateMode;
        const qtypeInput = document.getElementById("qtype") as HTMLSelectElement;
        const qtype = mode === "single" ? qtypeInput.value : null;
        if (mode === "batch" || mode === "batch_three") {
            await generateQAStreaming(mode);
        } else {
            await generateQA(mode, qtype);
        }
    });

    setupModeKeyboardNavigation();

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && activeController) {
            activeController.abort();
            showToast("요청을 취소했습니다.", "warning");
        }
    });
}
