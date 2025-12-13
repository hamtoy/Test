# 🚀 프로젝트 개선 탐색 보고서

> 이 문서는 Vibe Coding Report VS Code 확장에서 자동으로 관리됩니다.  
> **적용된 개선 항목은 자동으로 필터링되어 미적용 항목만 표시됩니다.**

---

## 📋 프로젝트 정보

| 항목 | 값 |
|------|-----|
| **프로젝트명** | shining-quasar |
| **최초 분석일** | 2025-12-06 01:11 |

---

## 📌 사용 방법

1. 이 보고서의 개선 항목을 검토합니다
2. 적용하고 싶은 항목을 복사합니다
3. AI 에이전트(Copilot Chat 등)에 붙여넣어 구현을 요청합니다
4. 다음 보고서 업데이트 시 적용된 항목은 자동으로 제외됩니다

---

<!-- AUTO-SUMMARY-START -->
## 📊 개선 현황 요약 (미적용 항목만)

| 우선순위 | 남은 개수 |
|:---:|:---:|
| 🔴 P1 | 0 |
| 🟡 P2 | 1 |
| 🟢 P3 | 1 |
| 🚀 OPT | 2 |
| **합계** | **4** |

| # | 항목명 | 우선순위 | 카테고리 |
|:---:|:---|:---:|:---|
| 1 | 전체 워크플로우 E2E 테스트 구축 | P2 | 🧪 테스트 |
| 2 | 대시보드 UI 고도화 (상세 제어) | P3 | ✨ 기능 |
| 3 | Web API 동기 파일 I/O 비동기 전환 | OPT | ⚙️ 성능 |
| 4 | LATS 워크플로우 실행 속도 최적화 | OPT | ⚙️ 성능 |

- **P1 (Critical):** 현재 크리티컬한 배포/실행 차단 요인은 **없습니다**.
- **P2 (High):** 전체 시스템을 관통하는 E2E 테스트 확보가 시급합니다.
- **P3/OPT:** Web API와 LATS의 성능을 최적화하고 UI 편의성을 높이는 작업이 남았습니다.
<!-- AUTO-SUMMARY-END -->

---

<!-- AUTO-IMPROVEMENT-LIST-START -->
## 🔧 P1 (Critical) & P2 (High) 개선 과제

> **Note:** 이전 P1/P2 과제들은 모두 완료되었습니다.

### 🟡 중요 (P2)

#### [P2-1] 전체 워크플로우 E2E 테스트 구축

| 항목 | 내용 |
|------|------|
| **ID** | `test-e2e-001` |
| **카테고리** | 🧪 테스트 |
| **복잡도** | Medium |
| **대상 파일** | `tests/e2e/`, `src/workflow/` |
| **Origin** | manual-idea |
| **리스크 레벨** | medium |
| **관련 평가 카테고리** | testCoverage, productionReadiness |

- **현재 상태:**
  - 단위 테스트(`Vitest`, `pytest`)는 풍부하지만, 실제 CLI 실행부터 결과 생성까지의 전체 흐름을 검증하는 E2E 테스트가 부재함.
- **문제점 (Problem):**
  - 개별 모듈은 정상이어도, 실제 실행 환경에서 설정 로딩이나 파일 I/O 등이 꼬일 경우 감지하지 못함.
- **영향 (Impact):**
  - 배포 후 통합 오류 발생 가능성 존재.
- **원인 (Cause):**
  - 모킹(Mocking) 위주의 테스트 전략만 수립됨.
- **개선 내용 (Proposed Solution):**
  - `subprocess`를 활용하여 실제 `python -m src.main` 명령을 실행하고 종료 코드와 출력을 검증하는 테스트 스크립트 작성.
- **기대 효과:**
  - 배포 전 최종 안전장치 확보 및 통합 무결성 보장.
- **Definition of Done:**
  - [ ] `tests/e2e` 디렉토리 생성 및 테스트 스크립트 작성
  - [ ] CLI 정상 종료 및 출력 파일 생성 여부 검증
  - [ ] CI 파이프라인에 E2E 단계 추가

<!-- AUTO-IMPROVEMENT-LIST-END -->

---

<!-- AUTO-P3-OPT-START -->
## ✨ P3 (Medium) & OPT (Optimization) 과제

### 🟢 P3 (Feature Additions)

#### [P3-1] 대시보드 UI 고도화 (`feat-ui-dashboard-advanced`)

| 항목 | 내용 |
|------|------|
| **ID** | `feat-ui-dashboard-advanced` |
| **카테고리** | ✨ 기능 추가 |
| **대상 파일** | `src/web/`, `packages/frontend/` |
| **리스크 레벨** | Low |

- **현재 상태:**
  - 기본 대시보드와 메뉴 UI는 존재하나, 실시간 로그 스트리밍이나 상세 설정(Config) 편집 기능이 부족함.
- **개선 내용:**
  - 웹 UI에서 `settings.py`의 주요 파라미터를 직접 수정하고 저장하는 기능 추가.
  - 실행 로그를 실시간으로 웹소켓을 통해 조회하는 기능 구현.
- **기대 효과:**
  - CLI에 익숙하지 않은 운영자도 쉽게 시스템을 제어 가능.

<!-- AUTO-FEATURE-LIST-END -->

---

<!-- AUTO-OPTIMIZATION-START -->
## 🚀 코드 품질 & 성능 최적화 (OPT)

### 3-1. Web API 동기 파일 I/O 비동기 전환 (`opt-web-async-io-001`)

| 항목 | 내용 |
|------|------|
| **ID** | `opt-web-async-io-001` |
| **카테고리** | ⚙️ 성능 튜닝 |
| **영향 범위** | 성능 / 확장성 |
| **대상 파일** | `src/web/routers/`, `src/utils/file_io.py` |

- **현재 상태:**
  - `async def` 라우터 내부에서 표준 `open()`이나 `Path.read_text()`를 사용하여 파일 I/O를 수행.
  - 이는 이벤트 루프를 차단(Block)하여, 트래픽 증가 시 전체 API 응답성을 저하시킴.
- **최적화 내용:**
  - `aiofiles` 라이브러리를 도입하거나 `run_in_executor` 패턴을 적용하여 Non-blocking I/O로 전환.
- **예상 효과:**
  - 동시 접속자 수 증가 시에도 안정적인 응답 속도 유지.
- **측정 지표:**
  - `locust` 등을 이용한 부하 테스트 시 99th percentile 응답 시간.

### 3-2. LATS 워크플로우 실행 속도 최적화 (`opt-lats-performance-001`)

| 항목 | 내용 |
|------|------|
| **ID** | `opt-lats-performance-001` |
| **카테고리** | 🚀 알고리즘 최적화 |
| **대상 파일** | `src/lats/search.py`, `src/agent/gemini.py` |

- **현재 상태:**
  - 트리 탐색(Tree Search) 시 노드 확장이 순차적으로 이루어지거나, 불필요하게 많은 토큰을 소모하는 프롬프트 구조.
- **최적화 내용:**
  - 자식 노드 생성 시 `asyncio.gather`를 활용한 병렬 요청 처리.
  - 중간 평가 단계에서 프롬프트 Context Window를 절약하는 요약 기법 적용.
- **예상 효과:**
  - 복잡한 질의에 대한 자기 교정 소요 시간 30% 이상 단축.

<!-- AUTO-OPTIMIZATION-END -->
