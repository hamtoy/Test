# 🚨 422 에러 해결 가이드 (Unprocessable Content)

## 📌 문제 상황

API 요청 시 다음과 같은 에러가 발생하는 경우:

```
❌ 요청 데이터 검증 실패
HTTP 422 Unprocessable Content
```

**422 에러** = **Request Body 검증 실패**

FastAPI의 Pydantic 모델이 요청 데이터를 검증했지만 실패한 경우입니다.

---

## 🎯 주요 원인 3가지

### 원인 1: 필수 필드 누락

#### ✅ 올바른 요청 (`/api/qa/generate`)
```javascript
{
  "mode": "single",
  "ocr_text": "마이크로소프트 주가...",
  "qtype": "explanation"
}
```

#### ❌ 잘못된 요청 (필드 누락)
```javascript
{
  "mode": "single"
  // ocr_text, qtype 누락!
}
```

**결과**: `422 Unprocessable Content` - `qtype` 필드 누락

---

### 원인 2: 필드명 오타 (camelCase ❌ vs snake_case ✅)

#### ✅ 올바른 필드명 (snake_case)
```javascript
{
  "mode": "single",
  "ocr_text": "...",        // ✓ ocr_text (snake_case)
  "qtype": "explanation",   // ✓ qtype
  "batch_types": [...]      // ✓ batch_types (snake_case)
}
```

#### ❌ 잘못된 필드명 (camelCase → 422 에러!)
```javascript
{
  "mode": "single",
  "ocrText": "...",         // ❌ "ocr_text" 아님
  "queryType": "...",       // ❌ "query_type" 아님 (workspace API)
  "batchTypes": [...]       // ❌ "batch_types" 아님
}
```

**문제**: FastAPI는 정확한 필드명(snake_case)을 기대하므로 422 에러 발생

---

### 원인 3: 데이터 타입 오류

#### ✅ 올바른 타입
```javascript
{
  "mode": "single",         // string ✓
  "ocr_text": "텍스트...",   // string ✓
  "qtype": "explanation",   // string ✓
  "batch_types": ["reasoning", "explanation"]  // array of strings ✓
}
```

#### ❌ 잘못된 타입 (422 에러!)
```javascript
{
  "mode": 123,              // number ❌ (string 필요)
  "ocr_text": null,         // null ❌ (string 필요)
  "qtype": ["explanation"], // array ❌ (string 필요)
  "batch_types": "reasoning" // string ❌ (array 필요)
}
```

---

## 🛠️ 프론트엔드 자동 검증 (v3.1+)

**v3.1부터 프론트엔드에서 자동으로 요청 데이터를 검증합니다.**

### 사용 방법

```typescript
import { validateRequest, ValidationError } from "./validation.js";

// API 요청 전 검증
try {
    const payload = {
        mode: "single",
        ocr_text: ocrText,
        qtype: "explanation"
    };

    // 자동 검증
    validateRequest(payload, "/api/qa/generate");

    // 검증 통과 → API 호출
    const result = await apiCall("/api/qa/generate", "POST", payload);
} catch (error) {
    if (error instanceof ValidationError) {
        // 검증 실패 → 사용자에게 명확한 에러 메시지 표시
        showToast(`요청 검증 실패: ${error.message}`, "error");
    }
}
```

### 자동 검증 기능

1. **필드명 검증**: camelCase → snake_case 오타 자동 감지
2. **타입 검증**: 모든 필드의 데이터 타입 확인
3. **필수 필드 검증**: 누락된 필수 필드 확인
4. **유효 값 검증**: enum 타입 필드의 값 확인

---

## 🔎 DevTools로 디버깅

### Step 1: Network 탭 확인

1. DevTools 열기 (F12)
2. Network 탭 선택
3. API 요청 버튼 클릭
4. POST 요청 선택

### Step 2: Request Payload 확인

**올바른 형식 (`/api/qa/generate`)**:
```json
{
  "mode": "single",
  "ocr_text": "마이크로소프트 주가...",
  "qtype": "explanation"
}
```

**잘못된 형식 (필드명 오타)**:
```json
{
  "mode": "single",
  "ocrText": "...",      // ❌ camelCase
  "qtype": "explanation"
}
```

### Step 3: Response 확인

#### ✅ 성공 응답 (200)
```json
{
  "success": true,
  "data": {
    "mode": "single",
    "pair": {
      "type": "explanation",
      "query": "한국 증시 전망은?",
      "answer": "한국 증시 전망에 대해..."
    }
  }
}
```

