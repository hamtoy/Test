// 공통 유틸 함수 모음

const copyTimeouts = new Map();

export function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast toast--${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    requestAnimationFrame(() => toast.classList.add("toast--show"));
    setTimeout(() => {
        toast.classList.remove("toast--show");
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function createApiError(status, errorData = {}) {
    const messages = {
        400: "잘못된 요청입니다",
        401: "인증이 필요합니다",
        403: "접근 권한이 없습니다",
        404: "요청한 리소스를 찾을 수 없습니다",
        429: "요청이 너무 많습니다. 잠시 후 다시 시도해주세요",
        500: "서버 오류가 발생했습니다",
        502: "게이트웨이 오류입니다",
        503: "서비스를 일시적으로 사용할 수 없습니다",
        504: "LLM 응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요",
    };

    const detail =
        messages[status] ||
        errorData.detail ||
        errorData.message ||
        "요청 실패";
    const err = new Error(detail);
    err.status = status;
    err.canRetry = [429, 500, 502, 503, 504].includes(status);
    return err;
}

function handleApiError(error) {
    console.error("API Error:", error);
    if (error.canRetry) {
        showToast(`${error.message} [다시 시도 가능]`, "warning");
    } else {
        showToast(error.message, "error");
    }
}

export async function apiCall(url, method = "GET", body = null, signal) {
    const options = {
        method,
        headers: { "Content-Type": "application/json" },
        signal,
    };
    if (body) {
        options.body = JSON.stringify(body);
    }
    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            let errorData = {};
            try {
                errorData = await response.json();
            } catch {
                // ignore parse error
            }
            throw createApiError(response.status, errorData);
        }
        return await response.json();
    } catch (error) {
        if (error.name === "AbortError") {
            throw new Error("요청이 취소되었습니다");
        }
        handleApiError(error);
        throw error;
    }
}

export function showLoading(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.innerHTML = '<div class="loading"></div> 처리 중...';
}

export function copyToClipboard(text, buttonEl = null) {
    navigator.clipboard
        .writeText(text)
        .then(() => {
            if (buttonEl) {
                if (copyTimeouts.has(buttonEl)) {
                    clearTimeout(copyTimeouts.get(buttonEl));
                }
                if (!buttonEl.dataset.originalText) {
                    buttonEl.dataset.originalText = buttonEl.textContent;
                }
                buttonEl.textContent = "✅ 복사됨";
                buttonEl.classList.add("copied");
                const timeout = setTimeout(() => {
                    buttonEl.textContent = buttonEl.dataset.originalText;
                    buttonEl.classList.remove("copied");
                    copyTimeouts.delete(buttonEl);
                }, 1500);
                copyTimeouts.set(buttonEl, timeout);
            } else {
                showToast("클립보드에 복사되었습니다!", "success");
            }
        })
        .catch((err) => showToast("복사 실패: " + err.message, "error"));
}

// SSE 버퍼 파서 (불완전 청크 처리)
export function parseSSEBuffer(buffer) {
    const events = [];
    let startIdx = 0;

    while (true) {
        const dataIdx = buffer.indexOf("data:", startIdx);
        if (dataIdx === -1) break;
        const endIdx = buffer.indexOf("\n\n", dataIdx);
        if (endIdx === -1) {
            return { events, remainder: buffer.slice(startIdx) };
        }
        const payload = buffer.slice(dataIdx + 5, endIdx).trim();
        try {
            events.push(JSON.parse(payload));
        } catch (e) {
            console.warn("Failed to parse SSE chunk:", payload, e);
        }
        startIdx = endIdx + 2;
    }
    return { events, remainder: "" };
}

// 진행률 추정 헬퍼
export function showProgressWithEstimate(mode) {
    const estimatedTime = mode === "batch" ? 90000 : 45000; // ms
    const startTime = Date.now();
    const progressInterval = setInterval(() => {
        const elapsed = Date.now() - startTime;
        const progress = Math.min(95, (elapsed / estimatedTime) * 100);
        const bar = document.querySelector(".progress-fill");
        if (bar) bar.style.width = progress + "%";
    }, 200);
    return () => clearInterval(progressInterval);
}
