# 캐싱 전략 가이드 (Caching)

Gemini API 캐싱 전략, TTL 설정, 비용 분석에 대한 상세 가이드입니다.

---

## 📊 캐싱 개요

Gemini API는 2048 토큰 이상의 프롬프트에 대해 컨텍스트 캐싱을 지원합니다. 이를 통해 반복적인 API 호출 비용을 크게 절감할 수 있습니다.

### 최소 토큰 요구사항

```python
# Gemini API 제약 - 변경 불가
MIN_CACHE_TOKENS = 2048
```

> **참고**: 2048 토큰 미만의 프롬프트는 캐싱되지 않습니다.

---

## ⚙️ 캐싱 설정

### 환경 변수

```bash
# .env
GEMINI_CACHE_SIZE=50           # 캐시 항목 수
GEMINI_CACHE_TTL_MINUTES=360   # 기본 TTL (6시간)
GEMINI_CACHE_MIN_TOKENS=2048   # 최소 토큰 (고정)
```

### TTL 전략

용도에 따라 다른 TTL을 적용하면 비용 효율성을 높일 수 있습니다:

| 프롬프트 유형 | 권장 TTL | 이유 |
|---------------|----------|------|
| 시스템 프롬프트 | 1시간 (3600초) | 거의 변경되지 않음 |
| 평가 프롬프트 | 30분 (1800초) | 세션 동안 재사용 |
| 생성 프롬프트 | 15분 (900초) | 짧은 수명 |

```bash
# 권장 TTL 설정
CACHE_TTL_SYSTEM=3600
CACHE_TTL_EVALUATION=1800
CACHE_TTL_GENERATION=900
```

---

## 💰 비용 분석

### 가격 구조

Gemini 3 Pro Preview 모델 기준 (1M 토큰당 USD):

| 입력 토큰 범위 | 입력 비용 | 출력 비용 |
|----------------|-----------|-----------|
| ≤ 200,000 | $2.00 | $12.00 |
| > 200,000 | $4.00 | $18.00 |

### 캐시 히트 시 절감

캐시 히트 시 입력 토큰 비용이 **25% 절감**됩니다.

**예시 계산:**

| 시나리오 | 입력 토큰 | 캐시 | 비용 |
|----------|-----------|------|------|
| 첫 호출 | 10,000 | Miss | $0.020 |
| 두 번째 호출 | 10,000 | Hit | $0.005 (75% 절감) |

### 비용 절감 시뮬레이션

100회 동일 프롬프트 호출 시:

| 전략 | 총 비용 | 절감액 |
|------|---------|--------|
| 캐싱 없음 | $2.00 | - |
| 캐싱 사용 | $0.52 | $1.48 (74%) |

---

## 📈 캐시 통계 모니터링

### 통계 파일

```bash
# 기본 위치
CACHE_STATS_FILE=cache_stats.jsonl

# 보존 개수
CACHE_STATS_MAX_ENTRIES=100
```

### 통계 분석

```bash
python -m src.main --analyze-cache
```

출력 예시:

```
╭─ Cache Statistics ─────────────────────────╮
│ Total Calls: 150                           │
│ Cache Hits: 120 (80%)                      │
│ Cache Misses: 30 (20%)                     │
│ Estimated Savings: $1.52                   │
╰────────────────────────────────────────────╯
```

---

## 🔧 캐싱 최적화 팁

### 1. 시스템 프롬프트 공유

동일한 시스템 프롬프트를 여러 요청에서 재사용:

```python
# 시스템 프롬프트 캐싱 활성화
agent = GeminiAgent(config)
agent.enable_system_prompt_caching()
```

### 2. 템플릿 구조화

자주 변경되는 부분과 고정 부분을 분리:

```jinja2
{# 고정 부분 (캐싱됨) #}
{% include "system/base_system.j2" %}

{# 변동 부분 #}
{{ user_input }}
```

### 3. 배치 처리

유사한 요청을 배치로 처리하여 캐시 히트율 향상:

```python
results = await asyncio.gather(*[
    agent.process(query, shared_context)
    for query in queries
])
```

---

## 📊 캐시 히트율 목표

| 환경 | 목표 히트율 | 비고 |
|------|-------------|------|
| 개발 | 50%+ | 반복 테스트 시 |
| 스테이징 | 60%+ | 통합 테스트 시 |
| 프로덕션 | 70%+ | 실제 운영 시 |

---

## 🔍 캐시 디버깅

### 캐시 미스 원인

1. **토큰 부족**: 프롬프트가 2048 토큰 미만
2. **TTL 만료**: 캐시 유효 기간 초과
3. **프롬프트 변경**: 프롬프트 내용 변경

### 디버깅 로그

```bash
LOG_LEVEL=DEBUG python -m src.main
```

로그에서 캐시 관련 메시지 확인:

```
DEBUG - Cache hit for template: system/base_system.j2
DEBUG - Cache miss: token count 1500 < 2048
DEBUG - Cache expired: TTL exceeded
```

---

## 🏃 캐시 워밍

서버 시작 시 자주 사용하는 템플릿을 미리 캐싱:

```bash
python scripts/cache_warming.py
```

### 우선순위 템플릿

```python
PRIORITY_TEMPLATES = [
    "system/text_image_qa_explanation_system.j2",
    "system/text_image_qa_summary_system.j2",
    "eval/compare_three_answers.j2",
    "rewrite/enhance_answer.j2",
]
```

---

## ⏭️ 관련 문서

- [설정 가이드](CONFIGURATION.md)
- [모니터링](MONITORING.md)
- [비용 추적](../DEPLOYMENT_VERIFIED.md)
