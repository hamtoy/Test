# 코드 커버리지 리포트 안내

이 디렉토리에는 코드 커버리지 리뷰 결과와 관련 문서들이 포함되어 있습니다.

## 📄 주요 문서

### 1. CODE_COVERAGE_REVIEW.md
- **목적**: 전체 코드 커버리지 분석 및 통계
- **내용**: 
  - 전체 커버리지 요약 (84.97%)
  - 카테고리별 커버리지 분석
  - 우수 사례 및 개선이 필요한 모듈 목록
  - 액션 플랜

### 2. COVERAGE_IMPROVEMENT_PLAN.md
- **목적**: 구체적인 개선 계획 및 실행 가이드
- **내용**:
  - 각 우선순위별 모듈 상세 분석
  - 구체적인 테스트 코드 예제
  - 단계별 개선 방법론
  - 예상 효과 및 노력 추정

### 3. COVERAGE_REVIEW_SUMMARY.md
- **목적**: 실행 가능한 액션 플랜 및 빠른 참조
- **내용**:
  - 핵심 결과 요약
  - 즉시 실행 가능한 작업 목록
  - 성공 기준 및 체크리스트
  - 베스트 프랙티스

## 🗂️ 생성된 파일들

- `CODE_COVERAGE_REVIEW.md` - 상세 리뷰 보고서
- `COVERAGE_IMPROVEMENT_PLAN.md` - 개선 계획 및 예제
- `COVERAGE_REVIEW_SUMMARY.md` - 액션 플랜 요약
- `coverage.json` - 상세 커버리지 데이터 (JSON)
- `htmlcov/` - 인터랙티브 HTML 리포트 (브라우저로 확인 가능)

## 🚀 빠른 시작

### 커버리지 리포트 확인하기

1. **HTML 리포트 보기** (가장 직관적)
   ```bash
   open htmlcov/index.html
   # 또는
   firefox htmlcov/index.html
   ```

2. **터미널에서 확인**
   ```bash
   uv run pytest tests/ --cov=src --cov-report=term-missing
   ```

3. **특정 모듈만 확인**
   ```bash
   # 예: infra 모듈만
   uv run pytest tests/unit/infra/ --cov=src/infra --cov-report=term
   ```

### 테스트 실행하기

```bash
# 기본 테스트 실행
uv run pytest tests/

# 커버리지 포함 실행
uv run pytest tests/ --cov=src --cov-report=html

# 빠른 테스트 (병렬)
uv run pytest tests/ -n auto

# E2E 테스트 포함
uv run pytest tests/ -m ""
```

## 📊 현재 상태 요약

| 지표 | 값 |
|-----|-----|
| 전체 커버리지 | 84.97% ✅ |
| 목표 커버리지 | 80% |
| 총 라인 수 | 10,129 |
| 커버된 라인 | 8,607 |
| 누락된 라인 | 1,522 |
| 테스트 수 | 1,546 |
| 테스트 통과율 | 98.84% |

## 🎯 개선 우선순위

### 🔴 긴급 (커버리지 <50%)
1. `src/infra/structured_logging.py` - 28.00%
2. `src/qa/template_rules.py` - 28.17%
3. `src/infra/telemetry.py` - 40.94%

### 🟡 권장 (커버리지 50-70%)
4. `src/web/routers/workspace.py` - 52.30%
5. `src/agent/batch_processor.py` - 54.95%
6. 기타 4개 모듈

### 🟢 점진적 개선 (커버리지 70-80%)
- 9개 모듈 (상세 내용은 리뷰 문서 참조)

## 📅 개선 일정

- **Week 1-2**: HIGH Priority 모듈 개선 → 88% 목표
- **Week 3-4**: MEDIUM Priority 모듈 개선 → 92% 목표
- **Week 5-8**: 전체 모듈 80% 이상, 전체 95% 목표

## 🔄 정기 업데이트

이 리포트는 2주마다 업데이트됩니다.

- **최초 리뷰**: 2025-12-04
- **다음 리뷰**: 2025-12-18
- **최종 목표**: 2026-02-04

## 💡 도움말

### 커버리지가 낮은 이유 찾기

```bash
# 특정 파일의 누락된 라인 확인
uv run pytest tests/ --cov=src/infra/structured_logging.py --cov-report=term-missing

# JSON 데이터로 프로그래밍 방식 분석
python -c "
import json
with open('coverage.json') as f:
    data = json.load(f)
    for file, info in data['files'].items():
        if info['summary']['percent_covered'] < 80:
            print(f\"{file}: {info['summary']['percent_covered']:.2f}%\")
"
```

### 새로운 테스트 작성하기

COVERAGE_IMPROVEMENT_PLAN.md 파일에서 각 모듈별로 구체적인 테스트 예제를 확인할 수 있습니다.

## 📞 문의

커버리지 개선과 관련하여 질문이 있으면:
- GitHub Issue 생성
- 팀 채널에서 논의
- PR에서 코드 리뷰 요청

---

**작성일**: 2025-12-04  
**작성자**: GitHub Copilot Coding Agent
