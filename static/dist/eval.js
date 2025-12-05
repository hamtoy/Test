import { apiCall, showToast } from "./utils.js";
import { loadOCR, saveOCR } from "./ocr.js";
export function initEval() {
    var _a, _b;
    loadOCR();
    (_a = document.getElementById("save-ocr-btn")) === null || _a === void 0 ? void 0 : _a.addEventListener("click", () => saveOCR());
    (_b = document.getElementById("eval-btn")) === null || _b === void 0 ? void 0 : _b.addEventListener("click", async () => {
        const query = document.getElementById("query").value;
        const answers = [
            document.getElementById("answer-a").value,
            document.getElementById("answer-b").value,
            document.getElementById("answer-c").value,
        ];
        if (!query || answers.some((a) => !a.trim())) {
            showToast("모든 필드를 입력해주세요.", "error");
            return;
        }
        await evaluateAnswers(query, answers);
    });
}
async function evaluateAnswers(query, answers) {
    const resultsDiv = document.getElementById("eval-results");
    resultsDiv.innerHTML = "<div class=\"loading\"></div> 처리 중...";
    try {
        const data = await apiCall("/api/eval/external", "POST", { query, answers });
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
            .map((r) => `
                    <tr class="${r.candidate_id === data.best ? "best-answer" : ""}">
                        <td>${r.candidate_id} ${r.candidate_id === data.best ? "⭐" : ""}</td>
                        <td>${r.score}</td>
                        <td>${r.feedback}</td>
                    </tr>
                `)
            .join("")}
            </tbody>
        `;
        resultsDiv.appendChild(table);
    }
    catch (error) {
        resultsDiv.innerHTML = `<p style="color: var(--danger)">평가 실패: ${error.message}</p>`;
    }
}
