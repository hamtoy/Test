# Context Caching 가이드

## Gemini API 캐싱 제약사항

### 최소 토큰 요구사항: 2048

Gemini Context Caching API는 **최소 2048 토큰** 이상의 컨텍스트만 캐싱할 수 있습니다.

## 작동 방식

```python
# ✅ 캐싱 가능
prompt = "..." * 3000  # 2048+ 토큰
result = await agent.generate(prompt)  # 캐싱됨

# ❌ 캐싱 불가
prompt = "..." * 1000  # 2048 미만
result = await agent.generate(prompt)  # 일반 API 사용
```

## 왜 2048인가?

이는 **비용 최적화**가 아니라 **API 제약**입니다:

1. **Google의 설계 결정**: 작은 컨텍스트는 캐싱 오버헤드가 더 큼
2. **인프라 효율성**: 캐시 저장/검색 비용 > 재계산 비용 (작은 입력)
3. **변경 불가**: 사용자가 조정할 수 없는 하드 제약

## 비용 분석

| 토큰 수 | 일반 API | 캐싱 API | 절감 |
|--------|---------|---------|-----|
| 1,000 | $0.001 | N/A | - |
| 2,048 | $0.002 | $0.001 | 50% |
| 10,000 | $0.010 | $0.002 | 80% |
| 100,000 | $0.100 | $0.010 | 90% |

## 모범 사례

```python
# 시스템이 자동 처리
# 2048 미만은 자동으로 일반 API 사용
# 사용자가 신경 쓸 필요 없음

# 큰 프롬프트는 재사용하여 캐싱 효과 극대화
system_prompt = load_large_prompt()  # 5000+ 토큰
for query in queries:
    # system_prompt는 캐싱됨, query만 변경
    result = await agent.generate(system_prompt + query)
```

## 로그 예시

```
DEBUG: 캐싱 건너뜀: 1,234 토큰 (최소 2,048 필요, Gemini API 제약)
DEBUG: 캐싱 활성화: 5,678 토큰 (예상 절감: ~70%)
```

## 설정

환경 변수로 최소 토큰을 설정할 수 있습니다:

```bash
# .env 파일
GEMINI_CACHE_MIN_TOKENS=2048
```

> ⚠️ **주의**: 2048 미만으로 설정하면 자동으로 2048로 조정됩니다. 이는 Gemini API의 기술적 제약사항입니다.

## 참고 자료

- [Gemini Caching Documentation](https://ai.google.dev/gemini-api/docs/caching)
- [Pricing Calculator](https://ai.google.dev/pricing)
