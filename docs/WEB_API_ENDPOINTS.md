# Web API Endpoints - 사용 현황 및 가이드

이 문서는 웹 API 엔드포인트의 실제 사용 현황을 명시합니다.

## 📊 엔드포인트 사용 현황 요약

| 라우터 파일 | 엔드포인트 | 웹앱 사용 | 상태 | 비고 |
|-----------|-----------|----------|------|------|
| **qa_generation.py** | POST /api/qa/generate | ✅ | 활성 | QA 페이지 메인 |
| **qa_evaluation.py** | POST /api/eval/external | ✅ | 활성 | 평가 페이지 사용 |
| **workspace_unified.py** | POST /api/workspace/unified | ✅ | 활성 | 워크스페이스 메인 |
| **workspace_generation.py** | POST /api/workspace/generate-answer | ❌ | API 전용 | 직접 호출용 |
| **workspace_generation.py** | POST /api/workspace/generate-query | ❌ | API 전용 | 직접 호출용 |
| **workspace_review.py** | POST /api/workspace | ❌ | API 전용 | 직접 호출용 |
| **health.py** | GET /api/health | ✅ | 활성 | 헬스체크 |
| **stream.py** | GET /api/stream/qa | ✅ | 활성 | 스트리밍 |

## 🌐 웹 페이지별 사용 엔드포인트

### 1. QA 생성 페이지 (`/qa`)
- **템플릿**: `templates/web/qa.html`
- **프론트엔드**: `static/dist/chunks/qa.js`
- **사용 엔드포인트**:
  - `POST /api/qa/generate` - QA 페어 생성 (qa_generation.py)
  - `GET /api/ocr` - OCR 텍스트 조회
  - `POST /api/ocr` - OCR 텍스트 저장

### 2. 평가 페이지 (`/eval`)
- **템플릿**: `templates/web/eval.html`
- **프론트엔드**: `static/dist/chunks/eval.js`
- **사용 엔드포인트**:
  - `POST /api/eval/external` - 외부 답변 3개 평가 (qa_evaluation.py)
  - `GET /api/ocr` - OCR 텍스트 조회
  - `POST /api/ocr` - OCR 텍스트 저장

### 3. 워크스페이스 페이지 (`/workspace`)
- **템플릿**: `templates/web/workspace.html`
- **프론트엔드**: `static/dist/chunks/workspace.js`
- **사용 엔드포인트**:
  - `POST /api/workspace/unified` - 통합 워크플로우 (workspace_unified.py)
  - `GET /api/ocr` - OCR 텍스트 조회
  - `POST /api/ocr` - OCR 텍스트 저장

## 🔧 API 전용 엔드포인트 (웹 UI 미사용)

다음 엔드포인트들은 웹 프론트엔드에서 호출하지 않지만, 직접 API 호출이나 테스트에서 사용됩니다:

### workspace_generation.py
```http
POST /api/workspace/generate-answer
Content-Type: application/json

{
  "query": "질문 내용",
  "ocr_text": "OCR 텍스트",
  "query_type": "explanation"
}
```

```http
POST /api/workspace/generate-query
Content-Type: application/json

{
  "answer": "답변 내용",
  "ocr_text": "OCR 텍스트",
  "query_type": "explanation"
}
```

### workspace_review.py
```http
POST /api/workspace
Content-Type: application/json

{
  "mode": "inspect",  // 또는 "edit"
  "query": "질문 내용",
  "answer": "답변 내용",
  "edit_request": "수정 요청 사항"
}
```

## 📝 아키텍처 변경 히스토리

### Workspace 통합 (v3.0+)
- **이전**: workspace_generation.py + workspace_review.py (개별 엔드포인트)
- **현재**: workspace_unified.py (WorkspaceExecutor 기반 통합)
- **이유**: 
  - 워크플로우 타입 자동 감지 (full_generation, query_generation, answer_generation, rewrite, edit_query, edit_answer, edit_both)
  - 코드 중복 제거 및 일관된 에러 처리
  - 프론트엔드 API 호출 단순화 (하나의 엔드포인트로 모든 워크플로우 처리)

### QA 평가
- **qa_evaluation.py**: 외부 답변 평가 전용 (eval 페이지)
- **qa_generation.py**: QA 페어 생성 (qa 페이지)
- 두 기능은 명확히 분리되어 각각의 페이지에서 사용됨

## ⚠️ 주의사항

### 제거 가능성이 있는 엔드포인트
workspace_generation.py와 workspace_review.py의 엔드포인트들은 웹 프론트엔드에서 사용하지 않습니다.
다만 다음 이유로 현재 유지되고 있습니다:

1. **하위 호환성**: 직접 API를 호출하는 외부 클라이언트 존재 가능성
2. **테스트 커버리지**: 기존 테스트 코드에서 사용
3. **레거시 기능**: 점진적 마이그레이션 중

### 권장사항
새로운 기능 개발 시에는 다음을 권장합니다:
- ✅ workspace 관련 기능: `/api/workspace/unified` 사용
- ✅ QA 생성: `/api/qa/generate` 사용
- ✅ 평가: `/api/eval/external` 사용

## 🔍 확인 방법

웹 프론트엔드에서 실제로 호출하는 엔드포인트를 확인하려면:

```bash
# 워크스페이스 관련 API 호출
grep -r "/api/workspace" static/dist/chunks/workspace.js

# QA 관련 API 호출
grep -r "/api/qa" static/dist/chunks/qa.js

# 평가 관련 API 호출  
grep -r "/api/eval" static/dist/chunks/eval.js
```

## 📚 관련 문서

- [ARCHITECTURE.md](ARCHITECTURE.md) - 시스템 아키텍처 전체 구조
- [API.md](API.md) - Agent/Config API 레퍼런스
- [BACKEND_REFACTORING.md](BACKEND_REFACTORING.md) - 백엔드 리팩토링 히스토리
- [TROUBLESHOOTING_422_ERRORS.md](TROUBLESHOOTING_422_ERRORS.md) - 422 에러 해결 가이드
- [VALIDATION_EXAMPLES.md](VALIDATION_EXAMPLES.md) - 프론트엔드 검증 예제
