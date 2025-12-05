## 프론트엔드 개선사항 정리

### 즉시 수정 필요 (Critical)

**1. HTML 구조 오류**
- 파일: `templates/web/qa.html`
- 문제: `<script>` 블록 내부에 빈 `<style>` 태그가 있음
- 수정: `{% block scripts %}` 안의 `<style>` 태그를 제거하거나 별도 블록으로 분리

**2. 환경변수 검증 강화**
- 파일: `src/web/api.py`
- 현재: 테스트용 더미 API 키 자동 생성 (`GEMINI_API_KEY = "dummy-key-for-tests"`)
- 개선: 프로덕션 모드 감지 후 더미 키 사용 시 명시적 에러 발생
```python
if not os.getenv("GEMINI_API_KEY"):
    if os.getenv("ENVIRONMENT") == "production":
        raise ValueError("GEMINI_API_KEY required in production")
    os.environ["GEMINI_API_KEY"] = "dummy-key-for-tests"
```

### 개발 경험 개선 (High Priority)

**3. 타입 안전성 추가**
- 현재: JavaScript만 사용, 타입 체크 없음
- 옵션 1: JSDoc 주석으로 타입 힌트 추가
- 옵션 2: TypeScript 마이그레이션 (.ts 확장자로 점진적 전환)
```javascript
// JSDoc 예시
/**
 * @param {string} mode - 생성 모드 ('batch' | 'single')
 * @param {string|null} qtype - 질문 타입
 * @returns {Promise<void>}
 */
async function generateQA(mode, qtype) { ... }
```

**4. 빌드 도구 도입**
- 현재: ES6 모듈을 브라우저에서 직접 로드
- 문제: 구형 브라우저 호환성, 번들 최적화 부재
- 권장: Vite 또는 esbuild 설정
```bash
# Vite 기본 설정 예시
npm init vite@latest frontend -- --template vanilla
```

### 테스트 및 품질 (Medium Priority)

**5. 프론트엔드 테스트 추가**
- 현재: E2E/단위 테스트 없음
- 권장 도구:
  - 단위 테스트: Vitest
  - E2E 테스트: Playwright
```javascript
// Vitest 예시
import { describe, it, expect } from 'vitest';
import { escapeHtml, formatAnswer } from './qa.js';

describe('QA 유틸리티', () => {
  it('HTML 이스케이프 처리', () => {
    expect(escapeHtml('<script>alert("xss")</script>'))
      .toBe('&lt;script&gt;alert("xss")&lt;/script&gt;');
  });
});
```

**6. 에러 바운더리 강화**
- 파일: `static/qa.js`, `static/workspace.js`
- 현재: try-catch로 기본 에러 처리
- 개선: 전역 에러 핸들러 추가, 재시도 로직 구현
```javascript
// utils.js에 추가
export function withRetry(fn, maxRetries = 3) {
  return async (...args) => {
    for (let i = 0; i < maxRetries; i++) {
      try {
        return await fn(...args);
      } catch (error) {
        if (i === maxRetries - 1) throw error;
        await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)));
      }
    }
  };
}
```

### 성능 최적화 (Low Priority)

**7. 코드 스플리팅**
- 현재: 모든 JS 파일이 각 페이지에서 로드
- 개선: 동적 import로 필요한 모듈만 로드
```javascript
// 지연 로딩 예시
async function loadWorkspaceFeatures() {
  const { initWorkspace } = await import('./workspace.js');
  initWorkspace();
}
```

**8. CSS 최적화**
- 파일: `static/style.css` (15KB)
- 개선: 사용하지 않는 스타일 제거, Critical CSS 분리
- 도구: PurgeCSS 또는 Vite의 CSS 코드 스플리팅

### 접근성 개선 (Low Priority)

**9. ARIA 레이블 보완**
- 현재: 일부 대화형 요소에 레이블 누락
- 개선 대상:
  - `templates/web/qa.html`의 라디오 버튼 그룹에 `role="radiogroup"` 추가
  - 동적 콘텐츠 영역에 `aria-live` 속성 추가
```html
<div role="radiogroup" aria-labelledby="mode-label">
  <span id="mode-label" class="sr-only">생성 모드 선택</span>
  <label><input type="radio" ...> 4타입 일괄 생성</label>
</div>
```

**10. 키보드 네비게이션 강화**
- 진행 중인 작업 취소를 위한 ESC 키 핸들러
- 결과 카드 간 화살표 키 네비게이션
```javascript
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && isGenerating) {
    cancelGeneration();
  }
});
```

***

### 우선순위 요약
1. **즉시**: HTML 구조 오류 수정, 환경변수 검증
2. **단기** (1-2주): 타입 안전성, 빌드 도구
3. **중기** (1-2개월): 테스트 추가, 에러 처리 강화
4. **장기**: 성능 최적화, 접근성 개선

개인 사용 목적이므로 1-2번 항목만 처리해도 충분하며, 향후 확장 시 3-4번을 순차적으로 적용하시면 됩니다.