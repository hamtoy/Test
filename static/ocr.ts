import { apiCall, showToast } from "./utils.js";

interface OcrResponse {
    ocr?: string;
}

export async function loadOCR(targetId: string = "ocr-input"): Promise<void> {
    const input =
        document.getElementById(targetId) ||
        document.getElementById("ocr-preview");
    if (!input) {
        console.error("OCR element not found");
        return;
    }
    try {
        const data = await apiCall<OcrResponse>("/api/ocr");
        const value = data.ocr || "";
        if (input.tagName === "TEXTAREA") {
            (input as HTMLTextAreaElement).value = value;
            if (!value) {
                (input as HTMLTextAreaElement).placeholder = "OCR 파일이 없습니다. 텍스트를 직접 입력하세요...";
            }
        } else {
            input.textContent = value || "OCR 파일이 없습니다.";
            if (!value) input.style.color = "#999";
        }
    } catch (error: unknown) {
        const errorMessage = error instanceof Error ? error.message : "OCR 로드 실패";
        if (input.tagName === "TEXTAREA") {
            (input as HTMLTextAreaElement).value = "";
            (input as HTMLTextAreaElement).placeholder = errorMessage;
        } else {
            input.textContent = errorMessage;
        }
        // Show toast notification for better user feedback
        showToast(`OCR 로드 실패: ${errorMessage}`, "error");
    }
}

export async function saveOCR(sourceId: string = "ocr-input", statusId: string = "ocr-save-status"): Promise<void> {
    const input = document.getElementById(sourceId) as HTMLTextAreaElement;
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
    } catch (error: unknown) {
        if (statusEl) {
            statusEl.textContent = "❌ 저장 실패";
            statusEl.className = "status-text error";
        } else {
            const message =
                error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다.";
            showToast("OCR 저장 실패: " + message, "error");
        }
    }
}
