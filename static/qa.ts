import { apiCall, showToast, showProgressWithEstimate, withRetry } from "./utils.js";
import { loadOCR, saveOCR } from "./ocr.js";

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
    const escaped = escapeHtml(text);
    const formatted = escaped
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
        .replace(/\n\n/g, "<br><br>")
        .replace(/\n/g, "<br>")
        .replace(/^- /gm, "• ");
    // DOMPurify is loaded globally
    return window.DOMPurify ? window.DOMPurify.sanitize(formatted) : formatted;
}

function getTypeBadge(type: string): string {
    const badges: Record<string, string> = {
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
    resultsDiv.innerHTML = "";

    const selectedMode = (document.querySelector("input[name=\"mode\"]:checked") as HTMLInputElement)?.value;
    if (selectedMode === "batch_three") {
        const allowed = new Set(["global_explanation", "reasoning", "target_long"]);
        pairs = pairs.filter((p) => allowed.has(p.type));
    }
    if (!pairs.length) {
        resultsDiv.innerHTML = `
            <div class="qa-card">
                <p style="margin:0; color: var(--text-secondary, #666);">결과가 없습니다.</p>
            </div>
        `;
        return;
    }

    pairs.forEach((item, index) => {
        const card = document.createElement("div");
        card.className = "qa-card";
        card.style.animation = `slideIn 0.3s ease-out ${index * 0.05}s both`;

        card.innerHTML = `
            <div class="qa-header">
                <span class="qa-type-badge">${getTypeBadge(item.type)}</span>
            </div>
            <div class="qa-section">
                <strong>💬 질의</strong>
                <div class="qa-content">${escapeHtml(item.query)}</div>
            </div>
            <div class="qa-section">
                <strong>✨ 답변</strong>
                <div class="qa-content">${formatAnswer(item.answer)}</div>
            </div>
            <div class="btn-row" style="margin-top: 15px;">
                <button class="btn-small qa-copy-btn">📝 워크스페이스로 복사</button>
            </div>
        `;

        const copyBtn = card.querySelector(".qa-copy-btn");
        copyBtn?.addEventListener("click", () => {
            copyToWorkspace(item.query || "", item.answer || "");
        });

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
        await generateQA(mode, qtype);
    });

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && activeController) {
            activeController.abort();
            showToast("요청을 취소했습니다.", "warning");
        }
    });
}
