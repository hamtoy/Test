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
| 🟡 P2 | 2 |
| 🟢 P3 | 1 |
| 🚀 OPT | 2 |
| **합계** | **5** |

| # | 항목명 | 우선순위 | 카테고리 |
|:---:|:---|:---:|:---|
| 1 | 설정 파일 동시성(Lock) 제어 | P2 | 🔒 보안/안정성 |
| 2 | 대시보드 UI 단위 테스트 추가 | P2 | 🧪 테스트 |
| 3 | 프론트/백엔드 빌드 파이프라인 통합 | P3 | 📦 배포 |
| 4 | Web API 완전 비동기 I/O (aiofiles) | OPT | ⚙️ 성능 |
| 5 | LATS 워크플로우 실행 속도 최적화 | OPT | ⚙️ 성능 |

- **P1 (Critical):** 현재 서비스 중단을 야기할 치명적 결함은 없습니다.
- **P2 (High):** `config_api`의 동시성 문제 해결과 UI 컴포넌트 테스트 확보가 시급합니다.
- **P3/OPT:** 운영 편의성을 위한 빌드 통합과 고성능 처리를 위한 최적화 과제가 남아있습니다.
<!-- AUTO-SUMMARY-END -->

---

<!-- AUTO-IMPROVEMENT-LIST-START -->
## 🔧 P1 (Critical) & P2 (High) 개선 과제

> **Note:** 이전 P1/P2 과제들은 모두 완료되었습니다. P1 과제는 현재 없습니다.

### 🟡 중요 (P2)

#### [P2-1] 설정 파일 동시성(Lock) 제어

| 항목 | 내용 |
|------|------|
| **ID** | `fix-config-concurrency-001` |
| **카테고리** | 🔒 보안/안정성 |
| **복잡도** | Low |
| **대상 파일** | `src/web/routers/config_api.py`, `src/utils/file_lock.py` |
| **Origin** | static-analysis |
| **리스크 레벨** | medium |
| **관련 평가 카테고리** | errorHandling, productionReadiness |

- **현재 상태:**
  - `config_api.py`가 `settings.json` 등의 설정 파일을 직접 덮어씁니다(`write_text`).
  - 여러 사용자가 동시에 웹 대시보드에서 설정을 변경하거나, 백그라운드 프로세스가 접근할 경우 경합 조건(Race Condition)이 발생할 수 있습니다.
- **문제점 (Problem):**
  - 설정 파일 내용이 깨지거나(Corrupted), 마지막 변경사항만 적용되는 데이터 손실 위험 존재.
- **영향 (Impact):**
  - 운영 환경에서의 신뢰성 저하 및 예기치 않은 동작 오류 유발.
- **원인 (Cause):**
  - 파일 쓰기 시점의 배타적 잠금(Exclusive Lock) 메커니즘 부재.
- **개선 내용 (Proposed Solution):**
  - `fasteners` 패키지 또는 `portalocker`를 도입하여 파일 쓰기 전 락을 획득하도록 수정.
  - Context Manager(`with FileLock(...)`) 패턴 적용.
- **기대 효과:**
  - 다중 접속 환경에서도 설정 데이터의 무결성 보장.
- **Definition of Done:**
  - [ ] 파일 락 유틸리티 함수 구현 (`src/utils/file_lock.py`)
  - [ ] `config_api.py`의 쓰기 로직에 락 적용
  - [ ] 동시성 테스트(Concurrency Test) 스크립트로 데이터 무결성 검증

#### [P2-2] 대시보드 UI 단위 테스트 추가

| 항목 | 내용 |
|------|------|
| **ID** | `test-dashboard-unit-001` |
| **카테고리** | 🧪 테스트 |
| **복잡도** | Medium |
| **대상 파일** | `static/LogViewer.ts`, `static/ConfigEditor.ts`, `tests/frontend/` |
| **Origin** | manual-idea |
| **리스크 레벨** | low |
| **관련 평가 카테고리** | testCoverage |

