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
| 🔴 P1 | 1 |
| 🟡 P2 | 4 |
| 🟢 P3 | 2 |
| 🚀 OPT | 1 |
| **합계** | **8** |

| # | 항목명 | 우선순위 | 카테고리 |
|:---:|:---|:---:|:---|
| 1 | 기본 설치 경로의 선택 의존성(Neo4j) 결합 해소 | P1 | 📦 배포/의존성 |
| 2 | 최소 설치 CI 게이트 추가(옵션 미포함) | P2 | 📦 배포/CI |
| 3 | Web API 스킵 테스트 제거(더미/목 LLM 주입) | P2 | 🧪 테스트 |
| 4 | README/문서의 스크립트·실행 방법 최신화 | P2 | 📝 문서 |
| 5 | Web CORS/운영 보안 설정의 환경변수화 | P2 | 🔒 보안/배포 |
| 6 | OpenTelemetry 초기화 연결(옵션) | P3 | 📈 관측성 |
| 7 | Web에서 캐시 통계 요약 조회 엔드포인트 제공 | P3 | ✨ 기능 추가 |
| 8 | 캐시 통계(JSONL) 분석의 스트리밍 처리로 메모리 최적화 | OPT | 🚀 최적화 |

- P1: 기본 설치/실행 경로가 옵션 의존성에 의해 깨질 수 있는 리스크를 우선 제거합니다.
- P2: CI/테스트/문서/운영 설정을 정리하여 회귀 위험과 운영 비용을 낮춥니다.
- P3: 관측성과 운영 편의 기능을 확장합니다.
- OPT: 대용량 로그/통계 처리의 성능·메모리 효율을 개선합니다.
<!-- AUTO-SUMMARY-END -->

---

<!-- AUTO-IMPROVEMENT-LIST-START -->
## 📝 개선 항목 목록 (기존 기능 개선 / 미적용)

### 🔴 중요 (P1)

#### [P1-1] 기본 설치 경로의 선택 의존성(Neo4j) 결합 해소

| 항목 | 내용 |
|------|------|
| **ID** | `deps-optional-neo4j-001` |
| **카테고리** | 📦 배포/의존성 |
| **복잡도** | Medium |
| **대상 파일** | `src/cli.py`, `src/infra/neo4j_optimizer.py`, `pyproject.toml` |
| **Origin** | static-analysis |
| **리스크 레벨** | critical |
| **관련 평가 카테고리** | productionReadiness, codeQuality |

- **현재 상태:** 핵심 실행 경로에서 참조되는 CLI 모듈이 모듈 로드시 Neo4j 드라이버에 결합될 수 있는 구조가 관찰됩니다.
- **문제점 (Problem):** 기본 설치(옵션 미포함) 시 ImportError로 실행/임포트가 실패할 가능성이 있습니다.
- **영향 (Impact):** 신규 사용자 온보딩 실패, 배포 이미지 최소화 어려움, “옵션 기능”의 경계가 붕괴되어 회귀 위험이 증가합니다.
- **원인 (Cause):** 선택 의존성(Neo4j)을 사용하는 코드가 top-level import로 로드되며, 최소 설치 검증이 CI에 존재하지 않습니다.
- **개선 내용 (Proposed Solution):** Neo4j 관련 import/로직을 플래그(`--optimize-neo4j`) 실행 시점으로 지연시키고, 미설치 시 명확한 안내(필요 extras)로 폴백합니다.
- **기대 효과:** 기본 설치 안정성 확보, 옵션 기능의 경계 명확화, 배포/운영 구성 단순화.

**Definition of Done**
- [ ] 선택 의존성 import 지연/가드 구현
- [ ] 관련 테스트 추가 및 통과
- [ ] 기본 설치 경로에서 ImportError 없음
- [ ] 사용자 안내 메시지/문서 보완(필요시)

### 🟡 중요 (P2)

#### [P2-1] 최소 설치 CI 게이트 추가(옵션 미포함)

| 항목 | 내용 |
|------|------|
| **ID** | `ci-minimal-install-001` |
| **카테고리** | 📦 배포/CI |
| **복잡도** | Low |
| **대상 파일** | `.github/workflows/ci.yaml` |
| **Origin** | manual-idea |
| **리스크 레벨** | high |
| **관련 평가 카테고리** | productionReadiness, testCoverage |

