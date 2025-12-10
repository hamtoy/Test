// 공통 유틸 함수 모음

const copyTimeouts = new Map<HTMLElement, number>();
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Creates a debounced function that delays invoking fn until after delay ms
 * have elapsed since the last time the debounced function was invoked.
 */
export function debounce<T extends (...args: Parameters<T>) => void>(
    fn: T,
    delay: number
): (...args: Parameters<T>) => void {
    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    return (...args: Parameters<T>) => {
        if (timeoutId !== undefined) {
            clearTimeout(timeoutId);
        }
        timeoutId = setTimeout(() => {
            fn(...args);
            timeoutId = undefined;
        }, delay);
    };
}

export type ToastType = "info" | "success" | "warning" | "error";

export function showToast(message: string, type: ToastType = "info"): void {
    if (typeof document === "undefined") {
        console.warn(`[toast:${type}] ${message}`);
        return;
    }
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

export interface ApiErrorData {
    detail?: string;
    message?: string;
    [key: string]: unknown;
}

export class ApiError extends Error {
    status: number;
    canRetry: boolean;
    errorData: ApiErrorData;

    constructor(status: number, errorData: ApiErrorData = {}) {
        const messages: Record<number, string> = {
            400: "잘못된 요청입니다",
            401: "인증이 필요합니다",
            403: "접근 권한이 없습니다",
            404: "요청한 리소스를 찾을 수 없습니다",
            422: "요청 데이터 검증 실패",
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
        super(detail);
        this.status = status;
        this.canRetry = [429, 500, 502, 503, 504].includes(status);
        this.errorData = errorData;
    }
}

function handleApiError(error: unknown): void {
    console.error("API Error:", error);
    if (error instanceof ApiError) {
        // Special handling for 422 validation errors
        if (error.status === 422) {
            // Import parse422Error dynamically to avoid circular dependency
            import("./validation.js").then(({ parse422Error }) => {
                const detailedMessage = parse422Error(error.errorData);
                showToast(detailedMessage, "error");
            }).catch(() => {
                showToast(error.message, "error");
            });
            return;
        }

        if (error.canRetry) {
            showToast(`${error.message} [다시 시도 가능]`, "warning");
        } else {
            showToast(error.message, "error");
        }
    } else if (error instanceof Error) {
        showToast(error.message, "error");
    } else {
        showToast("알 수 없는 오류가 발생했습니다.", "error");
    }
}

export function registerGlobalErrorHandlers(): void {
    if (typeof window === "undefined") return;
    window.addEventListener("error", (event: ErrorEvent) => {
        if (event.error) {
            showToast(`오류: ${event.error.message}`, "error");
        } else {
            showToast("알 수 없는 오류가 발생했습니다.", "error");
        }
    });
    window.addEventListener("unhandledrejection", (event: PromiseRejectionEvent) => {
        const reason = event.reason;
        if (reason instanceof Error) {
            showToast(`오류: ${reason.message}`, "error");
        } else if (typeof reason === "string") {
            showToast(`오류: ${reason}`, "error");
        } else {
            showToast("알 수 없는 오류가 발생했습니다.", "error");
        }
    });
}

export interface ApiCallParams {
    url: string;
    method?: string;
    body?: unknown;
    signal?: AbortSignal;
}

export async function apiCall<T = unknown>(
    url: string,
    method: string = "GET",
    body?: unknown,
    signal?: AbortSignal
): Promise<T> {
    const options: RequestInit = {
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
            let errorData: ApiErrorData = {};
            try {
                errorData = await response.json();
            } catch {
                // ignore parse error
            }
            throw new ApiError(response.status, errorData);
        }
        return await response.json();
    } catch (error: unknown) {
        if (error instanceof DOMException && error.name === "AbortError") {
            throw new Error("요청이 취소되었습니다");
        }
        handleApiError(error);
        throw error;
    }
}

export async function apiCallWithRetry<T = unknown>(
    params: ApiCallParams & { retries?: number; initialDelayMs?: number },
): Promise<T> {
    const { retries = 2, initialDelayMs = 500, ...rest } = params;
    return withRetry(
        () => apiCall<T>(rest.url, rest.method, rest.body, rest.signal),
        retries,
        initialDelayMs,
    );
}

export function showLoading(elementId: string): void {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.innerHTML = '<div class="loading"></div> 처리 중...';
}

export function copyToClipboard(text: string, buttonEl: HTMLElement | null = null): void {
    navigator.clipboard
        .writeText(text)
        .then(() => {
            if (buttonEl) {
                if (copyTimeouts.has(buttonEl)) {
                    clearTimeout(copyTimeouts.get(buttonEl)!);
                }
                if (!buttonEl.dataset.originalText) {
                    buttonEl.dataset.originalText = buttonEl.textContent || "";
                }
                buttonEl.textContent = "✅ 복사됨";
                buttonEl.classList.add("copied");
                const timeout = setTimeout(() => {
                    buttonEl.textContent = buttonEl.dataset.originalText || "";
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

export interface SSEParseResult {
    events: unknown[];
    remainder: string;
}

// SSE 버퍼 파서 (불완전 청크 처리)
export function parseSSEBuffer(buffer: string): SSEParseResult {
    const events: unknown[] = [];
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
export function showProgressWithEstimate(mode: "batch" | "single"): () => void {
    const estimatedTime = mode === "batch" ? 90000 : 45000; // ms
    const startTime = Date.now();
    const progressInterval = setInterval(() => {
        const elapsed = Date.now() - startTime;
        const progress = Math.min(95, (elapsed / estimatedTime) * 100);
        const bar = document.querySelector(".progress-fill") as HTMLElement;
        if (bar) bar.style.width = progress + "%";
    }, 200);
    return () => clearInterval(progressInterval);
}

export async function withRetry<T>(
    fn: () => Promise<T>,
    retries: number = 2,
    initialDelayMs: number = 500
): Promise<T> {
    let attempt = 0;
    let delay = initialDelayMs;
    let lastError: unknown;
    while (attempt <= retries) {
        try {
            return await fn();
        } catch (err: unknown) {
            lastError = err;
            const retryable =
                !err ||
                (err instanceof ApiError && err.canRetry) ||
                (typeof err === "object" &&
                    err !== null &&
                    "status" in err &&
                    typeof (err as { status?: number }).status === "number" &&
                    (err as { status: number }).status >= 500);
            if (attempt === retries || !retryable) {
                break;
            }
            await sleep(delay);
            delay *= 2;
            attempt += 1;
        }
    }
    throw lastError;
}

export function createRipple(event: MouseEvent): void {
    const button = event.currentTarget as HTMLElement;
    const circle = document.createElement("span");
    const diameter = Math.max(button.clientWidth, button.clientHeight);
    const radius = diameter / 2;

    circle.style.width = circle.style.height = `${diameter}px`;
    circle.style.left = `${event.clientX - button.getBoundingClientRect().left - radius}px`;
    circle.style.top = `${event.clientY - button.getBoundingClientRect().top - radius}px`;
    circle.classList.add("ripple");

    const existingRipple = button.getElementsByClassName("ripple")[0];
    if (existingRipple) {
        existingRipple.remove();
    }

    button.appendChild(circle);

    setTimeout(() => circle.remove(), 600);
}
