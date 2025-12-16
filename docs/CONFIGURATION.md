# 설정 가이드 (Configuration)

모든 환경 변수 및 설정 옵션에 대한 상세 가이드입니다.

---

## 📦 설치 옵션

### 기본 설치

```bash
pip install -e .
```

포함 기능:

- Google Gemini AI (`google-generativeai`)
- 설정 관리 (`pydantic`, `pydantic-settings`)
- 재시도 로직 (`tenacity`)
- 콘솔 UI (`rich`)
- 템플릿 엔진 (`jinja2`)
- 환경 변수 (`python-dotenv`)

### 선택적 설치

| 설치 명령 | 포함 패키지 | 용도 |
|-----------|-------------|------|
| `pip install -e ".[rag]"` | langchain, langchain-neo4j | Neo4j RAG 시스템 |
| `pip install -e ".[web]"` | fastapi, uvicorn, python-multipart | 웹 UI 서버 |
| `pip install -e ".[worker]"` | faststream[redis] | Redis 기반 LATS 워커 |
| `pip install -e ".[multimodal]"` | pillow | 이미지 처리 |
| `pip install -e ".[all]"` | 위 모든 패키지 | 전체 기능 |
| `pip install -e ".[dev]"` | pytest, mypy, ruff, sphinx 등 | 개발/테스트 |

---

## 🔑 필수 환경 변수

### GEMINI_API_KEY (필수)

```bash
GEMINI_API_KEY=AIza...
```

