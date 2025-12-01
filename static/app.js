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
// OCR 로드 및 저장
// ============================================================================

async function loadOCR() {
    try {
        const data = await apiCall('/api/ocr');
        // Support both textarea (ocr-input) and div (ocr-preview) elements
        const input = document.getElementById('ocr-input') || document.getElementById('ocr-preview');
        
        if (!input) {
            console.error('OCR element not found');
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
    const text = document.getElementById('ocr-input').value;
    const statusEl = document.getElementById('ocr-save-status');
    
    try {
        await apiCall('/api/ocr', 'POST', { text: text });
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
    
    // Create elements safely using DOM methods
    const h3 = document.createElement('h3');
    h3.textContent = `[${index}] ${pair.type}`;
    
    const p = document.createElement('p');
    const strong = document.createElement('strong');
    strong.textContent = '질의:';
    p.appendChild(strong);
    p.appendChild(document.createTextNode(' ' + pair.query));
    
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.style.cursor = 'pointer';
    summary.style.color = 'var(--primary)';
    summary.textContent = '답변 보기';
    const pre = document.createElement('pre');
    pre.textContent = pair.answer;
    details.appendChild(summary);
    details.appendChild(pre);
    
    const button = document.createElement('button');
    button.className = 'btn-secondary';
    button.textContent = '워크스페이스로 보내기 →';
    // Store data in dataset for safe access
    button.dataset.query = pair.query;
    button.dataset.answer = pair.answer;
    button.addEventListener('click', function() {
        sendToWorkspace(this.dataset.query, this.dataset.answer);
    });
    
    card.appendChild(h3);
    card.appendChild(p);
    card.appendChild(details);
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
        
        // Create elements safely using DOM methods
        const pre = document.createElement('pre');
        pre.textContent = resultText;
        
        const button = document.createElement('button');
        button.className = 'btn-secondary';
        button.textContent = '📋 클립보드 복사';
        button.dataset.text = resultText;
        button.addEventListener('click', function() {
            copyToClipboard(this.dataset.text);
        });
        
        card.appendChild(pre);
        card.appendChild(button);

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

    // Clear and rebuild using DOM methods for safety
    resultsDiv.innerHTML = '';
    
    // First result card - metadata
    const metaCard = document.createElement('div');
    metaCard.className = 'result-card';
    
    const h3Meta = document.createElement('h3');
    h3Meta.textContent = '메타데이터';
    metaCard.appendChild(h3Meta);
    
    const pFilename = document.createElement('p');
    pFilename.innerHTML = '<strong>파일명:</strong> ';
    pFilename.appendChild(document.createTextNode(data.filename));
    metaCard.appendChild(pFilename);
    
    const pTableChart = document.createElement('p');
    pTableChart.innerHTML = '<strong>표/그래프:</strong> ';
    pTableChart.appendChild(document.createTextNode(meta.has_table_chart ? '✅' : '❌'));
    metaCard.appendChild(pTableChart);
    
    const pDensity = document.createElement('p');
    pDensity.innerHTML = '<strong>텍스트 밀도:</strong> ';
    pDensity.appendChild(document.createTextNode(meta.text_density.toFixed(2)));
    metaCard.appendChild(pDensity);
    
    const pTopics = document.createElement('p');
    pTopics.innerHTML = '<strong>주요 토픽:</strong>';
    metaCard.appendChild(pTopics);
    
    const topicsDiv = document.createElement('div');
    topicsDiv.style.cssText = 'display: flex; gap: 5px; flex-wrap: wrap; margin-top: 5px;';
    meta.topics.forEach(topic => {
        const span = document.createElement('span');
        span.style.cssText = 'background: var(--primary); padding: 4px 8px; border-radius: 4px; font-size: 12px;';
        span.textContent = topic;
        topicsDiv.appendChild(span);
    });
    metaCard.appendChild(topicsDiv);
    
    resultsDiv.appendChild(metaCard);
    
    // Second result card - extracted text
    const textCard = document.createElement('div');
    textCard.className = 'result-card';
    
    const h3Text = document.createElement('h3');
    h3Text.textContent = '추출된 텍스트';
    textCard.appendChild(h3Text);
    
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.style.cssText = 'cursor: pointer; color: var(--primary);';
    summary.textContent = '텍스트 보기';
    details.appendChild(summary);
    
    const pre = document.createElement('pre');
    pre.textContent = meta.extracted_text;
    details.appendChild(pre);
    textCard.appendChild(details);
    
    const qaButton = document.createElement('button');
    qaButton.className = 'btn-primary';
    qaButton.textContent = 'QA 생성으로 보내기 →';
    qaButton.addEventListener('click', function() {
        window.location.href = '/qa';
    });
    textCard.appendChild(qaButton);
    
    resultsDiv.appendChild(textCard);
}
