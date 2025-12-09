import{s as p,a as g,w as f,b as y}from"../app.js";import{l as m,s as h}from"./ocr.js";import{validateRequest as b,ValidationError as v}from"./validation.js";let i=null;function x(e){return e==="batch"?{title:"⚡ 4개 타입 동시 생성 중...",eta:"30초~2분"}:e==="batch_three"?{title:"⚡ 3개 타입 동시 생성 중...",eta:"20초~90초"}:{title:"🚀 답변 생성 중...",eta:"15초~1분"}}function w(e){const{title:t,eta:r}=x(e);return`
        <div class="progress-container" style="text-align: center; padding: 40px 20px; background: var(--bg-secondary, #f5f5f5); border-radius: 8px;">
            <h3 style="margin-bottom: 20px; color: var(--text-primary, #333);">${t}</h3>
            <div style="margin: 25px auto; width: 320px; height: 10px; background: #e0e0e0; border-radius: 5px; overflow: hidden; box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);">
                <div class="progress-fill" style="width: 0%; height: 100%; background: linear-gradient(90deg, var(--primary, #21808d) 0%, var(--primary-dark, #1a6673) 100%); transition: width 0.5s ease;"></div>
            </div>
            <p style="color: var(--text-secondary, #666); font-size: 0.95em; margin-top: 20px; font-weight: 500;">예상 소요 시간: <strong>${r}</strong></p>
            <p style="color: var(--text-secondary, #666); font-size: 0.85em; margin-top: 8px;">병렬 처리로 빠르게 완료됩니다 ✨</p>
        </div>
    `}function u(e){const t=document.createElement("div");return t.textContent=e||"",t.innerHTML}function q(e){const r=u(e).replace(/\n\n/g,"<br><br>").replace(/\n/g,"<br>").replace(/ - /g,"<br><br>- ");return window.DOMPurify?window.DOMPurify.sanitize(r):r}function k(e){return{explanation:"🌍 전반 설명",global_explanation:"🌍 전반 설명",reasoning:"🧠 추론",target_short:"🎯 타겟 단답",target_long:"📝 타겟 장답"}[e]||e}function E(e,t){sessionStorage.setItem("workspace_query",e),sessionStorage.setItem("workspace_answer",t),window.location.href="/workspace"}function _(e){if(!e||typeof e!="object")return!1;const t=e;return typeof t.type=="string"&&typeof t.query=="string"&&typeof t.answer=="string"}function L(e){var o,n;if(!e||typeof e!="object")return[];const t=e,r=[];return t.pairs&&r.push(...t.pairs),t.pair&&r.push(t.pair),(o=t.data)!=null&&o.pairs&&r.push(...t.data.pairs),(n=t.data)!=null&&n.pair&&r.push(t.data.pair),r.filter(_)}function A(e){var n;let t=L(e);const r=document.getElementById("results");if(!r)return;if(r.setAttribute("role","status"),r.setAttribute("aria-live","polite"),r.innerHTML="",((n=document.querySelector('input[name="mode"]:checked'))==null?void 0:n.value)==="batch_three"){const a=new Set(["global_explanation","reasoning","target_long"]);t=t.filter(l=>a.has(l.type))}if(!t.length){r.innerHTML=`
            <div class="qa-card">
                <p style="margin:0; color: var(--text-secondary, #666);">결과가 없습니다.</p>
            </div>
        `;return}t.forEach((a,l)=>{const s=document.createElement("div");s.className="qa-card",s.style.animation=`slideIn 0.3s ease-out ${l*.05}s both`,s.innerHTML=`
            <div class="qa-header">
                <span class="qa-type-badge">${k(a.type)}</span>
            </div>
            <div class="qa-section">
                <strong>💬 질의</strong>
                <div class="qa-content">${u(a.query)}</div>
            </div>
            <div class="qa-section">
                <strong>✨ 답변</strong>
                <div class="qa-content">${q(a.answer)}</div>
            </div>
            <div class="btn-row" style="margin-top: 15px;">
                <button class="btn-small qa-copy-btn">📝 워크스페이스로 복사</button>
            </div>
        `;const c=s.querySelector(".qa-copy-btn");c==null||c.addEventListener("click",()=>{E(a.query||"",a.answer||"")}),r.appendChild(s)})}async function I(e,t){const r=document.getElementById("results");if(!r)return;const n=document.getElementById("ocr-input").value;if(!n.trim()){p("OCR 텍스트를 먼저 입력하세요.","error");return}r.innerHTML=w(e);const a=g(e==="batch"||e==="batch_three"?"batch":"single"),l=document.querySelector(".progress-fill");try{const s=e==="single"?{mode:"single",ocr_text:n,qtype:t||"global_explanation"}:{mode:"batch",ocr_text:n};e==="batch_three"&&(s.batch_types=["global_explanation","reasoning","target_long"]);try{b(s,"/api/qa/generate")}catch(d){if(d instanceof v){p(`요청 검증 실패: ${d.message}`,"error"),a(),r.innerHTML=`
                    <div style="text-align: center; padding: 30px; background: #ffebee; border-radius: 8px; border: 1px solid #f44336; margin-top: 20px;">
                        <h3 style="color: #f44336; margin-bottom: 10px;">⚠️ 요청 데이터 오류</h3>
                        <p style="color: #666; margin: 0; white-space: pre-line;">${d.message}</p>
                        <p style="color: #999; margin-top: 15px; font-size: 0.9em;">💡 필드명과 데이터 타입을 확인하세요</p>
                    </div>
                `;return}throw d}i&&i.abort(),i=new AbortController;const c=await f(()=>y("/api/qa/generate","POST",s,i.signal),2,800);i=null,a(),l&&(l.style.width="100%"),await new Promise(d=>setTimeout(d,300)),A(c)}catch(s){i=null,a();const c=s instanceof Error?s.message:"알 수 없는 오류가 발생했습니다.";r.innerHTML=`
            <div style="text-align: center; padding: 30px; background: #ffebee; border-radius: 8px; border: 1px solid #f44336; margin-top: 20px;">
                <h3 style="color: #f44336; margin-bottom: 10px;">❌ 생성 실패</h3>
                <p style="color: #666; margin: 0;">${c}</p>
            </div>
        `}}function M(){const e=Array.from(document.querySelectorAll('input[name="mode"]'));if(!e.length)return;const t=r=>{const o=e[r];o.focus(),o.checked=!0,o.dispatchEvent(new Event("change",{bubbles:!0}))};e.forEach((r,o)=>{r.addEventListener("keydown",n=>{let a=o;n.key==="ArrowRight"||n.key==="ArrowDown"?(a=(o+1)%e.length,n.preventDefault(),t(a)):n.key==="ArrowLeft"||n.key==="ArrowUp"?(a=(o-1+e.length)%e.length,n.preventDefault(),t(a)):n.key==="Home"?(n.preventDefault(),t(0)):n.key==="End"&&(n.preventDefault(),t(e.length-1))})})}function H(){var e,t;m(),(e=document.getElementById("save-ocr-btn"))==null||e.addEventListener("click",()=>h()),document.querySelectorAll('input[name="mode"]').forEach(r=>{r.addEventListener("change",o=>{const n=document.getElementById("type-selector");n&&(n.style.display=o.target.value==="single"?"block":"none")})}),(t=document.getElementById("generate-btn"))==null||t.addEventListener("click",async()=>{const r=document.querySelector('input[name="mode"]:checked'),o=(r==null?void 0:r.value)||"single",n=document.getElementById("qtype"),a=o==="single"?n.value:null;await I(o,a)}),M(),document.addEventListener("keydown",r=>{r.key==="Escape"&&i&&(i.abort(),p("요청을 취소했습니다.","warning"))})}export{H as initQA};
//# sourceMappingURL=qa.js.map