#### ❌ 실패 응답 (422)
```json
{
  "detail": [
    {
      "loc": ["body", "qtype"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**해석**:
- `loc`: 어느 필드가 문제인지 → `body.qtype`
- `msg`: 무엇이 문제인지 → `field required` (필드 누락)
- `type`: 에러 유형 → `value_error.missing`

---

## 📋 API별 요청 형식

### 1. `/api/qa/generate` (QA 생성)

#### Single 모드
```typescript
{
  mode: "single",           // 필수: "single" | "batch" | "batch_three"
  ocr_text: string,         // 선택: OCR 텍스트
  qtype: string             // 필수 (single): "global_explanation" | "reasoning" | "target_short" | "target_long"
}
```

#### Batch 모드
```typescript
{
  mode: "batch",            // 필수
  ocr_text: string,         // 선택
  batch_types: string[]     // 선택: 커스텀 타입 배열
}
```

### 2. `/api/workspace/unified` (워크스페이스)

```typescript
{
  mode: string,                      // 선택: "full" | "query-only" | "answer-only"
  query: string | null,              // 선택
  answer: string | null,             // 선택
  edit_request: string | null,       // 선택
  ocr_text: string | null,           // 선택
  query_type: string | null,         // 선택: "global_explanation" | "reasoning" | "target_short" | "target_long"
  global_explanation_ref: string | null  // 선택
}
```

**⚠️ 주의**: 모든 필드명은 **snake_case** 사용!

---

## ✅ 체크리스트

### 요청 전 확인사항

- [ ] 필드명이 **snake_case**인가? (camelCase 금지)
- [ ] 필수 필드가 모두 포함되어 있는가?
- [ ] 모든 필드의 데이터 타입이 올바른가?
- [ ] null/undefined 값이 없는가? (또는 허용되는 필드인가?)
- [ ] enum 타입 필드의 값이 유효한가?

### 디버깅 단계

1. [ ] DevTools Network 탭에서 Request Payload 확인
2. [ ] 필드명에 오타가 없는지 확인 (특히 snake_case vs camelCase)
3. [ ] Response에서 정확한 에러 필드 확인 (`detail[].loc`)
4. [ ] 콘솔에서 프론트엔드 검증 에러 메시지 확인
5. [ ] 백엔드 로그에서 Validation Error 상세 내용 확인

---

## 🔧 백엔드 모델 참고

### GenerateQARequest (Pydantic 모델)

```python
class GenerateQARequest(BaseModel):
    mode: Literal["batch", "batch_three", "single"] = "batch"
    ocr_text: Optional[str] = None
    qtype: Optional[Literal["global_explanation", "reasoning", "target_short", "target_long"]] = None
    batch_types: Optional[List[Literal["global_explanation", "reasoning", "target_short", "target_long"]]] = None
```

### UnifiedWorkspaceRequest (Pydantic 모델)

```python
class UnifiedWorkspaceRequest(BaseModel):
    query: Optional[str] = ""
    answer: Optional[str] = ""
    edit_request: Optional[str] = ""
    ocr_text: Optional[str] = None
    query_type: Optional[Literal["global_explanation", "reasoning", "target_short", "target_long"]] = None
    global_explanation_ref: Optional[str] = None
    use_lats: bool = True
```

---

## 🎯 일반적인 해결 방법

### 1. 필드명 확인 (2분)
```typescript
// ❌ 잘못된 예
{ ocrText: "...", queryType: "..." }

// ✅ 올바른 예
{ ocr_text: "...", query_type: "..." }
```

### 2. 타입 확인 (1분)
```typescript
// ❌ 잘못된 예
{ mode: 123, qtype: ["explanation"] }

// ✅ 올바른 예
{ mode: "single", qtype: "explanation" }
```

### 3. 필수 필드 확인 (1분)
```typescript
// ❌ single 모드인데 qtype 누락
{ mode: "single", ocr_text: "..." }

// ✅ qtype 포함
{ mode: "single", ocr_text: "...", qtype: "explanation" }
```

---

## 💡 예방 팁

1. **TypeScript 사용**: 타입 체크로 컴파일 시점에 오류 감지
2. **자동 검증 사용**: `validateRequest()` 함수 사용
3. **상수 활용**: 하드코딩 대신 상수로 필드명/값 관리
4. **테스트 작성**: API 요청 형식을 검증하는 유닛 테스트 작성
5. **린트 설정**: snake_case 규칙 적용

---

## 📞 문제 지속 시

1. **DevTools에서 정확한 Request body 캡처**
2. **Response에서 `detail` 배열의 에러 메시지 확인**
3. **백엔드 로그에서 Validation Error 메시지 확인**
4. **어느 필드가 문제인지 파악 (`loc` 필드 참고)**
5. **GitHub Issue 생성 (요청/응답 포함)**

---

## 🔗 관련 문서

- [Web API Endpoints](./WEB_API_ENDPOINTS.md) - API 엔드포인트 상세 가이드
- [Pydantic Models](../src/web/models.py) - 백엔드 요청/응답 모델
- [Frontend Validation](../static/validation.ts) - 프론트엔드 검증 헬퍼

---

**예상 해결 시간**: 2-5분  
**난이도**: ⭐ (매우 쉬움)  
**효과**: 422 에러 예방 + 명확한 에러 메시지 ✅
