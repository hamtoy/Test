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
| 🚀 OPT | 1 |
| **합계** | **4** |

| # | 항목명 | 우선순위 | 카테고리 |
|:---:|:---|:---:|:---|
| 1 | Web API 스킵 테스트 제거(더미/목 LLM 주입) | P2 | 🧪 테스트 |
| 2 | README/문서의 스크립트·실행 방법 최신화 | P2 | 📝 문서 |
| 3 | 설정 파일(`settings.py`) 분리 및 모듈화 | P3 | 🧹 코드 품질 |
| 4 | 동기식 파일 I/O(`open`, `read_text`)의 비동기 전환 | OPT | 🚀 최적화 |

- **P1 (Critical):** 현재 크리티컬한 배포/실행 차단 요인은 **모두 해소**되었습니다.
- **P2 (High):** 테스트 신뢰성 확보와 문서 정확도 개선이 주요 과제입니다.
- **P3/OPT:** 코드 유지보수성과 고부하 상황에서의 I/O 안정성을 확보합니다.
<!-- AUTO-SUMMARY-END -->

---

<!-- AUTO-IMPROVEMENT-LIST-START -->
## 📝 개선 항목 목록 (기존 기능 개선 / 미적용)

<!-- AUTO-P1-P2-START -->
## 🔧 P1 (Critical) & P2 (High) 개선 과제

### 1-1. Web API 스킵 테스트 제거 (`test-webapi-no-key-001`)

- **분류:** 🧪 테스트 / **난이도:** 중 / **리스크:** Medium
- **대상 파일:** `tests/test_web_api.py`, `tests/conftest.py`
- **발견 경로:** `coverage` 분석 및 `pytest` 실행 결과 (`s` 마킹 확인)
- **현재 상태:**
  - `TestQAGeneration`, `TestWorkspace` 등 핵심 기능 테스트가 LLM 키/복잡한 모킹 문제로 `@pytest.mark.skip` 처리됨.
- **문제점:**
  - Web API의 핵심 로직(검증/파이프라인 연결)이 변경되어도 CI가 통과해버림(False Positive).
- **해결 방안:**
  - `MockAgent`, `MockPipeline`을 정교하게 구성하여 LLM 없이도 라우터의 요청/응답 스키마와 데이터 흐름을 검증하도록 개선.
- **기대 효과:**
  - Web API 테스트 커버리지 100% 신뢰성 확보, CI 안정망 강화.
- **Definition of Done:**
  - [ ] `pytest tests/test_web_api.py` 실행 시 스킵되는 테스트가 0건이어야 함.
  - [ ] 모킹된 응답으로 정상적인 JSON 구조가 반환되는지 검증.

### 1-2. 문서/스크립트 동기화 (`docs-scripts-sync-001`)

- **분류:** 📝 문서 / **난이도:** 하 / **리스크:** Low
- **대상 파일:** `README.md`, `docs/*.md`, `scripts/`
- **발견 경로:** `scripts/` 디렉토리 내용과 문서 간 불일치
- **현재 상태:**
  - `auto_profile.py`, `compare_runs.py` 등이 리팩토링 과정에서 제거/이동되었으나 문서에는 잔재가 남음.
- **문제점:**
  - 신규 개발자나 운영자가 문서대로 실행했다가 `FileNotFoundError` 등으로 혼란을 겪음.
- **해결 방안:**
  - `scripts/`의 현행 스크립트 전수 조사 및 용도 파악.
  - `README.md`의 "Troubleshooting" 및 "Scripts" 섹션 최신화.
- **기대 효과:**
  - 온보딩 경험 개선 및 문서 신뢰도 회복.
- **Definition of Done:**
  - [ ] `README.md` 내의 모든 `python scripts/...` 명령어가 실제 작동하거나 경로가 수정됨.
  - [ ] 존재하지 않는 스크립트에 대한 언급 삭제.
<!-- AUTO-P1-P2-END -->

---

<!-- AUTO-P3-OPT-START -->
## ✨ P3 (Medium) & OPT (Optimization) 과제

### 2-1. 설정 파일 분리 및 모듈화 (`refactor-settings-split-001`)

- **분류:** 🧹 코드 품질 / **난이도:** 중 / **리스크:** Low
- **대상 파일:** `src/config/settings.py`
- **발견 경로:** 정적 분석(복잡도) 및 코드 리뷰
- **현재 상태:**
  - `AppConfig` 하나의 클래스에 LLM, DB(Neo4j/Redis), Web(CORS), Path, CI 등 모든 설정이 집중됨 (500+ lines).
- **문제점:**
  - 설정 추가/변경 시 영향 범위 파악이 어렵고, 테스트(`test_config.py`) 작성 시 과도한 환경변수 모킹이 필요.
- **해결 방안:**
  - `LLMSettings`, `DatabaseSettings`, `WebSettings` 등으로 Pydantic 모델 분리.
  - `AppConfig`는 이들을 조합(Composition)하는 형태로 리팩토링.
- **기대 효과:**
  - 설정 그룹별 명확한 책임 분리 및 유닛 테스트 용이성 증대.
