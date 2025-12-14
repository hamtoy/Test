# shining-quasar 사용자 매뉴얼

본 문서는 `shining-quasar` Graph RAG QA 시스템의 설치, 설정, 사용 방법을 안내합니다.

## 1. 설치 (Installation)

### 1.1 필수 요구사항

- **Python:** 3.11 이상
- **uv:** Python 패키지 관리자 (권장)
- **Docker:** Neo4j, Redis 실행을 위해 필요
- **Google AI API Key:** Gemini API 접근용

### 1.2 프로젝트 클론 및 의존성 설치

```bash
git clone https://github.com/yourorg/shining-quasar.git
cd shining-quasar

# uv 사용 시 (권장)
uv sync

# pip 사용 시
pip install -e .
```

### 1.3 Docker 서비스 실행

```bash
# Neo4j 및 Redis 시작
docker-compose up -d

# 모니터링 스택 (Prometheus/Grafana) 시작 (선택)
docker-compose -f docker-compose.monitoring.yml up -d
```

## 2. 설정 (Configuration)

### 2.1 환경 변수 (.env)

프로젝트 루트에 `.env` 파일을 생성하고 다음 변수를 설정합니다:

```dotenv
# 필수
GOOGLE_API_KEY=your_gemini_api_key_here

# Neo4j (RAG 기능 사용 시)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# Redis (캐싱 사용 시)
REDIS_URL=redis://localhost:6379

# 기능 플래그
ENABLE_RAG=true
ENABLE_LATS=true
ENABLE_METRICS=true

# 로그 레벨
LOG_LEVEL=INFO
```

### 2.2 주요 설정 항목

| 변수명 | 설명 | 기본값 |
|:---|:---|:---:|
| `GOOGLE_API_KEY` | Gemini API 키 (필수) | - |
| `NEO4J_URI` | Neo4j 연결 URI | - |
| `ENABLE_RAG` | Graph RAG 기능 활성화 | false |
| `ENABLE_LATS` | LATS 에이전트 활성화 | false |
| `ENABLE_METRICS` | Prometheus 메트릭 수집 활성화 | true |

## 3. 사용 방법 (Basic Usage)

### 3.1 웹 서버 실행

```bash
uv run uvicorn src.web.main:app --reload --host 0.0.0.0 --port 8000
```

서버가 실행되면 `http://localhost:8000` 에서 API에 접근할 수 있습니다.

### 3.2 API 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|:---|:---:|:---|
| `/api/v1/qa/ask` | POST | 질문을 전송하고 답변을 받습니다. |
| `/api/v1/qa/stream` | POST | SSE 스트리밍으로 실시간 답변을 받습니다. |
| `/metrics` | GET | Prometheus 메트릭을 조회합니다. |
| `/health` | GET | 서버 상태를 확인합니다. |

### 3.3 질문 예시 (cURL)

```bash
curl -X POST http://localhost:8000/api/v1/qa/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "프로젝트의 주요 기능은 무엇인가요?"}'
```

### 3.4 CLI 사용 (선택)

```bash
uv run python -m src.cli ask "질문 내용"
```

## 4. 트러블슈팅 (Troubleshooting)

### 4.1 429 Rate Limit 에러

**증상:** `googleapi.error: 429 RESOURCE_EXHAUSTED`

**원인:** Gemini API 호출 한도 초과

**해결 방법:**

1. 잠시 기다린 후 재시도합니다 (시스템이 자동으로 Fallback 모델을 사용합니다).
2. `.env`에서 `MAX_RETRIES` 값을 늘립니다.
3. API 할당량을 Google Cloud Console에서 확인합니다.

### 4.2 Neo4j 연결 실패

**증상:** `ServiceUnavailable: Failed to establish connection`

**원인:** Neo4j 서비스가 실행 중이지 않거나 연결 정보가 잘못됨

**해결 방법:**

1. Docker 컨테이너 상태 확인: `docker ps`
2. Neo4j 컨테이너가 없으면 실행: `docker-compose up -d neo4j`
3. `.env`의 `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` 확인

### 4.3 Redis 연결 실패

**증상:** `ConnectionError: Error connecting to Redis`

**해결 방법:**

1. Redis 컨테이너 상태 확인: `docker ps | grep redis`
2. Redis가 없으면 실행: `docker-compose up -d redis`
3. `.env`의 `REDIS_URL` 확인

### 4.4 메트릭이 수집되지 않음

**증상:** `/metrics` 엔드포인트가 빈 응답을 반환

**해결 방법:**

1. `prometheus_client` 패키지 설치 확인: `uv pip install prometheus-client`
2. `.env`에서 `ENABLE_METRICS=true` 설정 확인
3. 서버 재시작

## 5. 추가 자료

- **API 문서:** 서버 실행 후 `http://localhost:8000/docs` (Swagger UI)
- **소스 코드:** [GitHub Repository](https://github.com/yourorg/shining-quasar)
- **이슈 제보:** GitHub Issues를 통해 버그 및 기능 요청을 제출하세요.
