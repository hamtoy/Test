import { apiCall, showToast } from "./utils.js";
export async function loadOCR(targetId = "ocr-input") {
    const input = document.getElementById(targetId) ||
        document.getElementById("ocr-preview");
    if (!input) {
        console.error("OCR element not found");
        return;
    }
    try {
        const data = await apiCall("/api/ocr");
        const value = data.ocr || "";
        if (input.tagName === "TEXTAREA") {
            input.value = value;
            if (!value) {
                input.placeholder = "OCR 파일이 없습니다. 텍스트를 직접 입력하세요...";
            }
        }
        else {
            input.textContent = value || "OCR 파일이 없습니다.";
            if (!value)
                input.style.color = "#999";
        }
    }
    catch (error) {
        if (input.tagName === "TEXTAREA") {
            input.value = "";
            input.placeholder = "OCR 로드 실패";
        }
        else {
            input.textContent = "OCR 로드 실패";
        }
    }
}
export async function saveOCR(sourceId = "ocr-input", statusId = "ocr-save-status") {
    const input = document.getElementById(sourceId);
    if (!input) {
        console.error("OCR source not found");
        return;
    }
    const statusEl = document.getElementById(statusId);
    try {
        await apiCall("/api/ocr", "POST", { text: input.value });
        if (statusEl) {
            statusEl.textContent = "✅ 저장됨";
            statusEl.className = "status-text success";
            setTimeout(() => (statusEl.textContent = ""), 2000);
        }
    }
    catch (error) {
        if (statusEl) {
            statusEl.textContent = "❌ 저장 실패";
            statusEl.className = "status-text error";
        }
        else {
            showToast("OCR 저장 실패: " + error.message, "error");
        }
    }
}
