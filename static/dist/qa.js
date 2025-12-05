import { apiCall, copyToClipboard, showToast, showProgressWithEstimate } from "./utils.js";
import { loadOCR, saveOCR } from "./ocr.js";
function getModeLabels(mode) {
    if (mode === "batch") {
        return { title: "⚡ 4개 타입 동시 생성 중...", eta: "30초~2분" };
    }
    if (mode === "batch_three") {
        return { title: "⚡ 3개 타입 동시 생성 중...", eta: "20초~90초" };
    }
    return { title: "🚀 답변 생성 중...", eta: "15초~1분" };
}
function renderProgress(mode) {
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
function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text || "";
    return div.innerHTML;
}
function formatAnswer(text) {
    const escaped = escapeHtml(text);
    const formatted = escaped
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
        .replace(/\n\n/g, "<br><br>")
        .replace(/\n/g, "<br>")
        .replace(/^- /gm, "• ");
    // DOMPurify is loaded globally
    return window.DOMPurify ? window.DOMPurify.sanitize(formatted) : formatted;
}
function getTypeBadge(type) {
    const badges = {
        global_explanation: "🌍 전반 설명",
        reasoning: "🧠 추론",
        target_short: "🎯 타겟 단답",
        target_long: "📝 타겟 장답",
    };
    return badges[type] || type;
}
function copyToWorkspace(query, answer) {
    sessionStorage.setItem("workspace_query", query);
    sessionStorage.setItem("workspace_answer", answer);
    window.location.href = "/workspace";
}
function displayResults(data) {
    var _a;
    if (data && data.success !== undefined && data.data) {
        data = data.data;
    }
    const resultsDiv = document.getElementById("results");
    resultsDiv.innerHTML = "";
    let pairs = data.pairs || (data.pair ? [data.pair] : []);
    const selectedMode = (_a = document.querySelector("input[name=\"mode\"]:checked")) === null || _a === void 0 ? void 0 : _a.value;
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
        copyBtn.addEventListener("click", () => {
            copyToWorkspace(item.query || "", item.answer || "");
        });
        resultsDiv.appendChild(card);
    });
}
async function generateQA(mode, qtype) {
    const resultsDiv = document.getElementById("results");
    const ocrText = document.getElementById("ocr-input").value;
    if (!ocrText.trim()) {
        showToast("OCR 텍스트를 먼저 입력하세요.", "error");
        return;
    }
    resultsDiv.innerHTML = renderProgress(mode);
    const stopProgress = showProgressWithEstimate(mode);
    const progressBar = document.querySelector(".progress-fill");
    try {
        const payload = { mode, ocr_text: ocrText };
        if (mode === "single") {
            payload.qtype = qtype || "global_explanation";
        }
        else if (mode === "batch_three") {
            payload.mode = "batch";
            payload.batch_types = [
                "global_explanation",
                "reasoning",
                "target_long",
            ];
        }
        const result = await apiCall("/api/qa/generate", "POST", payload);
        stopProgress();
        if (progressBar)
            progressBar.style.width = "100%";
        await new Promise((resolve) => setTimeout(resolve, 300));
        displayResults(result);
    }
    catch (error) {
        stopProgress();
        resultsDiv.innerHTML = `
            <div style="text-align: center; padding: 30px; background: #ffebee; border-radius: 8px; border: 1px solid #f44336; margin-top: 20px;">
                <h3 style="color: #f44336; margin-bottom: 10px;">❌ 생성 실패</h3>
                <p style="color: #666; margin: 0;">${error.message}</p>
            </div>
        `;
    }
}
export function initQA() {
    var _a, _b;
    loadOCR();
    (_a = document.getElementById("save-ocr-btn")) === null || _a === void 0 ? void 0 : _a.addEventListener("click", () => saveOCR());
    document.querySelectorAll("input[name=\"mode\"]").forEach((radio) => {
        radio.addEventListener("change", (e) => {
            const selector = document.getElementById("type-selector");
            selector.style.display = e.target.value === "single" ? "block" : "none";
        });
    });
    (_b = document.getElementById("generate-btn")) === null || _b === void 0 ? void 0 : _b.addEventListener("click", async () => {
        const mode = document.querySelector("input[name=\"mode\"]:checked").value;
        const qtype = mode === "single" ? document.getElementById("qtype").value : null;
        await generateQA(mode, qtype);
    });
}
