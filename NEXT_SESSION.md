# Next Session: Phase 5-7 (Optional)

## 현재 상태 (2025-11-28) ✅

- ✅ v3.0.0 릴리스 완료
- ✅ 테스트 100% 통과 (520/520)
- ✅ mypy strict 에러 0개
- ✅ 완벽한 타입 안정성 달성
- ✅ 27개 shim 파일 제거 완료
- ✅ 14개 모듈화된 패키지 구조

## 선택적 개선 항목

### Phase 5: 테스트 커버리지 90%+ (선택사항)

현재: ~84% → 목표: 90%+

우선순위 패키지:

- `src/features/` (커버리지 낮음)
- `src/analysis/` (복잡한 로직)
- `src/routing/` (엣지 케이스)

#### 예상 작업

```bash
# 현재 커버리지 확인
uv run pytest tests/ --cov=src --cov-report=html

# HTML 리포트 열기
start htmlcov/index.html  # Windows
open htmlcov/index.html   # macOS/Linux
```

작업 흐름:

- 주차별 1-2개 패키지 집중
- 엣지 케이스 위주 테스트 추가
- pyproject.toml fail_under 85 → 90 상향

예상 시간: 세션 3-4회 (각 1-2시간)

### Phase 6: 성능 최적화 (선택사항)

벤치마크 수립:

```bash
# 현재 성능 측정
python scripts/auto_profile.py src.main --mode AUTO \
  --ocr-file example_ocr.txt --cand-file example_candidates.json

# 레이턴시 베이스라인
python scripts/latency_baseline.py --log-file app.log

# Neo4j 성능 점검
python scripts/neo4j_benchmark_stub.py
```

최적화 타겟:

1. **Redis 캐싱**
   - Hit rate 목표: 70%+
   - TTL 최적화

2. **LLM API 호출**
   - 배치 처리 개선
   - 병렬 처리 최적화 (current: 5 → 10?)
   - 프롬프트 토큰 효율화

3. **벡터 검색**
   - 인덱스 최적화
   - 쿼리 성능 튜닝

목표 메트릭:

- p50 latency: -20% 감소
- p90 latency: -30% 감소
- 토큰 효율: +15% 개선

예상 시간: 세션 2-3회 (각 2-3시간)

### Phase 7: UI/UX 개선 (선택사항)

Rich 콘솔 강화:

- 진행 상황 대시보드 (Progress, Table, Panel 통합)
- 실시간 메트릭 표시
- 컬러 스키마 개선

대화형 CLI:

- 인터랙티브 선택 메뉴
- 키보드 단축키
- 자동 완성 개선

결과 시각화:

- 비용 추이 그래프
- 캐시 효율 차트
- 토큰 사용량 통계

예상 시간: 세션 2회 (각 2시간)

## 📋 요약

| Phase | 우선순위 | 예상 시간 | 설명 |
|-------|---------|----------|------|
| Phase 5 | 선택 | 2-3주 | 테스트 커버리지 90%+ |
| Phase 6 | 선택 | 1-2주 | 성능 최적화 |
| Phase 7 | 선택 | 1주 | UI/UX 개선 |

> **참고**: v3.0.0은 완료된 상태입니다. 위 Phase들은 모두 선택적 개선 항목입니다.
