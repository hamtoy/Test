# shining-quasar 프로젝트 개선 탐색 보고서

본 문서는 프로젝트 평가 결과를 바탕으로, 향후 수행해야 할 **미결(Pending) 개선 항목**을 정의합니다.

<!-- AUTO-SUMMARY-START -->
## 1. 전체 개선 요약

### 1.1 현재 상태

프로젝트 코드베이스 분석 결과, 다음의 미결 개선 항목이 식별되었습니다.

| 구분 | 미결 항목 수 | 상태 |
|:---:|:---:|:---:|
| **P1 (Critical)** | 0 | ✅ 항목 없음 |
| **P2 (High)** | 1 | 🔄 대기 중 |
| **P3 (Normal)** | 0 | ✅ 항목 없음 |
| **OPT (Optimization)** | 2 | 🔄 대기 중 |

### 1.2 미결 개선 항목 분포

| # | 항목명 | 우선순위 | 카테고리 | 대상 파일 |
|:---:|:---|:---:|:---|:---|
| 1 | Gemini Batch API 전체 구현 | P2 | ⚙️ 기능 완성 | `src/llm/batch.py` |
| 2 | Neo4j 배치 트랜잭션 적용 | OPT | 🚀 성능 최적화 | `src/graph/builder.py` |
| 3 | Redis 파이프라이닝 적용 | OPT | 🚀 성능 최적화 | `src/caching/redis_cache.py` |

### 1.3 식별 근거

- **Batch API stub:** `src/llm/batch.py` 코드 내 `NOTE: This is a stub implementation` 주석 확인
- **Neo4j 개별 트랜잭션:** `src/graph/builder.py`에서 개별 `session.run()` 호출 패턴 식별
- **Redis 개별 호출:** `src/caching/redis_cache.py`에서 개별 `await redis.get/set` 호출 확인

> 📝 **참고:** 적용 완료된 개선 사항의 상세 이력은 `Session_History.md`에서 확인할 수 있습니다.
<!-- AUTO-SUMMARY-END -->

<!-- AUTO-IMPROVEMENT-LIST-START -->
## 2. 기능 개선 항목 (P1/P2)

### 🟡 중요 (P2)

#### [P2-1] Gemini Batch API 전체 구현

| 항목 | 내용 |
|------|------|
| **ID** | `llm-batch-001` |
| **카테고리** | ⚙️ 기능 완성 |
| **복잡도** | Medium |
| **대상 파일** | `src/llm/batch.py` |
| **Origin** | static-analysis (코드 내 stub 주석 발견) |
| **리스크 레벨** | medium |
| **관련 평가 카테고리** | 기능 완성도, 성능/최적화 |

**현재 상태:**

`src/llm/batch.py`에 Gemini Batch API 클라이언트가 인터페이스 수준으로 구현되어 있습니다. `GeminiBatchClient` 클래스가 `submit_batch()`, `get_status()`, `get_results()`, `cancel()`, `list_jobs()` 메서드를 제공하지만, 실제 Gemini Batch API 연동은 구현되지 않았습니다.

```python
# submit_batch 메서드 내 주석
# NOTE: This is a stub implementation. Actual Gemini Batch API
# integration will be added when the API becomes available.
# See: https://ai.google.dev/gemini-api/docs/batch
```

**문제점 (Problem):**

- 현재 stub 구현으로 실제 배치 처리 불가
- 로컬 메모리(`self._jobs`) 기반 상태 관리로 프로덕션 환경 부적합
- 대량 데이터 처리 시 비용 최적화 기회 상실 (50% 비용 절감 불가)

**영향 (Impact):**

- 대량 평가, 데이터 전처리 워크로드에서 비용 효율성 저하
- 비동기 배치 작업 지원 불가로 운영 유연성 제한
- 실시간이 아닌 작업에서 불필요한 API 비용 발생

**원인 (Cause):**

- Gemini Batch API가 최근 출시되어 통합 작업 대기 상태
- 우선순위 높은 다른 기능 구현에 리소스 집중

**개선 내용 (Proposed Solution):**

1. Google AI SDK의 Batch API 클라이언트 연동
2. 배치 작업 상태 영구 저장 (Redis/DB 연동)
3. 배치 완료 시 콜백/웹훅 알림 구현
4. 비용 추적 메트릭 통합 (`cost_tracker.py` 연동)

**기대 효과:**

- 대량 처리 워크로드 비용 50% 절감
- 비동기 배치 작업 지원으로 운영 효율성 향상
- 프로덕션 수준의 상태 관리 및 장애 복구 지원

**Definition of Done:**

