import { apiCall, showToast } from "./utils.js";
import { loadOCR, saveOCR } from "./ocr.js";

interface EvalCandidate {
    candidate_id: string;
    score: number;
    feedback: string;
}

interface EvalResponse {
    best: string;
    results: EvalCandidate[];
}

export function initEval(): void {
    loadOCR();
    document.getElementById("save-ocr-btn")?.addEventListener("click", () => saveOCR());

    document.getElementById("eval-btn")?.addEventListener("click", async () => {
        const query = (document.getElementById("query") as HTMLTextAreaElement).value;
        const answers = [
            (document.getElementById("answer-a") as HTMLTextAreaElement).value,
            (document.getElementById("answer-b") as HTMLTextAreaElement).value,
            (document.getElementById("answer-c") as HTMLTextAreaElement).value,
        ];

        if (!query || answers.some((a) => !a.trim())) {
            showToast("모든 필드를 입력해주세요.", "error");
            return;
        }

        await evaluateAnswers(query, answers);
    });
}

async function evaluateAnswers(query: string, answers: string[]): Promise<void> {
    const resultsDiv = document.getElementById("eval-results");
    if (!resultsDiv) return;

    // Create loading indicator using DOM API
    resultsDiv.innerHTML = "";
    const loadingDiv = document.createElement("div");
    loadingDiv.className = "loading";
    resultsDiv.appendChild(loadingDiv);
    resultsDiv.appendChild(document.createTextNode(" 처리 중..."));

    try {
        const data = await apiCall<EvalResponse>("/api/eval/external", "POST", { query, answers });
        resultsDiv.innerHTML = "";

        const heading = document.createElement("h3");
        heading.textContent = "평가 결과";
        resultsDiv.appendChild(heading);

        const table = document.createElement("table");
        const thead = document.createElement("thead");
        const headerRow = document.createElement("tr");
        ["답변", "점수", "피드백"].forEach((text) => {
            const th = document.createElement("th");
            th.textContent = text;
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);

        const tbody = document.createElement("tbody");
        data.results.forEach((r) => {
            const row = document.createElement("tr");
            if (r.candidate_id === data.best) {
                row.className = "best-answer";
            }

            const tdId = document.createElement("td");
            tdId.textContent = r.candidate_id + (r.candidate_id === data.best ? " ⭐" : "");
            row.appendChild(tdId);

            const tdScore = document.createElement("td");
            tdScore.textContent = String(r.score);
            row.appendChild(tdScore);

            const tdFeedback = document.createElement("td");
            tdFeedback.textContent = r.feedback;
            row.appendChild(tdFeedback);

            tbody.appendChild(row);
        });
        table.appendChild(tbody);
        resultsDiv.appendChild(table);
    } catch (error: unknown) {
        resultsDiv.innerHTML = "";
        const errorP = document.createElement("p");
        errorP.className = "eval-error-message";
        errorP.textContent = `평가 실패: ${error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다."}`;
        resultsDiv.appendChild(errorP);
    }
}
