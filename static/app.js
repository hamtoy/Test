// ============================================================================
// 공통 함수
// ============================================================================

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    requestAnimationFrame(() => toast.classList.add('toast--show'));
    setTimeout(() => {
        toast.classList.remove('toast--show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

async function apiCall(url, method = 'GET', body = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' }
    };

    if (body) {
        options.body = JSON.stringify(body);
    }

    try {
        const response = await fetch(url, options);
        if (!response.ok) {
            const error = await response.json();
            const err = new Error(error.detail || '요청 실패');
            err.status = response.status;  // Add status code to error object
            throw err;
        }
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        showToast('오류: ' + error.message, 'error');
        throw error;
    }
}

function showLoading(elementId) {
    const el = document.getElementById(elementId);
    el.innerHTML = '<div class="loading"></div> 처리 중...';
}

function copyToClipboard(text, buttonEl = null) {
    navigator.clipboard
        .writeText(text)
        .then(() => {
            if (buttonEl) {
                const originalText = buttonEl.textContent;
                buttonEl.textContent = '✅ 복사됨';
                buttonEl.classList.add('copied');
                setTimeout(() => {
                    buttonEl.textContent = originalText;
                    buttonEl.classList.remove('copied');
                }, 1500);
            } else {
                showToast('클립보드에 복사되었습니다!', 'success');
            }
        })
        .catch((err) => {
            showToast('복사 실패: ' + err.message, 'error');
        });
}

// ============================================================================
// OCR 로드 및 저장
// ============================================================================

async function loadOCR() {
    try {
        const data = await apiCall('/api/ocr');
        // Support both textarea (ocr-input) and div (ocr-preview) elements
        const input = document.getElementById('ocr-input') || document.getElementById('ocr-preview');

        if (!input) {
            console.error('OCR element not found (searched for ocr-input and ocr-preview)');
            return;
        }

        if (input.tagName === 'TEXTAREA') {
            // For textarea elements
            if (data.ocr) {
                input.value = data.ocr;
            } else {
                input.value = '';
                input.placeholder = 'OCR 파일이 없습니다. 텍스트를 직접 입력하세요...';
            }
        } else {
            // For div elements (read-only preview)
            if (data.ocr) {
                input.textContent = data.ocr;
            } else {
                input.textContent = 'OCR 파일이 없습니다.';
                input.style.color = '#999';
            }
        }
    } catch (error) {
        const input = document.getElementById('ocr-input') || document.getElementById('ocr-preview');
        if (input) {
            if (input.tagName === 'TEXTAREA') {
                input.value = '';
                input.placeholder = 'OCR 로드 실패';
            } else {
                input.textContent = 'OCR 로드 실패';
            }
        }
    }
}

async function saveOCR() {
    const ocrText = document.getElementById('ocr-input').value;
    const statusEl = document.getElementById('ocr-save-status');

    try {
        await apiCall('/api/ocr', 'POST', { text: ocrText });
        statusEl.textContent = '✅ 저장됨';
        statusEl.style.color = 'var(--success, green)';
        setTimeout(() => statusEl.textContent = '', 2000);
    } catch (error) {
        statusEl.textContent = '❌ 저장 실패';
        statusEl.style.color = 'var(--danger, red)';
    }
}

// ============================================================================
// QA 생성
// ============================================================================

async function generateQA(mode, qtype) {
    const resultsDiv = document.getElementById('results');

    const estimatedTime = mode === 'batch' ? '30초~2분' : '15초~1분';

    // 진행 상황 표시
    resultsDiv.innerHTML = `
        <div class="progress-container" style="text-align: center; padding: 40px 20px; background: var(--bg-secondary, #f5f5f5); border-radius: 8px;">
            <h3 style="margin-bottom: 20px; color: var(--text-primary, #333);">
                ${mode === 'batch' ? '⚡ 4개 타입 동시 생성 중...' : '🚀 답변 생성 중...'}
            </h3>
            <div style="margin: 25px auto; width: 320px; height: 10px; background: #e0e0e0; border-radius: 5px; overflow: hidden; box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);">
                <div class="progress-fill" style="width: 0%; height: 100%; background: linear-gradient(90deg, var(--primary, #21808d) 0%, var(--primary-dark, #1a6673) 100%); transition: width 0.5s ease;"></div>
            </div>
            <p style="color: var(--text-secondary, #666); font-size: 0.95em; margin-top: 20px; font-weight: 500;">
                예상 소요 시간: <strong>${estimatedTime}</strong>
            </p>
            <p style="color: var(--text-secondary, #666); font-size: 0.85em; margin-top: 8px;">
                병렬 처리로 빠르게 완료됩니다 ✨
            </p>
        </div>
    `;

    const progressBar = document.querySelector('.progress-fill');
    progressBar.classList.add('indeterminate');

    try {
        const body = { mode };
        if (mode === 'single') {
            body.qtype = qtype;
        }

        const data = await apiCall('/api/qa/generate', 'POST', body);

        // 완료 애니메이션
        progressBar.classList.remove('indeterminate');
        progressBar.style.width = '100%';
        await new Promise(resolve => setTimeout(resolve, 400));

        // 결과 표시
        resultsDiv.innerHTML = '';

        if (data.mode === 'batch') {
            data.pairs.forEach((pair, idx) => {
                resultsDiv.appendChild(createQACard(pair, idx + 1));
            });
        } else {
            resultsDiv.appendChild(createQACard(data.pair, 1));
        }
    } catch (error) {
        // Check if it's a timeout error (status 504)
        if (error.status === 504) {
            resultsDiv.innerHTML = `
                <div style="text-align: center; padding: 20px;">
                    <p style="color: var(--warning, orange); font-size: 1.2em; margin-bottom: 15px;">⏱️ 생성 시간이 초과되었습니다.</p>
                    <p style="color: var(--text-secondary, #666); margin-bottom: 20px;">LLM 서버 응답이 느립니다. 잠시 후 다시 시도해주세요.</p>
                    <button onclick="location.reload()" class="btn-primary" style="padding: 10px 20px; cursor: pointer;">새로고침</button>
                </div>`;
        } else {
            progressBar.classList.remove('indeterminate');
            resultsDiv.innerHTML = `<p style="color: var(--danger, red)">생성 실패: ${error.message}</p>`;
        }
    }
}

function createQACard(pair, index) {
    const card = document.createElement('div');
    card.className = 'result-card';

    const h3 = document.createElement('h3');
    h3.textContent = `[${index}] ${pair.type}`;

    // 질의 섹션
    const querySection = document.createElement('div');
    querySection.className = 'qa-section';

    const queryLabel = document.createElement('div');
    queryLabel.className = 'qa-label';
    const queryStrong = document.createElement('strong');
    queryStrong.textContent = '질의:';
    const copyQueryBtn = document.createElement('button');
    copyQueryBtn.className = 'copy-btn-small';
    copyQueryBtn.textContent = '📋 복사';
    copyQueryBtn.addEventListener('click', function () {
        copyToClipboard(pair.query, this);
    });
    queryLabel.appendChild(queryStrong);
    queryLabel.appendChild(copyQueryBtn);

    const queryText = document.createElement('p');
    queryText.className = 'qa-text';
    queryText.textContent = pair.query;
    querySection.appendChild(queryLabel);
    querySection.appendChild(queryText);

    // 답변 섹션
    const answerSection = document.createElement('div');
    answerSection.className = 'qa-section';

    const answerLabel = document.createElement('div');
    answerLabel.className = 'qa-label';
    const answerStrong = document.createElement('strong');
    answerStrong.textContent = '답변:';
    const copyAnswerBtn = document.createElement('button');
    copyAnswerBtn.className = 'copy-btn-small';
    copyAnswerBtn.textContent = '📋 복사';
    copyAnswerBtn.addEventListener('click', function () {
        copyToClipboard(pair.answer, this);
    });
    answerLabel.appendChild(answerStrong);
    answerLabel.appendChild(copyAnswerBtn);

    const answerText = document.createElement('pre');
    answerText.className = 'qa-text';
    answerText.textContent = pair.answer;
    answerSection.appendChild(answerLabel);
    answerSection.appendChild(answerText);

    const button = document.createElement('button');
    button.className = 'btn-secondary';
    button.textContent = '워크스페이스로 보내기 →';
    button.dataset.query = pair.query;
    button.dataset.answer = pair.answer;
    button.addEventListener('click', function () {
        sendToWorkspace(this.dataset.query, this.dataset.answer);
    });

    card.appendChild(h3);
    card.appendChild(querySection);
    card.appendChild(answerSection);
    card.appendChild(button);

    return card;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function sendToWorkspace(query, answer) {
    sessionStorage.setItem('workspace_query', query);
    sessionStorage.setItem('workspace_answer', answer);
    window.location.href = '/workspace';
}

// ============================================================================
// 외부 답변 평가
// ============================================================================

async function evaluateAnswers(query, answers) {
    showLoading('eval-results');

    try {
        const data = await apiCall('/api/eval/external', 'POST', { query, answers });

        const resultsDiv = document.getElementById('eval-results');
        resultsDiv.innerHTML = '<h3>평가 결과</h3>';

        const table = document.createElement('table');
        table.innerHTML = `
            <thead>
                <tr>
                    <th>답변</th>
                    <th>점수</th>
                    <th>피드백</th>
                </tr>
            </thead>
            <tbody>
                ${data.results.map(r => `
                    <tr class="${r.candidate_id === data.best ? 'best-answer' : ''}">
                        <td>${r.candidate_id} ${r.candidate_id === data.best ? '⭐' : ''}</td>
                        <td>${r.score}</td>
                        <td>${r.feedback}</td>
                    </tr>
                `).join('')}
            </tbody>
        `;

        resultsDiv.appendChild(table);
    } catch (error) {
        document.getElementById('eval-results').innerHTML = `<p style="color: var(--danger)">평가 실패: ${error.message}</p>`;
    }
}

// ============================================================================
// 워크스페이스
// ============================================================================

// 워크플로우 라벨 매핑 함수
function getWorkflowLabel(workflow) {
    const labels = {
        'full_generation': '🎯 전체 생성',
        'query_generation': '❓ 질의 생성',
        'answer_generation': '💡 답변 생성',
        'edit_query': '✏️ 질의 수정',
        'edit_answer': '✏️ 답변 수정',
        'edit_both': '✏️ 질의+답변 수정',
        'rewrite': '✅ 재작성/검수'
    };
    return labels[workflow] || workflow;
}

// 페이지 로드 시 세션 데이터 복원
if (window.location.pathname === '/workspace') {
    window.addEventListener('DOMContentLoaded', () => {
        const query = sessionStorage.getItem('workspace_query');
        const answer = sessionStorage.getItem('workspace_answer');

        if (query) {
            document.getElementById('query').value = query;
            sessionStorage.removeItem('workspace_query');
        }
        if (answer) {
            document.getElementById('answer').value = answer;
            sessionStorage.removeItem('workspace_answer');
        }
    });
}

async function executeWorkspace(mode, query, answer, editRequest) {
    showLoading('workspace-results');

    try {
        const body = { mode, query, answer };
        if (mode === 'edit') {
            body.edit_request = editRequest;
        }

        const data = await apiCall('/api/workspace', 'POST', body);

        const resultsDiv = document.getElementById('workspace-results');
        resultsDiv.innerHTML = '<h3>결과</h3>';

        const card = document.createElement('div');
        card.className = 'result-card';

        const resultText = data.result.fixed || data.result.edited;

        // Create elements safely using DOM methods
        const pre = document.createElement('pre');
        pre.textContent = resultText;

        const button = document.createElement('button');
        button.className = 'btn-secondary';
        button.textContent = '📋 클립보드 복사';
        button.dataset.text = resultText;
        button.addEventListener('click', function () {
            copyToClipboard(this.dataset.text, this);
        });

        card.appendChild(pre);
        card.appendChild(button);

        resultsDiv.appendChild(card);
    } catch (error) {
        document.getElementById('workspace-results').innerHTML = `<p style="color: var(--danger)">작업 실패: ${error.message}</p>`;
    }
}

// ============================================================================
// Streaming QA (SSE)
// ============================================================================

function parseSSEBuffer(buffer) {
    const events = [];
    const parts = buffer.split(/\n\n/);
    const complete = parts.slice(0, -1);
    const remainder = parts[parts.length - 1] || '';

    complete.forEach((chunk) => {
        const line = chunk.trim();
        if (!line.startsWith('data:')) return;
        const payload = line.replace(/^data:\s*/, '');
        try {
            events.push(JSON.parse(payload));
        } catch (e) {
            console.warn('Failed to parse SSE chunk', e);
        }
    });

    return { events, remainder };
}

function appendStreamResult(text) {
    const el = document.getElementById('stream-output');
    if (!el) return;
    el.textContent += text;
}

async function generateQAStream(prompt) {
    const response = await fetch('/api/qa/generate/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt }),
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parsed = parseSSEBuffer(buffer);
        buffer = parsed.remainder;

        parsed.events.forEach((evt) => {
            if (evt.text) {
                appendStreamResult(evt.text);
            }
            if (evt.error) {
                appendStreamResult(`\n[error] ${evt.error}\n`);
            }
        });
    }
}
