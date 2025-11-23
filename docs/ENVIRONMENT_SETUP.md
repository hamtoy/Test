# 환경 설정 가이드

Gemini 워크플로우 시스템 실행을 위한 환경 변수 설정 가이드입니다.

## 필수 환경 변수

### Gemini API (핵심 워크플로우)

```bash
GEMINI_API_KEY=AIzaxxxxx
```

**Gemini API 키 발급:**

1. <https://makersuite.google.com/app/apikey> 접속
2. "Create API Key" 클릭
3. API 키 복사 (AIza로 시작, 총 39자)
4. **중요**: 키는 재확인 불가하므로 안전하게 저장

## 선택적 환경 변수

### 모델 및 성능 설정

```bash
GEMINI_MODEL_NAME=gemini-3-pro-preview  # 사용할 모델
GEMINI_MAX_OUTPUT_TOKENS=8192           # 최대 출력 토큰
GEMINI_TIMEOUT=120                      # API 타임아웃(초)
GEMINI_MAX_CONCURRENCY=5                # 동시 요청 수
GEMINI_TEMPERATURE=0.2                  # 샘플링 온도
```

### 캐싱 설정

```bash
GEMINI_CACHE_SIZE=50                    # 컨텍스트 캐시 크기
GEMINI_CACHE_TTL_MINUTES=10             # 캐시 TTL(분)
LOCAL_CACHE_DIR=.cache                  # 로컬 캐시 저장 폴더
```

### 로깅 및 통계

```bash
LOG_LEVEL=INFO                          # 로그 레벨
LOG_FILE=app.log                        # INFO+ 로그 파일
ERROR_LOG_FILE=error.log                # ERROR+ 로그 파일
CACHE_STATS_FILE=cache_stats.jsonl      # 캐시 통계 파일
CACHE_STATS_MAX_ENTRIES=100             # 통계 보존 개수
```

### Neo4j (QA 시스템 사용 시)

QA RAG 시스템을 사용하는 경우에만 필요합니다:

```bash
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

**Neo4j Aura 무료 인스턴스 생성:**

1. <https://neo4j.com/cloud/aura-free/> 접속
2. "Start Free" 클릭
3. 인스턴스 생성 후 연결 정보 복사
4. **중요**: 비밀번호는 재확인 불가하므로 안전하게 저장

## 빠른 시작

```bash
# 1. .env.example을 .env로 복사
cp .env.example .env

# 2. .env 파일 편집하여 GEMINI_API_KEY 입력
# (VS Code, notepad 등 사용)

# 3. 환경 변수 확인
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('GEMINI_API_KEY:', os.getenv('GEMINI_API_KEY')[:10] + '...')"

# 4. 워크플로우 테스트
python -m src.main --mode AUTO --ocr-file example_ocr.txt --cand-file example_candidates.json --intent "요약"
```

## 문제 해결

### "환경 변수 GEMINI_API_KEY가 설정되지 않았습니다"

→ `.env` 파일에 `GEMINI_API_KEY` 추가 필요

### "API key format error"

→ API 키가 `AIza`로 시작하고 총 39자인지 확인

### "Rate limit exceeded"

→ `GEMINI_MAX_CONCURRENCY`를 낮춰보세요 (예: 1 또는 2)

### "Neo4j 연결 실패"

→ QA 시스템을 사용하지 않는다면 무시해도 됩니다. 사용하는 경우 URI/User/Password 확인

## 개발 환경 설정 (권장)

```bash
# 의존성 설치
uv sync --extra dev

# pre-commit 훅 활성화
pre-commit install

# 첫 실행 시 전체 파일 검사
pre-commit run --all-files
```

## 로컬 개발 속도 향상

- **테스트 워치**: `uv run pytest-watcher .` (파일 변경 시 자동 재실행)
- **병렬 테스트**: `uv run pytest -n auto tests/` (실패 우선: `--ff`)
- **프로파일링**: `python scripts/auto_profile.py src.main -- --help`
- **결과 비교**: `python scripts/compare_runs.py --sort-by cost`
- **빠른 백업**: `pwsh scripts/backup.ps1 -SkipEnv`

## 추가 리소스

- **프로젝트 구조**: `README.md` 확인
- **UV 패키지 매니저**: `UV_GUIDE.md` 참조
- **개발 원칙 리뷰**: `docs/PRINCIPLES_REVIEW.md`
- **주석 가이드**: `docs/COMMENT_REVIEW.md`