- [ ] Gemini Batch API 클라이언트 실제 연동
- [ ] 배치 작업 상태 영구 저장 구현 (Redis)
- [ ] 배치 완료 알림 메커니즘 구현
- [ ] 단위 테스트 추가 (`tests/unit/llm/test_batch.py` 확장)
- [ ] 통합 테스트 추가
- [ ] 비용 추적 메트릭 통합
- [ ] 문서 업데이트

<!-- AUTO-IMPROVEMENT-LIST-END -->

<!-- AUTO-FEATURE-LIST-START -->
## 3. 기능 추가 항목 (P3)

현재 미결 P3 기능 추가 항목이 없습니다.

> 🎉 P3 우선순위의 신규 기능 추가 항목은 발견되지 않았습니다. Analysis/Optimization 라우터 등 최근 추가된 기능들이 정상 동작 중입니다.
<!-- AUTO-FEATURE-LIST-END -->

<!-- AUTO-OPTIMIZATION-START -->
## 4. 코드 품질 및 성능 최적화 (OPT)

### 4.1 일반 분석 결과

코드베이스 정적 분석 결과:

- **중복 코드:** 주요 중복 없음, 유틸 함수 적절히 분리됨
- **타입 안정성:** Strict mypy 적용 완료, `any` 남용 없음
- **에러 처리:** 일관된 예외 처리 패턴 적용
- **성능 개선 여지:** Neo4j/Redis 배치 처리 최적화 가능

---

### 🚀 [OPT-1] Neo4j 배치 트랜잭션 적용

| 항목 | 내용 |
|------|------|
| **ID** | `opt-neo4j-batch-001` |
| **카테고리** | 🚀 성능 튜닝 |
| **영향 범위** | 성능 |
| **대상 파일** | `src/graph/builder.py` |
| **Origin** | static-analysis (개별 `session.run()` 호출 패턴 식별) |
| **리스크 레벨** | low |

**현재 상태:**

`src/graph/builder.py`에서 각 노드/관계 생성 시 개별 `session.run()` 호출을 수행합니다. 다수의 규칙, 제약조건, 예시를 생성할 때 약 20개 이상의 개별 트랜잭션이 발생합니다.

**최적화 내용:**

Neo4j 5.x의 `UNWIND` + 배치 파라미터 또는 `CALL {...} IN TRANSACTIONS` 구문을 활용하여 다중 노드/관계를 단일 트랜잭션으로 처리합니다.

```python
# 현재 코드 (개별 실행)
for rule_text in current_rules:
    session.run("MERGE (r:Rule {id: $id}) SET...", id=rid, text=rule_text)

# 최적화 후 (배치 실행)
session.run("""
    UNWIND $batch AS item
    MERGE (r:Rule {id: item.id})
    SET r.text = item.text
""", batch=rules_batch)
```

**예상 효과:**

- 그래프 구축 시간 30~50% 단축
- 네트워크 라운드트립 감소
- 트랜잭션 오버헤드 최소화

**측정 지표:**

- 그래프 구축 소요 시간 (before/after)
- 네트워크 요청 수
- 메모리 사용량

---

### 🚀 [OPT-2] Redis 파이프라이닝 적용

| 항목 | 내용 |
|------|------|
| **ID** | `opt-redis-pipe-001` |
| **카테고리** | 🚀 성능 튜닝 |
| **영향 범위** | 성능 |
| **대상 파일** | `src/caching/redis_cache.py` |
| **Origin** | static-analysis (개별 `await redis.get/set` 호출 식별) |
| **리스크 레벨** | low |

**현재 상태:**

`src/caching/redis_cache.py`에서 캐시 조회/저장 시 개별 `await redis.get()` 또는 `await redis.set()` 호출을 수행합니다. 다중 키 조회 시 순차적 I/O 대기가 발생합니다.

**최적화 내용:**

`redis.pipeline()`을 활용하여 다중 명령을 배치 처리합니다. 특히 `get_many()`, `set_many()` 메서드 추가를 권장합니다.

```python
# 최적화 예시
async def get_many(self, keys: list[str]) -> list[float | None]:
    async with self.redis.pipeline() as pipe:
        for key in keys:
            pipe.get(f"{self.prefix}{key}")
        return await pipe.execute()
```

**예상 효과:**

- 다중 캐시 조회 시 레이턴시 60~80% 감소
- 네트워크 I/O 효율 향상
- 동시성 처리 개선

**측정 지표:**

- 다중 키 조회 응답 시간 (before/after)
- Redis 명령 수 / 응답 시간 비율
<!-- AUTO-OPTIMIZATION-END -->
