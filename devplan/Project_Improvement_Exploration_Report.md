# shining-quasar 프로젝트 개선 탐색 보고서

본 문서는 프로젝트 평가 결과를 바탕으로, 향후 수행해야 할 **미결(Pending) 개선 항목**을 정의합니다. 이미 완료된 항목은 제외하고, 안정성, 확장성, 문서화 관점에서 우선순위를 재조정하였습니다.

<!-- AUTO-SUMMARY-START -->
## 1. 전체 개선 요약

현재 프로젝트는 핵심 기능이 완성단계에 도달했으나, 운영 관점의 모니터링 수단과 사용자 문서가 부족합니다. 또한, 그래프 쿼리 성능을 장기적으로 확보하기 위한 최적화가 필요합니다.

### 1.1 미결 개선 항목 현황 (Pending Items)

| # | 항목명 | 우선순위 | 카테고리 | 상태 |
|:---:|:---|:---:|:---:|:---:|
| 1 | 텔레메트리 대시보드 구축 | **P2** (중요) | ⚙️ Ops | ⬜ Pending |
| 2 | Neo4j 쿼리 성능 최적화 | **OPT** | ⚙️ 성능 | ⬜ Pending |
| 3 | 사용자 매뉴얼 작성 | **P3** (권장) | 📚 문서 | ⬜ Pending |

### 1.2 우선순위 분포

- **P1 (Critical):** 없음 (현재 크리티컬한 장애 요소는 해소됨)
- **P2 (High):** 1건 (텔레메트리 연동)
- **P3 (Normal):** 1건 (문서화)
- **OPT (Optimization):** 1건 (쿼리 최적화)
<!-- AUTO-SUMMARY-END -->

<!-- AUTO-IMPROVEMENT-LIST-START -->
### 🟡 중요 (P2)

#### [P2-1] 텔레메트리 대시보드 구축 (Telemetry Integration)

| 항목 | 내용 |
|:---:|:---|
| **ID** | `feat-telemetry-001` |
| **카테고리** | ⚙️ Ops / 📊 모니터링 |
| **복잡도** | Medium |
| **대상 파일** | `src/monitoring` (new), `src/config/settings.py` |
| **Origin** | manual-idea |
| **리스크 레벨** | medium |
| **관련 평가 카테고리** | 운영/안정성 (Stability) |

- **현재 상태:** `metrics.py`를 통해 Prometheus 포맷의 메트릭은 생성하고 있으나, 이를 시각화하거나 중앙에서 수집하는 대시보드 설정이 부재합니다.
- **문제점 (Problem):** 운영 중 실시간 API 호출량, 에러율, 레이턴시 등을 한눈에 파악하기 어렵습니다. 문제 발생 시 로그 파일(`server.log`)을 직접 열어봐야 하는 비효율이 존재합니다.
- **영향 (Impact):** 장애 인지 속도 저하 및 성능 병목 구간 식별 곤란.
- **원인 (Cause):** 초기 개발 단계에서 기능 구현에 집중하느라 모니터링 스택(Grafana/Prometheus 등) 통합이 지연되었습니다.
- **개선 내용 (Proposed Solution):**
  1. `docker-compose.yml`에 Prometheus 및 Grafana 컨테이너 추가.
  2. `src/monitoring` 모듈에 시스템 메트릭(CPU/Memory) 수집 로직 추가.
  3. Grafana 기본 대시보드 템플릿(JSON) 생성.
- **기대 효과:** 실시간 장애 감지 가능, 데이터 기반의 성능 튜닝 가능.

**Definition of Done:**

- [ ] `docker-compose.yml`에 모니터링 스택 정의
- [ ] Grafana 대시보드 프로비저닝 설정 완료
- [ ] 애플리케이션 실행 시 메트릭 수집 정상 확인
<!-- AUTO-IMPROVEMENT-LIST-END -->

<!-- AUTO-FEATURE-LIST-START -->
### 🟢 권장 (P3)

#### [P3-1] 사용자 매뉴얼 작성 (User Documentation)

| 항목 | 내용 |
|:---:|:---|
| **ID** | `doc-user-manual-001` |
| **카테고리** | 📚 문서 / 🧑‍💻 DX |
| **복잡도** | Low |
| **대상 파일** | `docs/user_manual.md` (new), `README.md` |
| **Origin** | manual-idea |
| **리스크 레벨** | low |
| **관련 평가 카테고리** | 문서화 (Documentation) |

- **현재 상태:** 개발자 대상의 기술 문서는 존재하나, 최종 사용자가 시스템을 어떻게 활용해야 하는지에 대한 가이드는 부족합니다.
- **개선 내용:**
  1. `docs/user_manual.md` 생성.
  2. 설치, 설정, 기본 질의 예제, 에러 트러블슈팅 가이드 포함.
- **기대 효과:** 사용자 온보딩 시간 단축 및 운영 문의 감소.
<!-- AUTO-FEATURE-LIST-END -->

<!-- AUTO-OPTIMIZATION-START -->
## 3. 코드 품질 및 성능 최적화 (OPT)

### 🚀 코드 최적화 (OPT-1)

#### [OPT-1] Neo4j 쿼리 성능 최적화 (Query Optimization)

| 항목 | 내용 |
|:---:|:---|
| **ID** | `opt-query-perf-001` |
| **카테고리** | ⚙️ 성능 튜닝 / 🚀 최적화 |
| **영향 범위** | 성능 (Graph RAG 속도) |
| **대상 파일** | `src/graph/query_builder.py` |

- **현재 상태:** 현재 구현된 Cypher 쿼리 생성 로직은 단순 매칭 위주이며, 인덱스를 효율적으로 활용하지 못하는 경우가 있습니다.
- **최적화 내용:**
  1. `query_builder.py`에서 생성하는 Cypher 쿼리에 `USING INDEX` 힌트 추가 검토.
  2. 자주 조회되는 노드 속성에 대한 인덱스 생성 스크립트(`scripts/setup_indexes.cypher`) 추가.
  3. 불필요한 `OPTIONAL MATCH` 줄이기.
- **예상 효과:** 복잡한 그래프 질의 시 응답 속도 20~30% 향상 예상.
- **측정 지표:** `metrics.py`에 기록되는 `rag_query_latency` 평균값.
<!-- AUTO-OPTIMIZATION-END -->
