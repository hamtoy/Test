// ============================================================================
// 공통 함수
// ============================================================================

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
            throw new Error(error.detail || '요청 실패');
        }
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        alert('오류: ' + error.message);
        throw error;
    }
}

function showLoading(elementId) {
    const el = document.getElementById(elementId);
    el.innerHTML = '<div class="loading"></div> 처리 중...';
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        alert('클립보드에 복사되었습니다!');
    });
}

// ============================================================================
// OCR 로드
// ============================================================================

async function loadOCR() {
    try {
        const data = await apiCall('/api/ocr');
        const preview = document.getElementById('ocr-preview');
        
        if (data.ocr) {
            preview.textContent = data.ocr;
        } else {
            preview.textContent = 'OCR 파일이 없습니다.';
            preview.style.color = '#999';
        }
    } catch (error) {
        document.getElementById('ocr-preview').textContent = 'OCR 로드 실패';
    }
}

// ============================================================================
// QA 생성
// ============================================================================

async function generateQA(mode, qtype) {
    showLoading('results');

    try {
        const body = { mode };
        if (mode === 'single') {
            body.qtype = qtype;
        }

        const data = await apiCall('/api/qa/generate', 'POST', body);

        const resultsDiv = document.getElementById('results');
        resultsDiv.innerHTML = '';

        if (data.mode === 'batch') {
            data.pairs.forEach((pair, idx) => {
                resultsDiv.appendChild(createQACard(pair, idx + 1));
            });
        } else {
            resultsDiv.appendChild(createQACard(data.pair, 1));
        }
    } catch (error) {
        document.getElementById('results').innerHTML = `<p style="color: var(--danger)">생성 실패: ${error.message}</p>`;
    }
}

function createQACard(pair, index) {
    const card = document.createElement('div');
    card.className = 'result-card';
    
    card.innerHTML = `
        <h3>[${index}] ${pair.type}</h3>
        <p><strong>질의:</strong> ${pair.query}</p>
        <details>
            <summary style="cursor:pointer; color: var(--primary)">답변 보기</summary>
            <pre>${pair.answer}</pre>
        </details>
        <button class="btn-secondary" onclick="sendToWorkspace('${escapeHtml(pair.query)}', '${escapeHtml(pair.answer)}')">
            워크스페이스로 보내기 →
        </button>
    `;
    
    return card;
}

function escapeHtml(text) {
    return text.replace(/[&<>"']/g, (m) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    })[m]);
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
                    <tr class="${r.answer_id === data.best ? 'best-answer' : ''}">
                        <td>${r.answer_id} ${r.answer_id === data.best ? '⭐' : ''}</td>
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
        
        card.innerHTML = `
            <pre>${resultText}</pre>
            <button class="btn-secondary" onclick="copyToClipboard(\`${resultText.replace(/`/g, '\\`')}\`)">
                📋 클립보드 복사
            </button>
        `;

        resultsDiv.appendChild(card);
    } catch (error) {
        document.getElementById('workspace-results').innerHTML = `<p style="color: var(--danger)">작업 실패: ${error.message}</p>`;
    }
}

// ============================================================================
// 이미지 분석
// ============================================================================

async function analyzeImage(file) {
    showLoading('analysis-results');

    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/api/multimodal/analyze', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '분석 실패');
        }

        const data = await response.json();
        displayAnalysisResults(data);
    } catch (error) {
        document.getElementById('analysis-results').innerHTML = `<p style="color: var(--danger)">분석 실패: ${error.message}</p>`;
    }
}

function displayAnalysisResults(data) {
    const resultsDiv = document.getElementById('analysis-results');
    const meta = data.metadata;

    resultsDiv.innerHTML = `
        <div class="result-card">
            <h3>메타데이터</h3>
            <p><strong>파일명:</strong> ${data.filename}</p>
            <p><strong>표/그래프:</strong> ${meta.has_table_chart ? '✅' : '❌'}</p>
            <p><strong>텍스트 밀도:</strong> ${meta.text_density.toFixed(2)}</p>
            <p><strong>주요 토픽:</strong></p>
            <div style="display: flex; gap: 5px; flex-wrap: wrap; margin-top: 5px;">
                ${meta.topics.map(t => `<span style="background: var(--primary); padding: 4px 8px; border-radius: 4px; font-size: 12px;">${t}</span>`).join('')}
            </div>
        </div>

        <div class="result-card">
            <h3>추출된 텍스트</h3>
            <details>
                <summary style="cursor:pointer; color: var(--primary)">텍스트 보기</summary>
                <pre>${meta.extracted_text}</pre>
            </details>
            <button class="btn-primary" onclick="window.location.href='/qa'">
                QA 생성으로 보내기 →
            </button>
        </div>
    `;
}
