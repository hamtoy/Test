# Fix for Truncated Gemini API Responses

## 문제 요약 (Problem Summary)

사용자가 "타입별 생성 → 타겟 장답" 모드에서 단일 답변을 생성할 때, 답변이 중간에 끊기는 문제가 발생했습니다.
예: "이러한 외환 시장 불안을 포함한 투자" ← 여기서 끝

When users generated a single answer in "Type-based generation → Target long answer" mode, 
the response was being truncated mid-sentence.
Example: "이러한 외환 시장 불안을 포함한 투자" ← cut off here

## 해결 방법 (Solution)

이 문제의 **근본 원인을 진단**하기 위한 강화된 로깅 시스템을 추가했습니다.

Added enhanced logging system to **diagnose the root cause** of this issue.

### 변경 사항 (Changes Made)

#### 1. Enhanced API Response Logging (`src/agent/client.py`)

**추가된 로깅 정보:**
- ✅ **finish_reason**: API가 왜 응답을 멈췄는지 (STOP, MAX_TOKENS, SAFETY 등)
- ✅ **응답 길이**: 문자 수와 마지막 100자 미리보기
- ✅ **MAX_TOKENS 경고**: 토큰 제한으로 잘렸을 때 경고
- ✅ **타임아웃 경고**: 요청이 타임아웃에 근접할 때 경고

**Added logging information:**
- ✅ **finish_reason**: Why the API stopped responding (STOP, MAX_TOKENS, SAFETY, etc.)
- ✅ **Response length**: Character count and last 100 characters preview
- ✅ **MAX_TOKENS warning**: Warning when truncated due to token limits
- ✅ **Timeout warning**: Warning when request approaches timeout

**로그 예시 (Example logs):**

```
# 정상 응답 (Normal response)
🔍 API Response (Gemini Native) - Finish Reason: STOP, Length: 1234 chars, Last 100 chars: ...완전한 문장으로 끝납니다.

# 토큰 제한으로 잘림 (Truncated due to MAX_TOKENS)
🔍 API Response (Gemini Native) - Finish Reason: MAX_TOKENS, Length: 1234 chars, Last 100 chars: ...포함한 투자
⚠️ Response truncated due to MAX_TOKENS limit. Response length: 1234 chars. Consider increasing max_output_tokens.

# 타임아웃 근접 (Approaching timeout)
⚠️ API request took 98.5 s, approaching timeout of 120 s. Consider increasing GEMINI_TIMEOUT.

# 안전 필터 작동 (Safety filter triggered)
❌ API Response incomplete! Finish Reason: SAFETY, Safety: [safety ratings]
```

#### 2. Debug Script (`scripts/debug_api_response.py`)

**테스트용 독립 실행 스크립트:**
- 문제가 발생한 실제 OCR 텍스트와 답변으로 테스트
- 상세한 진단 정보 출력
- 잘림 현상 자동 감지

**Standalone test script:**
- Tests with actual OCR text and answer from the bug report
- Outputs detailed diagnostic information
- Automatically detects truncation

**사용법 (Usage):**

```bash
export GEMINI_API_KEY='your-api-key-here'
python scripts/dev/debug_api_response.py
```

#### 3. Unit Tests (`tests/unit/agent/test_client_logging.py`)

**테스트 커버리지:**
- ✅ finish_reason 로깅 테스트
- ✅ MAX_TOKENS 경고 감지 테스트
- ✅ 응답 길이 추적 테스트
- ✅ 짧은 응답 처리 테스트

**Test coverage:**
- ✅ finish_reason logging tests
- ✅ MAX_TOKENS warning detection tests
- ✅ Response length tracking tests
- ✅ Short response handling tests

## 진단 방법 (How to Diagnose)

### 1. 로그 확인 (Check Logs)

```bash
# 가장 최근 생성 로그에서 finish_reason 찾기
tail -200 app.log | grep "🔍 API Response"

# 경고 메시지 찾기
tail -200 app.log | grep "⚠️"
```

**확인할 내용 (What to check):**
- `Finish Reason`이 무엇인가? (STOP이어야 정상)
- 응답 길이가 얼마나 되는가?
- 마지막 문자가 완전한 문장으로 끝나는가?

**What to check:**
- What is the `Finish Reason`? (Should be STOP for normal completion)
- What is the response length?
- Does the last character end with a complete sentence?

### 2. 디버그 스크립트 실행 (Run Debug Script)

```bash
export GEMINI_API_KEY='your-api-key'
export GEMINI_TIMEOUT=120  # 또는 더 큰 값으로 테스트

python scripts/dev/debug_api_response.py
```

**출력 결과 확인 (Check output):**
- ✅ 완료: "✅ Response appears COMPLETE"
- ⚠️ 잘림: "⚠️ WARNING: Response appears to be TRUNCATED!"

### 3. 가능한 원인 및 해결책 (Possible Causes and Solutions)

| 원인 (Cause) | finish_reason | 해결책 (Solution) |
|-------------|---------------|------------------|
| **토큰 제한 초과** | MAX_TOKENS | `.env`에서 `GEMINI_MAX_OUTPUT_TOKENS=16384`로 증가 |
| **타임아웃** | 없음 (timeout error) | `.env`에서 `GEMINI_TIMEOUT=300`으로 증가 |
| **안전 필터** | SAFETY | 프롬프트 내용 검토 또는 safety_settings 조정 |
| **API 버그** | OTHER | Gemini API 상태 확인, 재시도 |

## 환경 변수 설정 (Environment Configuration)

**.env 파일에 추가:**

```bash
# 타임아웃 증가 (기본값: 120초)
GEMINI_TIMEOUT=300  # 5분

# 최대 출력 토큰 증가 (기본값: 8192)
GEMINI_MAX_OUTPUT_TOKENS=16384
```

## 다음 단계 (Next Steps)

1. **로그 레벨을 INFO로 설정** - 새 진단 메시지 확인
   ```bash
   LOG_LEVEL=INFO
   ```

2. **문제 재현 시 로그 확인** - `🔍 API Response` 메시지에서 finish_reason 확인

3. **필요시 디버그 스크립트 실행** - 상세 진단 정보 수집

4. **결과 공유** - finish_reason과 응답 길이 정보를 이슈에 보고

## 기술 세부사항 (Technical Details)

### 변경된 파일 (Modified Files)

1. `src/agent/client.py` - Enhanced logging in `execute()` method
2. `scripts/debug_api_response.py` - New debug utility script
3. `tests/unit/agent/test_client_logging.py` - New unit tests

### 코드 품질 (Code Quality)

- ✅ All files pass `ruff format` and `ruff check`
- ✅ Syntax validation passed
- ✅ CodeQL security check passed (0 alerts)
- ✅ Code review completed and feedback addressed

### 하위 호환성 (Backward Compatibility)

- ✅ 기존 기능에 영향 없음 (로깅만 추가)
- ✅ 기존 API 시그니처 변경 없음
- ✅ 모든 테스트 통과

- ✅ No impact on existing functionality (logging only)
- ✅ No changes to existing API signatures
- ✅ All tests passing

## 도움이 필요하신가요? (Need Help?)

이슈가 계속되면 다음 정보를 공유해주세요:

If the issue persists, please share:

1. 로그의 `finish_reason` 값
2. 응답 길이 (characters)
3. 마지막 100자의 내용
4. 사용 중인 환경 변수 (GEMINI_TIMEOUT, GEMINI_MAX_OUTPUT_TOKENS)

The finish_reason and response length will help identify the exact cause!
