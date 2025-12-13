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
| 1 | GitHub Actions 기반 CI 자동화 | P2 | 📦 배포/DevOps |
| 2 | LLM Rate Limit 모델 폴백(Fallback) | P3 | ✨ 기능 추가 |
| 3 | FileLock 모듈 타입 안정성 강화 | OPT | 🧹 코드 품질 |
| 4 | 서버 로그 로테이션(Rotation) 적용 | OPT | ⚙️ 성능/운영 |

- **P1 (Critical):** 현재 긴급한 장애 요인은 없습니다.
- **P2 (High):** 로컬 스크립트로 동작하는 빌드/테스트 과정을 **CI 파이프라인(GitHub Actions)**으로 이관하여 자동화해야 합니다.
- **P3/OPT:** 운영 안정성을 위한 로그 관리와 타입 시스템의 엄격함을 되찾는 최적화 작업이 필요합니다.
<!-- AUTO-SUMMARY-END -->

---

<!-- AUTO-IMPROVEMENT-LIST-START -->
## 🔧 P1 (Critical) & P2 (High) 개선 과제

> **Note:** 이전 P1/P2 과제들은 모두 완료되었습니다. P1 과제는 현재 없습니다.

### 🟡 중요 (P2)

#### [P2-1] GitHub Actions 기반 CI 자동화

| 항목 | 내용 |
|------|------|
| **ID** | `feat-ci-workflow-001` |
| **카테고리** | 📦 배포/DevOps |
| **복잡도** | Medium |
| **대상 파일** | `.github/workflows/ci.yml` |
| **Origin** | manual-idea |
| **리스크 레벨** | medium |
| **관련 평가 카테고리** | productionReadiness |

- **현재 상태:**
  - `python -m pytest` 및 `npm run build` 등의 검증 과정이 로컬 개발자 환경에 의존적입니다.
  - `build_release.py`가 추가되었으나 이를 자동 실행하는 파이프라인이 없습니다.
- **문제점 (Problem):**
  - PR 병합 시 테스트가 누락되거나, 환경 차이로 인한 빌드 오류 발생 가능성.
- **영향 (Impact):**
  - 메인 브랜치의 안정성 저하 및 배포 프로세스의 인적 오류 위험.
- **원인 (Cause):**
  - 자동화된 CI/CD 워크플로우(`yaml`) 부재.
- **개선 내용 (Proposed Solution):**
  - GitHub Actions 워크플로우(`.github/workflows/ci.yml`) 작성.
  - Push 및 PR 이벤트 발생 시 백엔드 테스트(`pytest`)와 프론트엔드 빌드 검증 수행.
- **기대 효과:**
  - 코드 변경에 대한 즉각적인 피드백 루프 확보 및 배포 신뢰도 상승.
- **Definition of Done:**
  - [ ] `.github/workflows/ci.yml` 파일 생성
  - [ ] Python 3.10+ 환경 설정 및 의존성 설치 스텝 구현
  - [ ] `pytest` 및 `npm run build` (또는 `build_release.py`) 실행 성공 단계 추가

<!-- AUTO-IMPROVEMENT-LIST-END -->

---

<!-- AUTO-P3-OPT-START -->
## ✨ P3 (Medium) & OPT (Optimization) 과제

### 🟢 P3 (Feature Additions)

#### [P3-1] LLM Rate Limit 모델 폴백(Fallback) (`feat-model-fallback-001`)

| 항목 | 내용 |
|------|------|
| **ID** | `feat-model-fallback-001` |
| **카테고리** | ✨ 기능 추가 |
| **대상 파일** | `src/llm/gemini_client.py` |
| **리스크 레벨** | Low |

- **현재 상태:**
  - `429 Too Many Requests` 발생 시 단순 Retry만 수행하며, 할당량이 소진된 경우 실패합니다.
- **개선 내용:**
  - `gemini-pro` 사용 불가 시 `gemini-flash` 등 하위 모델로 자동 전환하는 로직 구현.
  - `FallbackStrategy` 클래스 설계.
- **기대 효과:**
  - API 제한 상황에서도 서비스 연속성 보장.

<!-- AUTO-FEATURE-LIST-END -->

---

<!-- AUTO-OPTIMIZATION-START -->
## 🚀 코드 품질 & 성능 최적화 (OPT)

### 3-1. FileLock 모듈 타입 안정성 강화 (`opt-type-strictness-001`)

| 항목 | 내용 |
|------|------|
| **ID** | `opt-type-strictness-001` |
| **카테고리** | 🧹 코드 품질 |
| **영향 범위** | 품질 |
| **대상 파일** | `src/infra/file_lock.py`, `pyproject.toml` |

- **현재 상태:**
  - `msvcrt`(Windows) 및 `fcntl`(Unix) 모듈이 특정 OS에만 존재하여 `mypy` 검사 시 `import-error`가 발생.
  - 현재는 `type: ignore`와 `pyproject.toml`의 `warn_unused_ignores = false` 옵션으로 경고를 억제 중입니다.
- **최적화 내용:**
  - `sys.platform` 분기에 따라 조건부 타입 정의(`Protocol` 또는 `stub` 파일)를 적용.
  - `Any` 타입 사용을 줄이고 명시적인 타입 힌트 적용.
- **예상 효과:**
  - 타입 시스템의 엄격함 회복 및 잠재적 타입 오류 사전 방지.
- **측정 지표:**
  - `mypy` 실행 시 `warn_unused_ignores = true` 상태에서 에러 0건 달성.

### 3-2. 서버 로그 로테이션(Rotation) 적용 (`opt-log-rotation-001`)

| 항목 | 내용 |
|------|------|
| **ID** | `opt-log-rotation-001` |
| **카테고리** | ⚙️ 성능/운영 |
| **대상 파일** | `src/infra/logging.py` |

- **현재 상태:**
  - 로그 파일이 단일 파일(`app.log`)에 계속 누적되어, 장기 운영 시 디스크 용량 문제 및 분석 어려움 발생 가능.
- **최적화 내용:**
  - `RotatingFileHandler` 또는 `TimedRotatingFileHandler`를 도입하여, 파일 크기(예: 10MB) 또는 날짜 기준으로 로그 분할.
  - 오래된 로그 자동 삭제 정책 적용.
- **예상 효과:**
  - 디스크 공간 고갈 방지 및 로그 파일 접근 속도 유지.

<!-- AUTO-OPTIMIZATION-END -->
