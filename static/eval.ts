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
    resultsDiv.innerHTML = "<div class=\"loading\"></div> 처리 중...";

    try {
        const data = await apiCall<EvalResponse>("/api/eval/external", "POST", { query, answers });
        resultsDiv.innerHTML = "<h3>평가 결과</h3>";

        const table = document.createElement("table");
        table.innerHTML = `
            <thead>
                <tr>
                    <th>답변</th>
                    <th>점수</th>
                    <th>피드백</th>
                </tr>
            </thead>
            <tbody>
                ${data.results
                .map(
                    (r) => `
                    <tr class="${r.candidate_id === data.best ? "best-answer" : ""}">
                        <td>${r.candidate_id} ${r.candidate_id === data.best ? "⭐" : ""}</td>
                        <td>${r.score}</td>
                        <td>${r.feedback}</td>
                    </tr>
                `,
                )
                .join("")}
            </tbody>
        `;
        resultsDiv.appendChild(table);
    } catch (error: unknown) {
        const message =
            error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다.";
        resultsDiv.innerHTML = `<p style="color: var(--danger)">평가 실패: ${message}</p>`;
    }
}