- **현재 상태:** CI는 주로 dev(extra) 기반 설치를 전제하며, “기본 설치(옵션 미포함)”의 동작을 보증하는 잡이 명시적으로 존재하지 않습니다.
- **문제점 (Problem):** 선택 의존성 결합, 조건부 import 누락 등 최소 설치에서만 드러나는 결함이 누락될 수 있습니다.
- **영향 (Impact):** 릴리즈 후 사용자 환경에서만 장애가 발생하는 “환경 의존 버그” 가능성이 커집니다.
- **원인 (Cause):** 테스트/린트/타입체크가 dev 설치를 전제로 구성됨.
- **개선 내용 (Proposed Solution):** CI에 최소 설치 잡을 추가하여 base 의존성만 설치 후 핵심 모듈 임포트/헬스 체크를 수행합니다.
- **기대 효과:** 배포 품질 향상, 설치 옵션 경계 명확화, 회귀 조기 탐지.

**Definition of Done**
- [ ] 최소 설치 CI 잡 추가 및 green
- [ ] 최소 설치에서 핵심 임포트/엔트리포인트 검증
- [ ] 기존 dev 기반 잡과 충돌 없이 유지
- [ ] 문서에 최소 설치 검증 범위 명시(필요시)

#### [P2-2] Web API 스킵 테스트 제거(더미/목 LLM 주입)

| 항목 | 내용 |
|------|------|
| **ID** | `test-webapi-no-key-001` |
| **카테고리** | 🧪 테스트 |
| **복잡도** | Medium |
| **대상 파일** | `tests/test_web_api.py`, `tests/conftest.py`, `src/web/api.py` |
| **Origin** | static-analysis |
| **리스크 레벨** | medium |
| **관련 평가 카테고리** | testCoverage, productionReadiness |

- **현재 상태:** Web API 관련 테스트 중 일부가 실제 API 키/외부 호출 의존을 이유로 스킵 처리되어 있습니다.
- **문제점 (Problem):** 핵심 엔드포인트의 정상 동작(200 응답/스키마)이 CI에서 지속적으로 검증되지 못합니다.
- **영향 (Impact):** 라우터/의존성 초기화 변경 시 회귀가 늦게 발견되며, 배포 안정성이 저하됩니다.
- **원인 (Cause):** 테스트에서 LLM 호출 경로를 완전히 격리하지 못하거나, 목 주입이 일관되지 않습니다.
- **개선 내용 (Proposed Solution):** 테스트에서 `google.generativeai`/LLM 호출을 autouse 목으로 격리하고, 라우터 의존성 주입을 더미 Agent로 대체하여 스킵을 제거합니다.
- **기대 효과:** Web API 회귀 방어선 강화, 커버리지/신뢰성 개선.

**Definition of Done**
- [ ] 스킵된 Web API 테스트를 실행 가능 상태로 전환
- [ ] 외부 네트워크 호출 없이 테스트 통과
- [ ] 관련 픽스처/목의 일관성 확보
- [ ] CI에서 안정적으로 재현 가능

#### [P2-3] README/문서의 스크립트·실행 방법 최신화

| 항목 | 내용 |
|------|------|
| **ID** | `docs-scripts-sync-001` |
| **카테고리** | 📝 문서 |
| **복잡도** | Low |
| **대상 파일** | `README.md`, `docs/README_FULL.md`, `docs/CACHING.md`, `docs/ADVANCED_FEATURES.md`, `docs/MONITORING.md`, `docs/IMPROVEMENT_PROPOSAL.md` |
| **Origin** | static-analysis |
| **리스크 레벨** | medium |
| **관련 평가 카테고리** | documentation, productionReadiness |

- **현재 상태:** 문서에서 더 이상 존재하지 않는 스크립트(예: 프로파일링/캐시 워밍/비교 스크립트)를 참조하는 구간이 확인됩니다.
- **문제점 (Problem):** 문서의 실행 절차를 그대로 따라가면 실패하며, 사용자 신뢰도와 온보딩 속도가 저하됩니다.
- **영향 (Impact):** 지원 비용 증가, 잘못된 운영 방법 확산, 개선/실험 기능 활용 저하.
- **원인 (Cause):** 코드/스크립트 변경 후 문서 동기화 체계 부족.
- **개선 내용 (Proposed Solution):** 존재하는 스크립트/명령으로 문서를 재정렬하고, 삭제된 항목은 대체 경로를 제시합니다(필요 시 “현행 미지원” 명시).
- **기대 효과:** 온보딩 성공률 상승, 운영 절차의 일관성 확보.