- **현재 상태:**
  - E2E 테스트(`test_cli_flow`)는 전체 흐름을 보지만, `LogViewer`의 필터링 로직이나 `ConfigEditor`의 폼 검증 로직 같은 상세 단위 테스트는 부족합니다.
- **문제점 (Problem):**
  - UI 로직 변경 시 회귀 버그(Regression)를 E2E만으로 잡아내기에는 피드백 루프가 느리고 부정확함.
- **영향 (Impact):**
  - 프론트엔드 기능 고도화 시 개발 속도 저하.
- **원인 (Cause):**
  - 초기 개발 시 Vitest 환경이 E2E 위주로 구성됨.
- **개선 내용 (Proposed Solution):**
  - `src/static/` 내의 TS 파일들에 대한 `vitest` 단위 테스트 케이스 작성.
  - `jsdom` 환경에서 React 컴포넌트 렌더링 및 이벤트 핸들링 테스트.
- **기대 효과:**
  - UI 컴포넌트의 독립적 품질 보증 및 리팩토링 안전망 확보.
- **Definition of Done:**
  - [ ] `LogViewer.test.ts` 작성 (WebSocket 메시지 파싱 테스트)
  - [ ] `ConfigEditor.test.ts` 작성 (유효성 검증 로직 테스트)
  - [ ] `pnpm test:unit` 명령으로 통과 확인

<!-- AUTO-IMPROVEMENT-LIST-END -->

---

<!-- AUTO-P3-OPT-START -->
## ✨ P3 (Medium) & OPT (Optimization) 과제

### 🟢 P3 (Feature Additions)

#### [P3-1] 프론트/백엔드 빌드 파이프라인 통합 (`feat-build-integration-001`)

| 항목 | 내용 |
|------|------|
| **ID** | `feat-build-integration-001` |
| **카테고리** | 📦 배포 |
| **대상 파일** | `tasks.py` (또는 신규 스크립트), `pyproject.toml`, `package.json` |
| **리스크 레벨** | Low |

- **현재 상태:**
  - 백엔드 실행(`python -m src.main`)과 프론트엔드 빌드(`npm run build`)가 분리되어 있습니다.
  - 배포 시 두 과정을 각각 수동으로 수행해야 하는 약간의 불편함 존재.
- **개선 내용:**
  - 단일 명령(`python scripts/build_release.py` 등)으로 프론트엔드 빌드 -> 정적 파일 이동 -> 백엔드 패키징까지 수행하는 스크립트 작성.
- **기대 효과:**
  - CI/CD 파이프라인 단순화 및 로컬 개발 시 배포 테스트 용이성 증대.

<!-- AUTO-FEATURE-LIST-END -->

---

<!-- AUTO-OPTIMIZATION-START -->
## 🚀 코드 품질 & 성능 최적화 (OPT)

### 3-1. Web API 완전 비동기 I/O 도입 (`opt-web-async-io-002`)

| 항목 | 내용 |
|------|------|
| **ID** | `opt-web-async-io-002` |
| **카테고리** | ⚙️ 성능 튜닝 |
| **영향 범위** | 성능 / 품질 |
| **대상 파일** | `src/web/routers/logs_api.py`, `src/utils/file_io.py` |

- **현재 상태:**
  - `logs_api.py`에서 `run_in_executor`를 사용하여 블로킹을 우회하고 있지만, 이는 스레드 풀을 사용하는 방식으로 대규모 동시 접속 시 100% 효율적이지 않습니다.
- **최적화 내용:**
  - `aiofiles` 라이브러리를 도입하여 커널 레벨의 Non-blocking I/O를 활용하는 진정한 비동기 코드로 리팩토링.
  - `async for` 구문을 통한 로그 스트리밍 처리.
- **예상 효과:**
  - 스레드 컨텍스트 스위칭 오버헤드 제거 및 더 높은 동시성 처리량(Throughput) 달성.
- **측정 지표:**
  - 동시 WebSocket 연결 100개 이상 유지 시 CPU/메모리 점유율 비교.

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
