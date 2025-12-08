import{s as d,a as g,w as y,b as f}from"../app.js";import{l as m,s as h}from"./ocr.js";let i=null;function v(e){return e==="batch"?{title:"⚡ 4개 타입 동시 생성 중...",eta:"30초~2분"}:e==="batch_three"?{title:"⚡ 3개 타입 동시 생성 중...",eta:"20초~90초"}:{title:"🚀 답변 생성 중...",eta:"15초~1분"}}function b(e){const{title:t,eta:n}=v(e);return`
        <div class="progress-container" style="text-align: center; padding: 40px 20px; background: var(--bg-secondary, #f5f5f5); border-radius: 8px;">
            <h3 style="margin-bottom: 20px; color: var(--text-primary, #333);">${t}</h3>
            <div style="margin: 25px auto; width: 320px; height: 10px; background: #e0e0e0; border-radius: 5px; overflow: hidden; box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);">
                <div class="progress-fill" style="width: 0%; height: 100%; background: linear-gradient(90deg, var(--primary, #21808d) 0%, var(--primary-dark, #1a6673) 100%); transition: width 0.5s ease;"></div>
            </div>
            <p style="color: var(--text-secondary, #666); font-size: 0.95em; margin-top: 20px; font-weight: 500;">예상 소요 시간: <strong>${n}</strong></p>
            <p style="color: var(--text-secondary, #666); font-size: 0.85em; margin-top: 8px;">병렬 처리로 빠르게 완료됩니다 ✨</p>
        </div>
    `}function p(e){const t=document.createElement("div");return t.textContent=e||"",t.innerHTML}function w(e){const n=p(e).replace(/\*\*([^*]+)\*\*/g,"<strong>$1</strong>").replace(/\n\n/g,"<br><br>").replace(/\n/g,"<br>").replace(/^- /gm,"• ");return window.DOMPurify?window.DOMPurify.sanitize(n):n}function x(e){return{explanation:"🌍 전반 설명",global_explanation:"🌍 전반 설명",reasoning:"🧠 추론",target_short:"🎯 타겟 단답",target_long:"📝 타겟 장답"}[e]||e}function k(e,t){sessionStorage.setItem("workspace_query",e),sessionStorage.setItem("workspace_answer",t),window.location.href="/workspace"}function q(e){if(!e||typeof e!="object")return!1;const t=e;return typeof t.type=="string"&&typeof t.query=="string"&&typeof t.answer=="string"}function E(e){var a,r;if(!e||typeof e!="object")return[];const t=e,n=[];return t.pairs&&n.push(...t.pairs),t.pair&&n.push(t.pair),(a=t.data)!=null&&a.pairs&&n.push(...t.data.pairs),(r=t.data)!=null&&r.pair&&n.push(t.data.pair),n.filter(q)}function _(e){var r;let t=E(e);const n=document.getElementById("results");if(!n)return;if(n.setAttribute("role","status"),n.setAttribute("aria-live","polite"),n.innerHTML="",((r=document.querySelector('input[name="mode"]:checked'))==null?void 0:r.value)==="batch_three"){const o=new Set(["explanation","global_explanation","reasoning","target_long"]);t=t.filter(l=>o.has(l.type))}if(!t.length){n.innerHTML=`
            <div class="qa-card">
                <p style="margin:0; color: var(--text-secondary, #666);">결과가 없습니다.</p>
            </div>
        `;return}t.forEach((o,l)=>{const s=document.createElement("div");s.className="qa-card",s.style.animation=`slideIn 0.3s ease-out ${l*.05}s both`,s.innerHTML=`
            <div class="qa-header">
                <span class="qa-type-badge">${x(o.type)}</span>
            </div>
            <div class="qa-section">
                <strong>💬 질의</strong>
                <div class="qa-content">${p(o.query)}</div>
            </div>
            <div class="qa-section">
                <strong>✨ 답변</strong>
                <div class="qa-content">${w(o.answer)}</div>
            </div>
            <div class="btn-row" style="margin-top: 15px;">
                <button class="btn-small qa-copy-btn">📝 워크스페이스로 복사</button>
            </div>
        `;const c=s.querySelector(".qa-copy-btn");c==null||c.addEventListener("click",()=>{k(o.query||"",o.answer||"")}),n.appendChild(s)})}async function A(e,t){const n=document.getElementById("results");if(!n)return;const r=document.getElementById("ocr-input").value;if(!r.trim()){d("OCR 텍스트를 먼저 입력하세요.","error");return}n.innerHTML=b(e);const o=g(e==="batch"||e==="batch_three"?"batch":"single"),l=document.querySelector(".progress-fill");try{const s=e==="single"?{mode:"single",ocr_text:r,qtype:t||"explanation"}:{mode:"batch",ocr_text:r};e==="batch_three"&&(s.batch_types=["explanation","reasoning","target_long"]),i&&i.abort(),i=new AbortController;const c=await y(()=>f("/api/qa/generate","POST",s,i.signal),2,800);i=null,o(),l&&(l.style.width="100%"),await new Promise(u=>setTimeout(u,300)),_(c)}catch(s){i=null,o();const c=s instanceof Error?s.message:"알 수 없는 오류가 발생했습니다.";n.innerHTML=`
            <div style="text-align: center; padding: 30px; background: #ffebee; border-radius: 8px; border: 1px solid #f44336; margin-top: 20px;">
                <h3 style="color: #f44336; margin-bottom: 10px;">❌ 생성 실패</h3>
                <p style="color: #666; margin: 0;">${c}</p>
            </div>
        `}}function L(){const e=Array.from(document.querySelectorAll('input[name="mode"]'));if(!e.length)return;const t=n=>{const a=e[n];a.focus(),a.checked=!0,a.dispatchEvent(new Event("change",{bubbles:!0}))};e.forEach((n,a)=>{n.addEventListener("keydown",r=>{let o=a;r.key==="ArrowRight"||r.key==="ArrowDown"?(o=(a+1)%e.length,r.preventDefault(),t(o)):r.key==="ArrowLeft"||r.key==="ArrowUp"?(o=(a-1+e.length)%e.length,r.preventDefault(),t(o)):r.key==="Home"?(r.preventDefault(),t(0)):r.key==="End"&&(r.preventDefault(),t(e.length-1))})})}function T(){var e,t;m(),(e=document.getElementById("save-ocr-btn"))==null||e.addEventListener("click",()=>h()),document.querySelectorAll('input[name="mode"]').forEach(n=>{n.addEventListener("change",a=>{const r=document.getElementById("type-selector");r&&(r.style.display=a.target.value==="single"?"block":"none")})}),(t=document.getElementById("generate-btn"))==null||t.addEventListener("click",async()=>{const n=document.querySelector('input[name="mode"]:checked'),a=(n==null?void 0:n.value)||"single",r=document.getElementById("qtype"),o=a==="single"?r.value:null;await A(a,o)}),L(),document.addEventListener("keydown",n=>{n.key==="Escape"&&i&&(i.abort(),d("요청을 취소했습니다.","warning"))})}export{T as initQA};
//# sourceMappingURL=qa.js.map
