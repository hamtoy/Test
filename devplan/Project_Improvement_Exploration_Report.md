# 🚀 프로젝트 개선 탐구 보고서 (Improvement Exploration Report)

> 이 문서는 **현재 미적용된 개선 사항**만을 다룹니다. 이미 완료된 항목은 포함하지 않으며, 향후 진행해야 할 구체적인 작업 계획을 제시합니다.

---

<!-- AUTO-SUMMARY-START -->
## 1. 개선 요약 (Improvement Summary)

현재 프로젝트는 핵심 기능이 안정화된 단계이며, 남은 과제는 주로 **타입 안정성 강화**와 **코드 품질 최적화**에 집중되어 있습니다. 발견된 미해결 항목은 총 2건입니다.

| # | 항목명 | 우선순위 | 카테고리 |
|:---:|:---|:---:|:---|
| 1 | RAG 툴 타입 안정성 강화 | **P2** | 🧹 코드 품질 |
| 2 | 유틸리티 모듈 타입 엄격성 적용 | **OPT** | 🚀 코드 최적화 |

### 우선순위 분포

- **P2 (중요):** `qa_tools.py`의 `type: ignore` 제거 및 의존성 주입 구조 개선.
- **OPT (최적화):** `rule_parser.py` 등의 `no-any-return` 경고 해결.
<!-- AUTO-SUMMARY-END -->

---

<!-- AUTO-IMPROVEMENT-LIST-START -->
## 2. 기능 개선 항목 (Functional Improvements)

### 🟡 중요 (P2)

#### [P2-1] RAG 툴 타입 안정성 강화

| 항목 | 내용 |
|------|------|
| **ID** | `fix-type-safety-001` |
| **카테고리** | 🧹 코드 품질 |
| **복잡도** | Medium |
| **대상 파일** | `src/web/routers/qa_tools.py`, `src/qa/rag_system.py` |
| **Origin** | static-analysis |
| **리스크 레벨** | medium |
| **관련 평가 카테고리** | codeQuality |

- **현재 상태:** `qa_tools.py`에서 `CrossValidationSystem`, `GraphEnhancedRouter` 등의 클래스 초기화 시 `kg` 객체를 전달할 때 `type: ignore[arg-type]`이 다수 사용되고 있습니다.
- **문제점 (Problem):** `QAKnowledgeGraph` 클래스와 이를 받는 모듈의 타입 힌트가 일치하지 않아 타입 시스템을 우회하고 있으며, 이는 실제 데이터 불일치 시 런타임 에러로 이어질 수 있습니다.
- **영향 (Impact):** 코드의 유지보수성을 저해하고 미래의 리팩토링 시 사이드 이펙트를 예측하기 어렵게 만듭니다.
- **원인 (Cause):** `QAKnowledgeGraph` 클래스의 인터페이스나, 이를 사용하는 쪽의 타입 정의(`Optional` 처리 등)가 명확하지 않음.
- **개선 내용 (Proposed Solution):**
  - `QAKnowledgeGraph`와의 엄격한 타입 호환성 확보.
  - `type: ignore` 제거 및 올바른 타입 어노테이션 적용.
- **기대 효과:** 코드 품질 점수(A+) 달성 및 잠재적 런타임 오류 예방.

**Definition of Done:**

- [ ] `src/web/routers/qa_tools.py` 내 `type: ignore[arg-type]` 제거
- [ ] `mypy` 검사 통과
- [ ] 관련 기능 정상 동작 확인

<!-- AUTO-IMPROVEMENT-LIST-END -->

---

<!-- AUTO-FEATURE-LIST-START -->
## 3. 신규 기능 제안 (New Features)

### ✨ 기능 추가 (P3)

현재 주요 P3 항목은 발견되지 않았으나, 향후 확장을 위해 다음 기능을 고려할 수 있습니다.

#### [P3-1] 텔레메트리 대시보드 연동

| 항목 | 내용 |
|------|------|
| **ID** | `feat-telemetry-001` |
| **카테고리** | ⚙️ 운영/관제 |
| **복잡도** | High |
| **대상 파일** | `src/monitoring/metrics.py`, `src/infra/telemetry.py` |

- **제안 배경:** 현재 로그 기반 모니터링은 존재하나, 시계열 데이터(Prometheus 등) 수집 기능이 기초적인 수준임.
- **기능 내용:** 메트릭 수집기(`metrics.py`)를 고도화하여 Grafana 등과 연동 가능한 엔드포인트 제공.

<!-- AUTO-FEATURE-LIST-END -->

---

<!-- AUTO-OPTIMIZATION-START -->
## 4. 코드 최적화 (Optimization)

### 🚀 코드 최적화 (OPT-1)

#### [OPT-1] 유틸리티 모듈 타입 엄격성 적용

| 항목 | 내용 |
|------|------|
| **ID** | `opt-type-strict-001` |
| **카테고리** | 🚀 코드 최적화 / 🧹 코드 품질 |
| **영향 범위** | 품질 (타입 안정성) |
| **대상 파일** | `src/validation/rule_parser.py`, `src/monitoring/metrics.py` |

- **분석:**
  - `src/validation/rule_parser.py`: 딕셔너리 반환 시 `no-any-return` 경고를 무시(`type: ignore`)하고 있어, 반환 타입 추론이 불가능합니다.
  - `src/monitoring/metrics.py`: 클래스 재정의(`no-redef`) 경고를 무시하고 있어 코드 가독성을 해칩니다.

- **최적화 내용:**
  - `rule_parser.py`: 명시적인 `TypedDict` 또는 Pydantic 모델을 도입하여 반환 타입 명시.
  - `metrics.py`: 클래스 구조 리팩토링으로 재정의 패턴 제거.

- **예상 효과:** 전체 프로젝트의 `mypy` 검사 시간 단축 및 타입 관련 버그 원천 차단.
- **측정 지표:** `uv run mypy .` 실행 시 해당 파일에서의 에러 및 경고 0건 달성.

<!-- AUTO-OPTIMIZATION-END -->
