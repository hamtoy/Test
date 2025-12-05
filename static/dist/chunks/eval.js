import{s as r,b as o}from"../app.js";import{l as c,s as l}from"./ocr.js";function v(){var s,d;c(),(s=document.getElementById("save-ocr-btn"))==null||s.addEventListener("click",()=>l()),(d=document.getElementById("eval-btn"))==null||d.addEventListener("click",async()=>{const t=document.getElementById("query").value,e=[document.getElementById("answer-a").value,document.getElementById("answer-b").value,document.getElementById("answer-c").value];if(!t||e.some(a=>!a.trim())){r("모든 필드를 입력해주세요.","error");return}await i(t,e)})}async function i(s,d){const t=document.getElementById("eval-results");if(t){t.innerHTML='<div class="loading"></div> 처리 중...';try{const e=await o("/api/eval/external","POST",{query:s,answers:d});t.innerHTML="<h3>평가 결과</h3>";const a=document.createElement("table");a.innerHTML=`
            <thead>
                <tr>
                    <th>답변</th>
                    <th>점수</th>
                    <th>피드백</th>
                </tr>
            </thead>
            <tbody>
                ${e.results.map(n=>`
                    <tr class="${n.candidate_id===e.best?"best-answer":""}">
                        <td>${n.candidate_id} ${n.candidate_id===e.best?"⭐":""}</td>
                        <td>${n.score}</td>
                        <td>${n.feedback}</td>
                    </tr>
                `).join("")}
            </tbody>
        `,t.appendChild(a)}catch(e){const a=e instanceof Error?e.message:"알 수 없는 오류가 발생했습니다.";t.innerHTML=`<p style="color: var(--danger)">평가 실패: ${a}</p>`}}}export{v as initEval};
//# sourceMappingURL=eval.js.map
