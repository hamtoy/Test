# 🚀 프로젝트 개선 탐구 보고서 (Project Improvement Exploration Report)

> 이 문서는 `Project_Evaluation_Report.md`의 분석을 바탕으로, 현재 시급히 해결해야 할 과제 도출 및 구체적인 해결 방안을 제시합니다.
> **주의:** 이 보고서는 현재 **대기 중(Pending)**인 개선 항목만 포함하며, 이미 완료된 작업(Log Rotation, LATS 통합 등)은 포함하지 않습니다.

---

<!-- AUTO-SUMMARY-START -->
## 1. 개선 항목 요약 (Improvement Summary)

### 1-1. 전체 현황

현재 프로젝트는 핵심 기능이 대부분 구현되었으나, **API 안정성** 측면에서 하나의 중요한 과제와, 성능 효율성을 높이기 위한 하나의 최적화 과제가 남아있습니다.

| 우선순위 | 대기 중 항목 수 | 주요 키워드 |
|:---:|:---:|:---|
| 👑 **P1 (Critical)** | 0 | (없음 - 핵심 기능 안정적) |
| 🟡 **P2 (High)** | 1 | LLM API Fallback |
| 🟢 **P3 (Medium)** | 0 | (없음) |
| 🚀 **OPT (Optimization)** | 1 | 설정 로드 캐싱(Performance) |

### 1-2. 개선 항목 리스트 (Pending Items Only)

| # | 항목명 | 우선순위 | 카테고리 | ID |
|:---:|:---|:---:|:---|:---|
| 1 | **LLM Rate Limit 폴백 구현** | **P2** | 🔒 안정성 | `feat-model-fallback-001` |
| 2 | **설정 로드 최적화 (LRU Cache)** | **OPT** | ⚙️ 성능 | `opt-config-cache-001` |

<!-- AUTO-SUMMARY-END -->

---

<!-- AUTO-IMPROVEMENT-LIST-START -->
## 2. 기능 개선 항목 (Functional Improvements)

### 🟡 중요 (P2)

#### [P2-1] LLM Rate Limit 폴백(Fallback) 구현

| 항목 | 내용 |
|------|------|
| **ID** | `feat-model-fallback-001` |
| **카테고리** | 🔒 안정성 / ⚙️ 인프라 |
| **복잡도** | Medium |
| **대상 파일** | `src/llm/gemini.py` |
| **Origin** | manual-idea |
| **리스크 레벨** | Medium |
| **관련 평가 카테고리** | stability, productionReadiness |

- **현재 상태:**
  - `GeminiModelClient`는 단일 모델(`gemini-pro` 등) 설정에 의존합니다.
  - API 호출 시 `ResourceExhausted` (HTTP 429) 에러가 발생하면 즉시 실패하며, 재시도(Retry) 로직만 존재하고 모델 변경 로직은 없습니다.
  - 이로 인해 트래픽 급증 시 서비스 전체가 중단될 위험이 있습니다.

- **문제점 (Problem):**
  - "The service failed due to rate limiting" 에러 발생 시 대안이 없음.
  - 상용 서비스 수준의 SLA(가용성)를 보장하기 어려움.

- **개선 내용 (Proposed Solution):**
  1. `GeminiModelClient` 초기화 시 기본 모델 외에 `fallback_models` 리스트(예: `gemini-flash-lite-latest`)를 주입받도록 수정.
  2. `429 ResourceExhausted` 에러 발생 시, `logger.warning`을 기록하고 즉시 다음 순위 모델로 요청을 재시도.
  3. 모든 모델이 실패했을 때만 최종 예외를 발생시키도록 `generate` 메서드 래핑.

- **기대 효과:**
  - API 한도 초과 시에도 저렴/대용량 모델로 자동 전환되어 서비스 연속성 보장.
  - 시스템 신뢰성(Stability) 점수 상승.

- **Definition of Done:**
  - [ ] `GeminiModelClient`에 fallback 로직 구현 (`src/llm/gemini.py`)
  - [ ] `ResourceExhausted` 에러 시 모델 전환 테스트 케이스 작성 (`tests/unit/llm/test_gemini_fallback.py`)
  - [ ] 로깅 확인 (모델 전환 시 경고 로그 출력)

<!-- AUTO-IMPROVEMENT-LIST-END -->

---

<!-- AUTO-FEATURE-LIST-START -->
## 3. 신규 기능 추가 (New Feature Ideas)

> 현재 P3(Medium) 레벨의 신규 기능 추가 항목은 없습니다. 핵심 기능 안정화에 집중합시다.

<!-- AUTO-FEATURE-LIST-END -->

---

<!-- AUTO-OPTIMIZATION-START -->
## 4. 코드 품질 및 성능 최적화 (Optimization)

### 🚀 코드 최적화 (OPT-1)

#### [OPT-1] 설정 로드 최적화 (LRU Cache)

| 항목 | 내용 |
|------|------|
| **ID** | `opt-config-cache-001` |
| **카테고리** | ⚙️ 성능 / 🧹 유지보수 |
| **영향 범위** | 초기화 속도 및 중복 IO 제거 |
| **대상 파일** | `src/config/app_config.py` (또는 설정 로드 모듈) |

- **현재 상태:**
  - `load_config()` 함수가 호출될 때마다 `os.getenv` 및 `.env` 파일 파싱 로직이 반복 수행될 가능성이 있습니다.
  - 설정값은 런타임 중에 변경되지 않으므로, 매번 새로 읽어오는 것은 불필요한 비용입니다.

- **최적화 내용:**
  - `functools.lru_cache`를 사용하여 설정 객체를 메모리에 캐싱합니다.
  - 싱글톤 패턴과 유사한 효과를 내어, 전체 애플리케이션 수명 주기 동안 `config` 로딩을 1회로 제한합니다.

- **예상 효과:**
  - 애플리케이션 시작 시간 단축 (미세하지만 잦은 호출 시 유의미).
  - 불필요한 환경 변수 조회 오버헤드 제거.

- **측정 지표:**
  - `load_config` 1000회 반복 호출 시 소요 시간 비교 (Before vs After).

<!-- AUTO-OPTIMIZATION-END -->
