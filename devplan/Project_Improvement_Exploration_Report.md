# shining-quasar 프로젝트 개선 탐색 보고서

본 문서는 프로젝트 평가 결과를 바탕으로, 향후 수행해야 할 **미결(Pending) 개선 항목**을 정의합니다. 이미 완료된 항목은 제외하고, 문서화, 운영 안정성, 보안 관점에서 우선순위를 조정하였습니다.

<!-- AUTO-SUMMARY-START -->
## 1. 전체 개선 요약

현재 프로젝트는 핵심 기능 구현과 모니터링 스택 구축을 완료한 상태입니다. 남은 개선 사항은 API 문서 자동화, 모니터링 알림 설정, 보안 자동화에 집중되어 있습니다.

### 1.1 미결 개선 항목 현황

| # | 항목명 | 우선순위 | 카테고리 |
|:---:|:---|:---:|:---|
| 1 | API 문서 자동화 | **P2** | 📚 문서화 |
| 2 | 모니터링 알림 설정 | **P2** | ⚙️ 운영 |
| 3 | 보안 스캔 CI 통합 | **P3** | 🔒 보안 |
| 4 | 외부 의존성 모킹 개선 | **P3** | 🧪 테스트 |
| 5 | CLI 도움말 개선 | **OPT** | 🛠️ UX |

### 1.2 우선순위 분포

- **P1 (Critical):** 0건 - 현재 크리티컬한 장애 요소 없음
- **P2 (High):** 2건 - 문서화, 운영 안정성 개선
- **P3 (Normal):** 2건 - 보안, 테스트 인프라 개선
- **OPT (Optimization):** 1건 - 사용성 최적화
<!-- AUTO-SUMMARY-END -->

<!-- AUTO-IMPROVEMENT-LIST-START -->
## 2. 기능 개선 항목 (P1/P2)

### 🟡 중요 (P2)

#### [P2-1] API 문서 자동화 (API Documentation Automation)

| 항목 | 내용 |
|:---:|:---|
| **ID** | `doc-api-auto-001` |
| **카테고리** | 📚 문서화 / 🔧 DX |
| **복잡도** | Medium |
| **대상 파일** | `src/web/docs.py` (new), `docs/api/` (new) |
| **Origin** | manual-idea |
| **리스크 레벨** | medium |
| **관련 평가 카테고리** | 문서화 (85점 → 목표 92점) |

- **현재 상태:** FastAPI의 자동 OpenAPI 스펙 생성 기능이 있으나, 별도의 정적 문서 사이트가 없어 API 레퍼런스 접근성이 낮음.
- **문제점 (Problem):** 개발자가 API 사용법을 파악하기 위해 코드를 직접 확인해야 하며, 버전 관리된 문서가 없어 변경 추적이 어려움.
- **영향 (Impact):** 외부 개발자 온보딩 시간 증가, API 변경 시 클라이언트 측 혼란 가능성.
- **원인 (Cause):** 초기 개발 시 기능 구현에 집중하여 문서화 자동화 파이프라인 미구축.
- **개선 내용 (Proposed Solution):**
  1. OpenAPI 스펙을 마크다운으로 변환하는 스크립트 작성
  2. `docs/api/` 디렉토리에 버전별 API 문서 생성
  3. 각 엔드포인트에 상세 설명 및 예제 추가
- **기대 효과:** 문서화 점수 7점 상승 예상, 개발자 온보딩 시간 50% 단축.

**Definition of Done:**

- [ ] OpenAPI to Markdown 변환 스크립트 구현
- [ ] `docs/api/v3.0.0.md` 문서 생성 완료
- [ ] 빌드 시 자동 문서 생성 파이프라인 구축
- [ ] README에 API 문서 링크 추가

---

#### [P2-2] 모니터링 알림 설정 (Alerting Configuration)

| 항목 | 내용 |
|:---:|:---|
| **ID** | `ops-alerting-001` |
| **카테고리** | ⚙️ 운영 / 📊 모니터링 |
| **복잡도** | Low |
| **대상 파일** | `grafana/provisioning/alerting/` (new), `prometheus.yml` (update) |
| **Origin** | manual-idea |
| **리스크 레벨** | medium |
| **관련 평가 카테고리** | 운영 준비도 (92점 → 목표 96점) |

