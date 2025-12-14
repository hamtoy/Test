import { apiCall, showToast } from "./utils.js";

interface OcrResponse {
    ocr?: string;
}

interface ImageOcrResponse {
    status: string;
    ocr: string;
    metadata: {
        text_density: number;
        topics: string[];
        has_table_chart: boolean;
    };
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
                (input as HTMLTextAreaElement).placeholder = "OCR 파일이 없습니다. 텍스트를 직접 입력하거나 이미지를 업로드하세요...";
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

/** 이미지 파일을 Gemini Vision OCR로 처리 */
export async function uploadImageOCR(file: File): Promise<ImageOcrResponse | null> {
    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch("/api/ocr/image", {
            method: "POST",
            body: formData,
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || "OCR 처리 실패");
        }

        return await response.json();
    } catch (error) {
        const message = error instanceof Error ? error.message : "알 수 없는 오류";
        showToast(`이미지 OCR 실패: ${message}`, "error");
        return null;
    }
}

/** 드래그앤드롭 영역 초기화 */
export function initImageDropZone(
    dropZoneId: string = "image-drop-zone",
    targetId: string = "ocr-input"
): void {
    const dropZone = document.getElementById(dropZoneId);
    const targetInput = document.getElementById(targetId) as HTMLTextAreaElement;
    const fileInput = document.getElementById("image-file-input") as HTMLInputElement;

    if (!dropZone || !targetInput) return;

    // 드래그 이벤트
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("drag-over");
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("drag-over");
    });

    dropZone.addEventListener("drop", async (e) => {
        e.preventDefault();
        dropZone.classList.remove("drag-over");

        const files = e.dataTransfer?.files;
        if (files && files.length > 0) {
            await processImageFile(files[0], targetInput, dropZone);
        }
    });

    // 클릭으로 파일 선택
    dropZone.addEventListener("click", () => {
        fileInput?.click();
    });

    fileInput?.addEventListener("change", async () => {
        if (fileInput.files && fileInput.files.length > 0) {
            await processImageFile(fileInput.files[0], targetInput, dropZone);
        }
    });
}

async function processImageFile(
    file: File,
    targetInput: HTMLTextAreaElement,
    dropZone: HTMLElement
): Promise<void> {
    // 이미지 타입 검증
    const allowedTypes = ["image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp"];
    if (!allowedTypes.includes(file.type)) {
        showToast("지원하지 않는 이미지 형식입니다", "error");
        return;
    }

    // 로딩 상태 표시
    const originalText = dropZone.innerHTML;
    dropZone.innerHTML = `
        <div class="ocr-loading">
            <div class="spinner"></div>
            <span>🔍 Gemini Vision OCR 처리 중...</span>
        </div>
    `;
    dropZone.classList.add("processing");

    try {
        const result = await uploadImageOCR(file);
        if (result && result.ocr) {
            targetInput.value = result.ocr;
            showToast(`✅ OCR 완료! ${result.ocr.length}자 추출`, "success");

            // 메타데이터 표시
            if (result.metadata.topics.length > 0) {
                console.log("추출된 주제:", result.metadata.topics);
            }
            if (result.metadata.has_table_chart) {
                showToast("📊 표/차트가 감지되었습니다", "info");
            }
        }
    } finally {
        dropZone.innerHTML = originalText;
        dropZone.classList.remove("processing");
    }
}
