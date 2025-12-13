# 모니터링 가이드 (Monitoring)

성능 메트릭, SLO, 알림 설정에 대한 상세 가이드입니다.

---

## 📊 주요 메트릭 및 SLO

### Performance

| 메트릭 | SLO | 설명 |
|--------|-----|------|
| p99 Latency | < 5초 | 99번째 백분위수 응답 시간 |
| p50 Latency | < 2초 | 중앙값 응답 시간 |
| Cache Hit Rate | > 70% | 캐시 적중률 |

### Reliability

| 메트릭 | SLO | 설명 |
|--------|-----|------|
| Error Rate | < 1% | 오류 발생률 |
| Health Check Success | > 99% | 헬스체크 성공률 |
| Uptime | > 99.9% | 가용성 |

### Cost

| 메트릭 | SLO | 설명 |
|--------|-----|------|
| Daily Budget Usage | < 90% | 일일 예산 사용률 |
| Token Efficiency | > 80% | 토큰 효율성 |

---

## 🔍 헬스체크 엔드포인트

### GET /health

전체 시스템 상태 확인:

```json
{
  "status": "healthy",
  "components": {
    "redis": "healthy",
    "neo4j": "healthy",
    "gemini_api": "healthy",
    "disk": "healthy",
    "memory": "healthy"
  },
  "timestamp": "2025-01-29T12:00:00Z"
}
```

### GET /health/ready

Kubernetes readiness probe (Redis, Neo4j만 체크):

```json
{
  "ready": true,
  "checks": ["redis", "neo4j"]
}
```

### GET /health/live

Kubernetes liveness probe (프로세스 생존 확인):

```json
{
  "alive": true
}
```

---

## 📈 Prometheus 쿼리

### 평균 레이턴시

```promql
# 5분 평균 레이턴시
rate(gemini_api_latency_seconds_sum[5m]) / rate(gemini_api_latency_seconds_count[5m])
```

### 에러율

```promql
# 5분 에러율
rate(gemini_api_errors_total[5m]) / rate(gemini_api_calls_total[5m])
```

### 캐시 히트율

```promql
# 5분 캐시 히트율
rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))
```

### p99 레이턴시

```promql
# p99 레이턴시
histogram_quantile(0.99, rate(gemini_api_latency_seconds_bucket[5m]))
```

### 토큰 사용량

```promql
# 분당 입력 토큰
rate(gemini_input_tokens_total[1m])

# 분당 출력 토큰
rate(gemini_output_tokens_total[1m])
```

### 비용 추적

```promql
# 시간당 예상 비용
sum(rate(gemini_cost_usd_total[1h]))

# 일일 누적 비용
sum(increase(gemini_cost_usd_total[24h]))
```

---

## 📊 Grafana 대시보드

### 권장 패널

1. **API Latency**
   - p50, p90, p99 레이턴시 시계열
   - 히스토그램 분포

2. **Error Rate**
   - 에러율 게이지
   - 에러 유형별 분류

3. **Cache Performance**
   - 히트/미스 비율
   - 캐시 크기

4. **Cost Tracking**
   - 일일 비용 추이
   - 예산 사용률 게이지

5. **Token Usage**
   - 입력/출력 토큰 시계열
   - 토큰 효율성

### 대시보드 JSON

```json
{
  "dashboard": {
    "title": "Gemini Workflow Monitoring",
    "panels": [
      {
        "title": "API Latency",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.99, rate(gemini_api_latency_seconds_bucket[5m]))",
            "legendFormat": "p99"
          }
        ]
      }
    ]
  }
}
```

---

## 🚨 알림 설정

### Critical 알림 (즉시 대응)

| 조건 | 지속 시간 | 알림 채널 |
|------|-----------|-----------|
| p99 Latency > 10초 | 5분 | PagerDuty, Slack |
| Error Rate > 5% | 2분 | PagerDuty, Slack |
| Health Check 실패 | 1분 | PagerDuty |

### Warning 알림 (모니터링)

| 조건 | 지속 시간 | 알림 채널 |
|------|-----------|-----------|
| 예산 사용률 > 90% | 즉시 | Slack |
| Cache Hit Rate < 50% | 15분 | Slack |
| p99 Latency > 5초 | 10분 | Slack |

### AlertManager 설정 예시

```yaml
groups:
  - name: gemini-workflow
    rules:
      - alert: HighLatency
        expr: histogram_quantile(0.99, rate(gemini_api_latency_seconds_bucket[5m])) > 10
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High API latency detected"
          description: "p99 latency is {{ $value }}s"

      - alert: HighErrorRate
        expr: rate(gemini_api_errors_total[5m]) / rate(gemini_api_calls_total[5m]) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }}"
```

---

## 🔧 트러블슈팅

### 높은 레이턴시

1. **캐시 히트율 확인**

   ```bash
   python -m src.main --analyze-cache
   ```

2. **Neo4j 연결 상태 확인**

   ```bash
   python scripts/neo4j/neo4j_benchmark_stub.py
   ```

3. **Gemini API 상태 페이지 확인**
   - [Google Cloud Status](https://status.cloud.google.com/)

4. **동시성 조정**

   ```bash
   GEMINI_MAX_CONCURRENCY=3
   ```

### 높은 에러율

1. **로그에서 에러 타입 확인**

   ```bash
   tail -f error.log | grep ERROR
   ```

2. **API 키 유효성 확인**

   ```bash
   python -m src.list_models
   ```

3. **Rate Limit 도달 여부 확인**

   ```bash
   grep "429" app.log
   ```

4. **재시도 로직 확인**
   - Tenacity 재시도 횟수 증가

### 캐시 히트율 저하

1. **TTL 설정 확인**

   ```bash
   GEMINI_CACHE_TTL_MINUTES=360
   ```

2. **캐시 크기 확인**

   ```bash
   GEMINI_CACHE_SIZE=100
   ```

3. **프롬프트 토큰 수 확인**
   - 2048 토큰 이상인지 확인

---

## 📝 로그 분석

### 레이턴시 통계

```bash
python scripts/latency_baseline.py --log-file app.log
```

출력:

```
┏━━━━━━━━┳━━━━━━━━┓
┃ Metric ┃ Value  ┃
┡━━━━━━━━╇━━━━━━━━┩
│ Count  │ 150    │
│ Min    │ 45.23  │
│ Mean   │ 234.56 │
│ p50    │ 210.34 │
│ p90    │ 356.78 │
│ p99    │ 678.90 │
└────────┴────────┘
```

### 비용 분석

```bash
python scripts/analysis/compare_runs.py --sort-by cost
```

---

## ⏭️ 관련 문서

- [설정 가이드](CONFIGURATION.md)
- [캐싱 전략](CACHING.md)
- [보안](SECURITY.md)