- **현재 상태:** Prometheus/Grafana 모니터링 스택이 구축되어 메트릭 수집 및 시각화가 가능하나, 알림 규칙이 설정되지 않음.
- **문제점 (Problem):** 장애 발생 시 대시보드를 직접 확인해야만 인지 가능하여 대응 속도가 느림.
- **영향 (Impact):** MTTR(Mean Time To Recovery) 증가, 야간 장애 미감지 위험.
- **원인 (Cause):** 모니터링 스택 구축 후 알림 규칙 설정 작업이 후순위로 밀림.
- **개선 내용 (Proposed Solution):**
  1. Grafana 알림 규칙 정의 (에러율 > 5%, 레이턴시 > 5s)
  2. Slack/Email 알림 채널 설정
  3. 프로비저닝 파일을 통한 알림 규칙 코드화
- **기대 효과:** 운영 준비도 점수 4점 상승, 장애 인지 시간 90% 단축.

**Definition of Done:**

- [ ] `grafana/provisioning/alerting/rules.yaml` 생성
- [ ] 에러율, 레이턴시, 시스템 리소스 알림 규칙 정의
- [ ] 알림 채널 설정 및 테스트 완료
- [ ] 문서에 알림 설정 가이드 추가
<!-- AUTO-IMPROVEMENT-LIST-END -->

<!-- AUTO-FEATURE-LIST-START -->
## 3. 기능 추가 항목 (P3)

### 🟢 권장 (P3)

#### [P3-1] 보안 스캔 CI 통합 (Security Scanning CI Integration)

| 항목 | 내용 |
|:---:|:---|
| **ID** | `sec-ci-scan-001` |
| **카테고리** | 🔒 보안 / 🔧 CI/CD |
| **복잡도** | Low |
| **대상 파일** | `.github/workflows/security.yml` (new) |
| **Origin** | static-analysis |
| **리스크 레벨** | low |
| **관련 평가 카테고리** | 보안 (88점 → 목표 93점) |

- **현재 상태:** `pyproject.toml`에 Bandit, Safety 도구가 dev 의존성으로 설정되어 있으나, CI 파이프라인에 통합되어 있지 않음.
- **문제점 (Problem):** 보안 취약점이 있는 코드가 PR 리뷰 없이 병합될 가능성 존재.
- **영향 (Impact):** 잠재적인 보안 취약점이 프로덕션에 배포될 위험.
- **개선 내용 (Proposed Solution):**
  1. GitHub Actions 워크플로우에 Bandit 정적 분석 추가
  2. Safety를 통한 의존성 취약점 검사 자동화
  3. PR 시 보안 검사 결과를 코멘트로 리포트
- **기대 효과:** 보안 점수 5점 상승 예상, 배포 전 보안 취약점 자동 감지.

**Definition of Done:**

- [ ] `.github/workflows/security.yml` 워크플로우 생성
- [ ] Bandit 정적 분석 단계 추가
- [ ] Safety 의존성 검사 단계 추가
- [ ] PR 실패 조건 설정 (critical 취약점 시)

---

#### [P3-2] 외부 의존성 모킹 개선 (External Dependency Mocking)

| 항목 | 내용 |
|:---:|:---|
| **ID** | `test-mocking-001` |
| **카테고리** | 🧪 테스트 / 🔧 인프라 |
| **복잡도** | Medium |
| **대상 파일** | `tests/conftest.py`, `tests/fixtures/` (new) |
| **Origin** | test-failure |
| **리스크 레벨** | low |
| **관련 평가 카테고리** | 테스트 커버리지 (93점 → 목표 95점) |