- **Definition of Done:**
  - [ ] `src/config/settings.py`의 라인 수가 200라인 이하로 감소.
  - [ ] 기존 환경변수(`NEO4J_URI` 등)가 그대로 호환됨을 검증.

### 2-2. Web API 동기식 파일 I/O 제거 (`opt-async-file-io-001`)

- **분류:** 🚀 최적화 / **난이도:** 중 / **리스크:** Low
- **대상 파일:** `src/web/utils.py`, `src/web/routers/ocr.py`
- **발견 경로:** 코드 리뷰 (Async 핸들러 내 Blocking Call)
- **현재 상태:**
  - `api_save_ocr` 등 비동기 핸들러에서 `path.write_text` 등 블로킹 I/O를 직접 호출하거나 `open(..., 'w')`를 사용.
- **문제점:**
  - 동시 접속량이 늘어나거나 디스크 I/O가 지연될 경우, FastAPI의 이벤트 루프 전체가 멈춰 처리량(Throughput) 급감.
- **해결 방안:**
  - `aiofiles` 라이브러리를 도입하거나, `asyncio.to_thread` / `loop.run_in_executor`로 블로킹 구간 격리.
- **기대 효과:**
  - 고부하 상황에서도 안정적인 응답 속도 유지.
- **Definition of Done:**
  - [ ] `src/web/routers/ocr.py` 및 `utils.py` 내 파일 조작 로직이 비동기(`await`)로 전환됨.
  - [ ] 부하 테스트(간이) 시 에러 없이 동작 확인.

| **카테고리** | ✨ 기능 추가 |
| **복잡도** | Medium |
| **대상 파일** | `src/caching/analytics.py`, `src/web/routers/*`, `src/web/api.py` |
| **Origin** | manual-idea |
| **리스크 레벨** | medium |
| **관련 평가 카테고리** | productionReadiness, performance |

- **현재 상태:** 캐시 통계 분석은 CLI/유틸 함수로 제공되지만, Web에서 즉시 확인할 수 있는 API가 기본 제공되지는 않습니다.
- **목적/사용자 가치:** 운영자가 대시보드/모니터링 도구에서 캐시 hit-rate/절감액 요약을 즉시 조회할 수 있습니다.
- **의존성:** `cache_stats.jsonl`(또는 설정된 경로) 접근 권한, Web 라우터/템플릿 구조.
- **구현 전략(제안):** `GET /api/cache/summary` 형태로 요약 JSON을 반환하고(필요 시 pages 라우터에 간단한 HTML 뷰 추가), 파일 미존재/파싱 실패 시 명확한 오류 코드를 반환합니다.
- **평가 지표 연계:** 운영 편의/관측성 향상 → 프로덕션 준비도 및 성능 분석 역량 개선.

**Definition of Done**

- [ ] 캐시 요약 API 라우터 추가 및 응답 스키마 고정
- [ ] 파일 미존재/빈 파일/잘못된 JSONL 케이스 테스트
- [ ] 기존 기능(CLI 분석)과 결과 일관성 확인
- [ ] 문서에 엔드포인트/예시 추가(필요시)
<!-- AUTO-FEATURE-LIST-END -->

---

<!-- AUTO-OPTIMIZATION-START -->
## 🚀 코드 품질 & 성능 최적화 (OPT / 미적용)

### 🔎 일반 분석(요약)

- 중복 코드 및 유틸 함수로 추출 가능한 부분(패키지 간 유사 기능 중복 포함)
- 타입 안정성 강화 필요 구간(옵션 의존성 경계에서의 import/예외 처리 등)
- 가독성을 해치는 복잡한 함수/파일(초기화/의존성 주입/라우팅 결합 지점)
- 에러 처리 로직이 부족하거나 일관되지 않은 부분(운영 설정/옵션 기능 폴백의 가시성)
- 불필요한 연산, 비효율적인 I/O 처리(대용량 JSONL/로그 분석 등)

### 🚀 코드 최적화 (OPT-1)

| 항목 | 내용 |
|------|------|
| **ID** | `opt-cache-stats-stream-001` |
| **카테고리** | 🚀 코드 최적화 |
| **영향 범위** | 성능/품질(둘 다) |
| **대상 파일** | `src/caching/analytics.py`, `tests/test_caching_analytics.py` |

- **현재 상태:** `analyze_cache_stats`가 JSONL을 모두 리스트로 적재한 뒤 집계하여, 파일이 커질수록 메모리 사용량이 선형으로 증가합니다.
- **최적화 내용:** 레코드 적재 없이 스트리밍으로 집계(total hits/misses/records/savings)를 계산하고, 파싱 실패 라인은 카운트/스킵하도록 개선합니다.
- **예상 효과:** 대용량 통계 파일에서도 안정적 동작(메모리 상수화), 처리 시간 단축, 운영 환경에서 OOM 위험 감소.
- **측정 지표:** 동일 입력 파일 기준 (1) 최대 RSS, (2) 처리 시간, (3) 결과 값 동일성(회귀 테스트) 비교.
<!-- AUTO-OPTIMIZATION-END -->