- **형식**: `AIza`로 시작하는 39자 문자열
- **발급**: [Google AI Studio](https://makersuite.google.com/app/apikey)
- **검증**: 시작 시 자동 검증

---

## ⚙️ Gemini API 설정

| 변수 | 기본값 | 범위 | 설명 |
|------|--------|------|------|
| `GEMINI_MODEL_NAME` | `gemini-flash-latest` | 고정 | 사용 모델 |
| `GEMINI_MAX_OUTPUT_TOKENS` | `4096` | 1+ | 최대 출력 토큰 |
| `GEMINI_MAX_OUTPUT_TOKENS_EXPLANATION` | (옵션) | 1+ | explanation 토큰 상한 override |
| `GEMINI_MAX_OUTPUT_TOKENS_REASONING` | (옵션) | 1+ | reasoning 토큰 상한 override |
| `GEMINI_MAX_OUTPUT_TOKENS_TARGET` | (옵션) | 1+ | target 토큰 상한 override |
| `GEMINI_TIMEOUT` | `120` | 30-600 | API 타임아웃 (초) |
| `GEMINI_MAX_CONCURRENCY` | `10` | 1-20 | 최대 동시 요청 수 |
| `GEMINI_TEMPERATURE` | `0.2` | 0.0-2.0 | 샘플링 온도 |
| `GEMINI_CACHE_SIZE` | `50` | 1+ | 컨텍스트 캐시 크기 |
| `GEMINI_CACHE_TTL_MINUTES` | `360` | 1-1440 | 캐시 TTL (분) |
| `GEMINI_CACHE_MIN_TOKENS` | `2048` | 2048+ | 캐싱 최소 토큰 수 (Gemini API 제약) |

---

## 📊 캐싱 설정

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `CACHE_STATS_FILE` | `cache_stats.jsonl` | 캐시 통계 파일 경로 |
| `CACHE_STATS_MAX_ENTRIES` | `100` | 통계 파일 최대 보존 개수 |
| `LOCAL_CACHE_DIR` | `.cache` | 로컬 캐시 메타 저장 폴더 |

### TTL 설정 (시스템/평가/생성 구분)

```bash
# 권장 TTL 설정 (초 단위)
CACHE_TTL_SYSTEM=3600      # 시스템 프롬프트 TTL (1시간)
CACHE_TTL_EVALUATION=1800   # 평가 프롬프트 TTL (30분)
CACHE_TTL_GENERATION=900    # 생성 프롬프트 TTL (15분)
```

---

## 📝 로깅 설정

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `LOG_LEVEL` | `INFO` | 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `LOG_FILE` | `app.log` | INFO+ 로그 파일 경로 |
| `ERROR_LOG_FILE` | `error.log` | ERROR+ 로그 파일 경로 |

---

## 💰 예산 설정

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `BUDGET_LIMIT_USD` | `None` | 예산 한도 (USD) |
| `BUDGET_WARNING_THRESHOLD` | `0.8` | 경고 임계값 (80%) |

예산 경고 단계:

- 80% → WARNING
- 90% → HIGH
- 95% → CRITICAL

---

## 🔗 Neo4j 설정 (RAG 시스템)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j 접속 URI |
| `NEO4J_USER` | `neo4j` | Neo4j 사용자명 |
| `NEO4J_PASSWORD` | (필수) | Neo4j 비밀번호 |

> **참고**: `NEO4J_URI`를 설정하면 시스템이 RAG 모드를 자동 감지합니다.

---

## 🔄 Rate Limiting

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `RATE_LIMIT_RPM` | `60` | 분당 요청 수 |
| `MAX_CONCURRENT_REQUESTS` | `5` | 동시 요청 수 |

---

## 🚀 기능 플래그

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `ENABLE_LATS` | `false` | LATS 워커 활성화 |
| `ENABLE_DATA2NEO` | `false` | Data2Neo 파이프라인 활성화 |
| `DATA2NEO_BATCH_SIZE` | `100` | 배치 크기 |
| `DATA2NEO_CONFIDENCE_THRESHOLD` | `0.7` | 신뢰도 임계값 |

---

## 🐳 Docker/프로덕션 환경

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `ENVIRONMENT` | `development` | 환경 (development/staging/production) |
| `LOG_LEVEL_OVERRIDE` | - | 로그 레벨 강제 지정 |
| `REDIS_URL` | `redis://localhost:6379` | Redis 연결 URL |
| `PROJECT_ROOT` | 자동 감지 | 프로젝트 루트 경로 |

---

## 📁 .env.example 전체 템플릿

```bash
# ===========================================
# 필수 설정
# ===========================================
GEMINI_API_KEY=your_api_key_here

# ===========================================
# Gemini API 설정 (선택)
# ===========================================
GEMINI_MODEL_NAME=gemini-3-pro-preview
GEMINI_MAX_OUTPUT_TOKENS=8192
GEMINI_TIMEOUT=120
GEMINI_MAX_CONCURRENCY=5
GEMINI_TEMPERATURE=0.2
GEMINI_CACHE_SIZE=50
GEMINI_CACHE_TTL_MINUTES=360

# ===========================================
# 캐싱 설정 (선택)
# ===========================================
CACHE_STATS_FILE=cache_stats.jsonl
CACHE_STATS_MAX_ENTRIES=100
LOCAL_CACHE_DIR=.cache

# ===========================================
# 로깅 설정 (선택)
# ===========================================
LOG_LEVEL=INFO

# ===========================================
# 예산 설정 (선택)
# ===========================================
# BUDGET_LIMIT_USD=10.0

# ===========================================
# Neo4j 설정 (RAG 사용 시)
# ===========================================
# NEO4J_URI=bolt://localhost:7687
# NEO4J_USER=neo4j
# NEO4J_PASSWORD=your_password_here

# ===========================================
# 기능 플래그 (선택)
# ===========================================
# ENABLE_LATS=false
# ENABLE_DATA2NEO=false

# ===========================================
# Redis 설정 (워커 사용 시)
# ===========================================
# REDIS_URL=redis://localhost:6379
```

---

## 🔍 설정 검증

시작 시 다음 항목이 자동 검증됩니다:

1. **API 키 형식**: AIza 접두사, 39자 길이
2. **숫자 범위**: 동시성(1-20), 타임아웃(30-600), TTL(1-1440)
3. **로그 레벨**: 유효한 레벨 확인
4. **디렉토리**: 필수 디렉토리 자동 생성

검증 실패 시 명확한 오류 메시지와 해결 방법이 표시됩니다.