- **현재 상태:** 일부 통합 테스트가 실제 Neo4j, Redis 연결에 의존하여 CI 환경에서 불안정하게 동작.
- **문제점 (Problem):** 외부 서비스 상태에 따라 테스트가 간헐적으로 실패(Flaky Test).
- **영향 (Impact):** CI 신뢰성 저하, 개발자 생산성 감소.
- **개선 내용 (Proposed Solution):**
  1. pytest-mock 기반의 Neo4j/Redis 클라이언트 모킹 fixture 생성
  2. 통합 테스트용 fakeredis, neo4j-embedded 도입 검토
  3. 테스트 마커를 통한 외부 의존성 테스트 분리
- **기대 효과:** 테스트 점수 2점 상승, CI 안정성 대폭 개선.

**Definition of Done:**

- [ ] `tests/fixtures/mock_neo4j.py` 픽스처 생성
- [ ] `tests/fixtures/mock_redis.py` 픽스처 생성
- [ ] 기존 통합 테스트에 모킹 적용
- [ ] `@pytest.mark.requires_neo4j` 마커 일관성 있게 적용
<!-- AUTO-FEATURE-LIST-END -->

<!-- AUTO-OPTIMIZATION-START -->
## 4. 코드 품질 및 성능 최적화 (OPT)

### 일반 분석

현재 코드베이스 분석 결과 다음 최적화 기회가 식별되었습니다:

- **CLI 사용성:** `src/cli.py`의 도움말 메시지가 간결하지 않아 사용자 경험 개선 여지
- **중복 코드:** 일부 유틸리티 함수들이 여러 모듈에서 유사하게 구현됨
- **타입 안정성:** 대부분 strict mode 적용 완료, 스크립트 폴더는 예외 처리 중

### 🚀 코드 최적화 (OPT-1)

#### [OPT-1] CLI 도움말 개선 (CLI Help Enhancement)

| 항목 | 내용 |
|:---:|:---|
| **ID** | `ux-cli-help-001` |
| **카테고리** | 🛠️ UX / 📝 문서 |
| **영향 범위** | 사용자 경험 |
| **대상 파일** | `src/cli.py` |

- **현재 상태:** CLI 도움말이 기본 argparse 형식으로 제공되어 사용자 친화적이지 않음.
- **최적화 내용:**
  1. Rich 라이브러리를 활용한 컬러풀한 도움말 출력
  2. 주요 명령어에 대한 사용 예제 추가
  3. 서브커맨드별 그룹화된 도움말 구조
- **예상 효과:** 사용자 온보딩 경험 향상, 문서 없이도 CLI 사용 가능.
- **측정 지표:** 사용자 피드백 수집 또는 도움말 조회 빈도 분석.

**Definition of Done:**

- [ ] Rich 기반 도움말 포맷터 구현
- [ ] 각 명령어에 예제 추가
- [ ] `--help` 출력 테스트 케이스 추가

---

### 🚀 코드 최적화 (OPT-2)

#### [OPT-2] 캐싱 레이어 가시성 개선 (Caching Layer Visibility)

| 항목 | 내용 |
|:---:|:---|
| **ID** | `opt-cache-metrics-001` |
| **카테고리** | ⚙️ 성능 / 📊 모니터링 |
| **영향 범위** | 성능 + 운영 |
| **대상 파일** | `src/caching/`, `src/monitoring/metrics.py` |

- **현재 상태:** 캐싱 레이어가 구현되어 있으나, 캐시 히트율/미스율 메트릭이 노출되지 않음.
- **최적화 내용:**
  1. 캐시 히트/미스 카운터 메트릭 추가
  2. 캐시 키 통계 수집 (인기 키, 만료 빈도)
  3. Grafana 대시보드에 캐싱 성능 패널 추가
- **예상 효과:** 캐시 효율성 모니터링으로 최적 TTL 설정 가능, 불필요한 캐시 미스 감소.
- **측정 지표:** 캐시 히트율 모니터링 (`cache_hit_ratio` 메트릭).

**Definition of Done:**

- [ ] `CACHE_HIT_TOTAL`, `CACHE_MISS_TOTAL` Prometheus 메트릭 추가
- [ ] 캐싱 모듈에서 메트릭 수집 로직 구현
- [ ] Grafana 대시보드에 캐싱 패널 추가
<!-- AUTO-OPTIMIZATION-END -->