**Definition of Done**
- [ ] 문서 내 존재하지 않는 스크립트 참조 제거/대체
- [ ] 최신 실행 명령 검증(로컬/CI 기준)
- [ ] 주요 문서 간 중복/불일치 최소화
- [ ] 변경 사항 요약 업데이트

#### [P2-4] Web CORS/운영 보안 설정의 환경변수화

| 항목 | 내용 |
|------|------|
| **ID** | `web-cors-config-001` |
| **카테고리** | 🔒 보안/배포 |
| **복잡도** | Low |
| **대상 파일** | `src/web/api.py`, `src/config/settings.py`, `docs/MONITORING.md` |
| **Origin** | static-analysis |
| **리스크 레벨** | medium |
| **관련 평가 카테고리** | security, productionReadiness |

- **현재 상태:** Web API의 CORS 허용 Origin이 코드에 고정되어 있어 환경별 설정 유연성이 제한됩니다.
- **문제점 (Problem):** 배포 환경(스테이징/프로덕션)에서 올바른 Origin 정책을 적용하기 어렵고, 변경 시 코드 수정이 필요합니다.
- **영향 (Impact):** 보안 정책 적용 지연, 잘못된 CORS 설정으로 인한 접근 제어 이슈 가능성.
- **원인 (Cause):** 운영 설정이 설정 계층(AppConfig)로 승격되지 않음.
- **개선 내용 (Proposed Solution):** `CORS_ALLOW_ORIGINS`(CSV) 등 환경변수 기반 설정으로 전환하고 기본값은 로컬로 유지하며 문서에 운영 예시를 추가합니다.
- **기대 효과:** 배포 유연성/보안성 향상, 환경 분리 명확화.

**Definition of Done**
- [ ] CORS 설정의 환경변수화 및 기본값 유지
- [ ] 관련 테스트/검증 로직 추가(필요시)
- [ ] 운영 문서에 설정 예시 추가
- [ ] CI/로컬 실행에서 동작 확인
<!-- AUTO-IMPROVEMENT-LIST-END -->

---

<!-- AUTO-FEATURE-LIST-START -->
## ✨ 기능 추가 항목 (신규 기능 / 미적용)

### 🟢 개선 (P3)

#### [P3-1] OpenTelemetry 초기화 연결(옵션)

| 항목 | 내용 |
|------|------|
| **ID** | `feat-otel-wiring-001` |
| **카테고리** | 📈 관측성 |
| **복잡도** | Medium |
| **대상 파일** | `src/infra/telemetry.py`, `src/web/api.py`, `src/infra/worker.py` |
| **Origin** | manual-idea |
| **리스크 레벨** | low |
| **관련 평가 카테고리** | productionReadiness, errorHandling |

- **현재 상태:** OpenTelemetry 헬퍼(`init_telemetry`)는 존재하지만, 기본 실행 경로에서 초기화가 연결되지 않습니다.
- **문제점 (Problem):** 운영 환경에서 트레이싱/메트릭 상관관계가 부족하여 장애 분석 시간이 증가할 수 있습니다.
- **영향 (Impact):** 성능 병목/외부 의존 오류 진단이 늦어지고, SLA 대응 비용이 상승합니다.
- **원인 (Cause):** 옵션 기능(OTLP 엔드포인트 설정)과 런타임 초기화 지점의 결합이 누락됨.
- **개선 내용 (Proposed Solution):** `OTEL_EXPORTER_OTLP_ENDPOINT` 등 환경변수 존재 시 Web/Worker 시작 시점에 `init_telemetry`를 호출하고, 미설정/미설치 시는 조용히 비활성화합니다.
- **기대 효과:** 운영 관측성 강화, 장애 분석 시간 단축, 성능/에러 원인 추적 용이.

**Definition of Done**
- [ ] Web/Worker 시작 시점 텔레메트리 초기화 연결
- [ ] 옵션 미설치/미설정 시 graceful degradation 확인
- [ ] 최소 단위 테스트/스모크 테스트 추가
- [ ] 운영 설정 예시 문서화(필요시)

#### [P3-2] Web에서 캐시 통계 요약 조회 엔드포인트 제공

| 항목 | 내용 |
|------|------|
| **ID** | `feat-web-cache-analytics-001` |
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
