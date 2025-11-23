[![CI](https://github.com/hamtoy/Test/actions/workflows/ci.yml/badge.svg)](https://github.com/hamtoy/Test/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/hamtoy/Test/branch/main/graph/badge.svg)](https://codecov.io/gh/hamtoy/Test)

# Gemini 워크플로우 - Q&A 시스템

Google Gemini AI를 활용한 Q&A 응답 평가 및 재작성 워크플로우 시스템입니다.

## 주요 기능

- 🤖 **질의 생성**: OCR 텍스트에서 질의 자동생성
- 📊 **후보 평가**: 여러 답변 후보 평가 및 점수 부여
- ✍️ **답변 재작성**: 선택된 답변의 품질 개선
- 💰 **비용 추적**: 토큰 사용량 및 비용 추적
- 🛡️ **안정성**: Rate limiting, 타입 검증, 환각 감지
- 🎨 **사용자 인터페이스**: Rich 기반 콘솔 출력
- 🧪 **테스트**: pytest 기반 테스트 지원

## 프로젝트 구조

```
project_root/
├── .env                    # 환경 변수 (API 키)
├── .env.example            # 환경 변수 템플릿
├── pyproject.toml          # 프로젝트 메타데이터/의존성
├── .pre-commit-config.yaml # pre-commit 훅 설정
├── README.md               # 문서
├── UV_GUIDE.md             # UV 패키지 매니저 가이드
├── checks/                 # Session 검증
│   ├── detect_forbidden_patterns.py
│   └── validate_session.py
├── data/
│   ├── inputs/             # 입력 파일
│   └── outputs/            # 출력 파일 (Markdown)
├── docs/                   # 상세 문서
│   ├── ARCHITECTURE.md     # 시스템 아키텍처
│   ├── ENVIRONMENT_SETUP.md
│   └── ...
├── examples/               # 예제 데이터
│   └── session_input.json
├── notion-neo4j-graph/     # Neo4j 데이터 임포트
├── scripts/                # 유틸리티 스크립트
│   ├── auto_profile.py
│   ├── compare_runs.py
│   └── ...
├── src/                    # 소스 코드 (37개 파일)
│   ├── agent.py            # Gemini API 인터페이스
│   ├── main.py             # 메인 워크플로우
│   ├── qa_rag_system.py    # RAG + Graph QA 시스템
│   ├── config.py           # 설정 관리
│   ├── models.py           # Pydantic 모델
│   └── ...
├── templates/              # Jinja2 템플릿 (15개)
│   ├── system/             # 시스템 프롬프트
│   ├── user/               # 사용자 프롬프트
│   ├── eval/               # 평가 프롬프트
│   └── ...
└── tests/                  # 테스트 (25개 파일)
    ├── test_agent.py
    ├── test_main.py
    └── ...
```

## 시스템 개요

이 시스템은 다음 작업을 수행합니다:

- OCR 텍스트를 기반으로 검색 질의 생성
- 여러 후보 답변을 평가하고 점수 부여
- 최고 점수 답변을 재작성하여 품질 개선
- 토큰 사용량 및 비용 추적
- 입력 검증 및 환각 감지

### 시스템 구성

**워크플로우 다이어그램 (Mermaid)**

```mermaid
flowchart LR
    A[OCR 입력] --> B[질의 생성]
    B --> C[후보 평가]
    C --> D[답변 재작성]
    D --> E[결과 출력]

    C -.->|옵션: QA RAG| F[Neo4j 그래프]
    F -.-> G[벡터 검색]
    F -.-> H["Session 검증 (checks/)"]
    
    style F fill:#2d3748,stroke:#718096,stroke-dasharray: 5 5
    style G fill:#2d3748,stroke:#718096,stroke-dasharray: 5 5
    style H fill:#2d3748,stroke:#718096,stroke-dasharray: 5 5
```

> **기본 워크플로우** (실선): OCR 입력 → 질의 생성 → 후보 평가 → 답변 재작성 → 결과 출력  
> **선택적 RAG 경로** (점선): 후보 평가 시점에 Neo4j 그래프/벡터 검색/Session 검증을 통해 평가 품질을 보강할 수 있습니다.

> [!NOTE]
> Neo4j와 Notion은 **QA RAG 시스템** 사용 시에만 필요합니다. 기본 워크플로우는 Gemini API만으로 동작합니다.

## 시작하기

### 필수 요구사항

- Python 3.10 이상
- Google Gemini API 키 ([발급 링크](https://makersuite.google.com/app/apikey))

### 선택 요구사항 (QA RAG 시스템 사용 시)

- Neo4j 데이터베이스 ([Aura 무료](https://neo4j.com/cloud/aura-free/))
- Notion 계정 (규칙 데이터 소스)

### 설치

#### pip 사용

```bash
cd shining-quasar
pip install -e .
# 개발/테스트/문서 의존성까지 설치
pip install -e ".[dev]"
```

#### uv 사용

```bash
pip install uv
uv sync                # 런타임 의존성
uv sync --extra dev    # 개발/테스트/문서 의존성 포함
```

자세한 내용은 [UV_GUIDE.md](UV_GUIDE.md)를 참조하세요.

## ⚡️ Quick Start (샘플 데이터)

1) `.env`에서 `GEMINI_API_KEY` 설정  
2) 샘플 입력 사용:

```bash
python -m src.main --mode AUTO --ocr-file example_ocr.txt --cand-file example_candidates.json --intent "요약"
# 체크포인트 복구 실행
python -m src.main --mode AUTO --ocr-file example_ocr.txt --cand-file example_candidates.json --resume
```

### 시나리오 예시 (샘플 데이터)

- 요약: `uv run python -m src.main --mode AUTO --ocr-file example_ocr.txt --cand-file example_candidates.json --intent "요약"`
- 분류/라벨링: `uv run python -m src.main --mode AUTO --ocr-file example_ocr.txt --cand-file example_candidates.json --intent "분류"`
- 체크포인트 재시작: `uv run python -m src.main --mode AUTO --ocr-file example_ocr.txt --cand-file example_candidates.json --resume`
- 개인 사용 시 API 할당량 절약: `.env`에서 `GEMINI_MAX_CONCURRENCY=1`로 낮춰 실행

### 성능/관측 도구

```bash
# 캐시 통계 요약 (CACHE_STATS_FILE 기반)
python -m src.main --analyze-cache
make -C docs cache-report  # make 도움말 위치: docs/Makefile

# 로그에서 API latency p50/p90/p99 집계
python scripts/latency_baseline.py --log-file app.log
make -C docs latency
```

3) 결과는 `data/outputs/`에 저장됩니다.

### 개발 환경 (권장)

개발/테스트 시 필요한 도구를 설치하고 pre-commit 훅을 활성화하세요.

```bash
pip install -e ".[dev]"
pre-commit install
# 첫 실행 시 전체 파일 검사
pre-commit run --all-files
```

### 빠른 품질 검사(권장)

```bash
pre-commit run --all-files        # ruff + ruff-format + mypy
uv run pytest tests/ --cov=src --cov-fail-under=75
```

### CI 파이프라인

GitHub Actions에서 자동으로 실행되는 검증 단계:

1. `ruff check` - 린트 검사
2. `ruff format --check` - 포맷 검사
3. `mypy` - 타입 체크
4. `pytest --cov=src --cov-fail-under=75` - 테스트 및 커버리지

로컬에서 동일하게 실행하려면 `pre-commit run --all-files` 사용

### 템플릿/세션 도구

```bash
# 템플릿 렌더링 예시
uv run python scripts/render_prompt.py --template system/text_image_qa_explanation_system.j2 --context examples/session_input.json

# 세션 빌드 및 검증
uv run python scripts/build_session.py --context examples/session_input.json
uv run python checks/validate_session.py --context examples/session_input.json
uv run python scripts/run_pipeline.py --context examples/session_input.json
```

### 환경 설정

`.env.example`을 복사하여 `.env` 파일 생성:

```bash
cp .env.example .env
```

`.env` 파일 편집:

```bash
# 필수
GEMINI_API_KEY=your_api_key_here

# 선택 사항 - Gemini 설정 (기본값 제공)
GEMINI_MODEL_NAME=gemini-3-pro-preview
GEMINI_MAX_OUTPUT_TOKENS=8192
GEMINI_TIMEOUT=120
GEMINI_MAX_CONCURRENCY=5
GEMINI_TEMPERATURE=0.2
GEMINI_CACHE_SIZE=50
GEMINI_CACHE_TTL_MINUTES=10
LOG_LEVEL=INFO

# 선택 사항 - QA RAG 시스템 사용 시
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

다른 디렉토리에서 실행할 경우 `PROJECT_ROOT`를 설정할 수 있습니다.

API 키 확인:

```bash
python -m src.list_models
```

### 입력 파일 준비

`data/inputs/` 디렉토리에 파일 배치:

- OCR 텍스트: `data/inputs/input_ocr.txt`
- 후보 답변: `data/inputs/input_candidates.json`

### 실행

```bash
# 기본 실행
python -m src.main

# CHAT 모드 (질의 생성 후 후보 편집 가능)
python -m src.main --mode CHAT --intent "요약"

# 사용자 지정 입력 파일
python -m src.main --ocr-file custom_ocr.txt --cand-file custom_candidates.json

# 샘플 데이터 사용
python -m src.main --ocr-file input_ocr.txt --cand-file input_candidates.json
```

## 명령줄 옵션

도움말 표시:

```bash
python -m src.main --help
```

주요 옵션:

- `--mode`: `AUTO` (기본, 완전 자동) 또는 `CHAT` (질의 생성 후 편집 가능)
- `--ocr-file`: OCR 입력 파일 경로 (`data/inputs/` 기준)
- `--cand-file`: 후보 답변 파일 경로 (`data/inputs/` 기준)
- `--intent`: 추가 사용자 의도
- `--interactive`: 확인 프롬프트 활성화 (AUTO 모드에서도 적용)
- `--resume`: 체크포인트(`checkpoint.jsonl`)를 읽어 완료된 질의를 건너뜀
- `--checkpoint-file`: 체크포인트 경로 지정 (기본: `data/outputs/checkpoint.jsonl`)
- `--log-level`: 로그 레벨 override (`DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`)
- `--analyze-cache`: 캐시 통계 요약을 출력하고 종료 (`CACHE_STATS_FILE` 기반)

## 출력 및 로그

- 결과: `data/outputs/result_turn_<id>_<timestamp>.md`
- 콘솔: Rich 포맷 출력
- 로그 파일: `app.log`
- 캐싱: 프롬프트 토큰이 2000개 이상일 때만 활성화
- **캐시 통계**: `cache_stats.jsonl`(기본)로 누적 저장
  - 파일 경로: `CACHE_STATS_FILE` 환경 변수로 변경 가능
  - 보존 개수: `CACHE_STATS_MAX_ENTRIES`로 조정 가능
  - 통계 확인: `python -m src.main --analyze-cache`
- 로그 분리: INFO+ → `app.log`, ERROR+ → `error.log` (JSON 포맷은 production 모드에서 자동 적용)
- 체크포인트: `--resume` 사용 시 `checkpoint.jsonl`(기본)에서 완료된 질의를 건너뜀. `--checkpoint-file`로 경로 지정 가능
- **프로파일링 결과**: `profiling_results/` 디렉토리에 `.prof` 파일 저장

## 성능 분석

### API Latency 통계

로그 파일에서 API 호출 레이턴시를 분석하여 백분위수 통계를 확인할 수 있습니다:

```bash
# 기본 로그 파일 분석 (app.log)
python scripts/latency_baseline.py

# 사용자 지정 로그 파일
python scripts/latency_baseline.py --log-file custom.log

# 여러 로그 파일 통합 분석
python scripts/latency_baseline.py --log-file run1.log --log-file run2.log
```

출력 예시:

```
┏━━━━━━━━┳━━━━━━━━┓
┃ Metric ┃ Value  ┃
┡━━━━━━━━╇━━━━━━━━┩
│ Count  │ 150    │
│ Min    │ 45.23  │
│ Mean   │ 234.56 │
│ Max    │ 892.10 │
│ p50    │ 210.34 │
│ p90    │ 356.78 │
│ p99    │ 678.90 │
└────────┴────────┘
```

## 개발 도구

### 성능 분석

- **프로파일링**: `python scripts/auto_profile.py src.main --mode AUTO --ocr-file example_ocr.txt --cand-file example_candidates.json --intent "요약"`
  - 병목 상위 20개 표시 (`--` 구분은 선택 사항)
  - 결과 저장: `profiling_results/{module_name}_stats.prof`
  
- **레이턴시 분석**: `python scripts/latency_baseline.py --log-file app.log`
  - API 호출 레이턴시 통계 (p50/p90/p99)

### 결과 분석

- **결과 비교**: `python scripts/compare_runs.py --sort-by cost`
  - `data/outputs/result_*.md` 파일을 표로 정렬/요약
  
- **캐시 분석**: `python -m src.main --analyze-cache`
  - 캐시 hit/miss, 비용 절감 계산

### 데이터 관리

- **백업**: `pwsh scripts/backup.ps1`
  - 데이터·로그를 날짜별 ZIP으로 압축
  - 기본값: `.env` 포함
  - 민감정보 제외: `-SkipEnv` 옵션 사용

## 출력 예시

```
INFO     리소스 로드 중...
INFO     Rate limiter enabled: 60 requests/minute
INFO     워크플로우 시작 (Mode: AUTO)
INFO     질의 생성 중...
INFO     Token Usage - Prompt: 3,095, Response: 45, Total: 4,929
INFO     질의 생성 완료...
INFO     후보 평가 중...
INFO     Token Usage - Prompt: 4,908, Response: 282, Total: 7,123
INFO     후보 선정 완료: A
INFO     답변 재작성 중...
INFO     Token Usage - Prompt: 3,681, Response: 867, Total: 6,316

🤖 Query: 핵심 내용 요약
📊 Selected Candidate: A

╭─ 📝 Final Output ──────────────────────────╮
│ # 요약                                     │
│                                            │
│ 주요 내용:                                 │
│ 1. 첫 번째 요점                            │
│ 2. 두 번째 요점                            │
╰────────────────────────────────────────────╯

╭─ 비용 요약 ───────────────────────────────╮
│ 💰 총 비용: $0.0534 USD                   │
│ 📊 토큰: 11,684 입력 / 1,194 출력         │
│ 📈 캐시: 5 hit / 2 miss                   │
╰────────────────────────────────────────────╯
```

## 테스트

```bash
# 전체 테스트
pytest tests/ -v

# 특정 테스트
pytest tests/test_agent.py -v

# 커버리지 포함
pytest tests/ --cov=src --cov-report=html

# 빠른 피드백 루프
uv run pytest-watcher .
uv run pytest -n auto --ff tests/
```

## 개발 가이드

### 주요 모듈

- `src/agent.py`: Gemini API 호출, 재시도, rate limiting, 비용 추적
- `src/cache_analytics.py`: 캐시 통계 분석 및 비용 절감 계산
- `src/config.py`: 환경 변수 기반 설정 관리
- `src/constants.py`: 가격 티어, 예산 임계값, UI 메시지 템플릿
- `src/data_loader.py`: 타입 검증을 포함한 데이터 로딩
- `src/exceptions.py`: 사용자 정의 예외 (API 제한, 예산 초과 등)
- `src/logging_setup.py`: 콘솔/파일 로깅 분리, 민감 데이터 마스킹
- `src/main.py`: 워크플로우 실행, 체크포인트 관리, 병렬 처리
- `src/models.py`: 환각 감지 기능이 포함된 Pydantic 모델
- `src/utils.py`: 파일 처리 및 파싱 유틸리티
- `src/qa_rag_system.py`: RAG 및 그래프 기반 QA 시스템
- `src/integrated_quality_system.py`: 통합 품질 관리 파이프라인

### 주요 기능

#### 환각 감지

LLM이 선택한 후보가 실제 점수와 일치하는지 검증:

```python
@model_validator(mode='after')
def validate_best_candidate(self):
    actual_best = max(self.evaluations, key=lambda x: x.score)
    if self.best_candidate != actual_best.candidate_id:
        logger.warning("LLM Hallucination Detected - Auto-correcting")
        self.best_candidate = actual_best.candidate_id
```

#### Rate Limiting

- **Semaphore**: 동시 API 호출 수 제한
- **Rate Limiter**: 분당 요청 수 제한
- `429 Too Many Requests` 오류 방지

#### Dependency Injection

테스트와 프로덕션 환경 분리:

```python
# 프로덕션
agent = GeminiAgent(config, jinja_env=real_env)

# 테스트
agent = GeminiAgent(config, jinja_env=mock_env)
```

#### 병렬 처리

여러 질의를 동시에 처리하여 성능 향상:

```python
# asyncio.gather를 사용한 병렬 쿼리 처리
results = await asyncio.gather(*[
    process_single_query(agent, query, ocr_text, candidates)
    for query in queries
])
```

## 환경 변수

| 변수                       | 기본값                 | 설명               |
| -------------------------- | ---------------------- | ------------------ |
| `GEMINI_API_KEY`           | 필수                   | Gemini API 키      |
| `GEMINI_MODEL_NAME`        | `gemini-3-pro-preview` | 사용할 모델        |
| `GEMINI_MAX_OUTPUT_TOKENS` | `8192`                 | 최대 출력 토큰 수  |
| `GEMINI_TIMEOUT`           | `120`                  | API 타임아웃 (초)  |
| `GEMINI_MAX_CONCURRENCY`   | `5`                    | 최대 동시 요청 수  |
| `GEMINI_TEMPERATURE`       | `0.2`                  | 샘플링 온도        |
| `GEMINI_CACHE_SIZE`        | `50`                   | 컨텍스트 캐시 크기 |
| `GEMINI_CACHE_TTL_MINUTES` | `10`                   | 캐시 TTL (분)      |
| `LOG_LEVEL`                | `INFO`                 | 로그 레벨          |
| `CACHE_STATS_FILE`         | `cache_stats.jsonl`    | 캐시/토큰 통계 파일 경로 |
| `CACHE_STATS_MAX_ENTRIES`  | `100`                  | 통계 파일 보존 개수 |
| `LOCAL_CACHE_DIR`          | `.cache`               | 로컬 캐시 메타 저장 폴더 |
| `LOG_FILE`                 | `app.log`              | INFO+ 로그 파일 경로 |
| `ERROR_LOG_FILE`           | `error.log`            | ERROR+ 로그 파일 경로 |
| `PROJECT_ROOT`             | 자동 감지              | 프로젝트 루트 경로 |
| `NEO4J_URI`                | `bolt://localhost:7687`| Neo4j 접속 URI     |
| `NEO4J_USER`               | `neo4j`                | Neo4j 사용자명     |
| `NEO4J_PASSWORD`           | 필수                   | Neo4j 비밀번호     |

자동 감지는 `.git`, `templates`, `data` 폴더를 기준으로 수행됩니다.

## FAQ

- **GEMINI_API_KEY 형식 오류가 뜹니다.** → `AIza`로 시작하고 총 39자여야 합니다. `.env`에서 공백/따옴표가 섞여 있지 않은지 확인하세요.
- **커버리지 기준은 얼마인가요?** → CI에서 `--cov-fail-under=75`를 사용합니다. 로컬에서도 동일하게 실행됩니다.
- **캐시 통계 파일은 어디에 저장되나요?** → 기본 `cache_stats.jsonl`이며, `CACHE_STATS_FILE`로 경로를, `CACHE_STATS_MAX_ENTRIES`로 보존 개수를 설정할 수 있습니다.

## 구현된 기능

- **타입 안정성**: Pydantic Literal 사용
- **예외 처리**: 다중 레이어 에러 핸들링
- **Rate Limiting**: 동시성 및 RPM 제어
- **비용 추적**: 실시간 토큰 사용량 계산
- **로깅**: 콘솔 및 파일 분리, API 키 마스킹
- **테스트**: Dependency Injection 지원
- **검증**: 입력 유효성 검사 및 환각 감지
- **병렬 처리**: 여러 쿼리 동시 처리
- **캐시 모니터링**: 캐시 hit/miss 추적

## 문서

- **[UV_GUIDE.md](UV_GUIDE.md)**: UV 패키지 매니저 사용 가이드
- **[CONTRIBUTING.md](CONTRIBUTING.md)**: 기여 가이드라인
- **[DEPLOYMENT_VERIFIED.md](DEPLOYMENT_VERIFIED.md)**: 배포 검증 내역
- **Sphinx 문서**: `docs/` 디렉토리에서 `make html` 실행

## 즉시 실행 가능 - QA 시스템 구축

### 1. 그래프 스키마 구축

```bash
python src/graph_schema_builder.py
```

Notion 가이드에서 Rule/Constraint/Example을 추출하여 Neo4j 지식 그래프를 생성합니다.

### 2. Neo4j Browser에서 확인

```cypher
MATCH (n) RETURN labels(n), count(n)
```

생성된 노드 타입별 개수를 확인합니다.

### 3. RAG 시스템 테스트

```bash
python src/qa_rag_system.py
```

벡터 검색 기반 규칙 조회 및 제약 조건/모범 사례를 확인합니다.

### 4. 통합 파이프라인 실행

```bash
python src/integrated_qa_pipeline.py
```

전체 QA 세션 생성 및 검증을 실행합니다.

---

## Text-Image QA 템플릿 시스템

Notion 가이드 기반 텍스트 중심 이미지 QA 세션 생성 시스템입니다.

### 주요 구성요소

**템플릿:**

- `templates/system/` - 설명문, 요약문, 추론, 전역 시스템 프롬프트
- `templates/user/` - 타겟 질의, 일반 사용자 입력
- `templates/eval/` - 3개 답변 비교 평가
- `templates/rewrite/` - 최고 답변 재작성
- `templates/fact/` - 사실 검증

**도구:**

- `scripts/build_session.py` - 3~4턴 세션 자동 구성
- `scripts/render_prompt.py` - 템플릿 렌더링
- `checks/detect_forbidden_patterns.py` - 금지 패턴 검출

### 빠른 시작

```bash
# 기본 세션 생성
python scripts/build_session.py

# 커스텀 컨텍스트로 세션 생성
python scripts/build_session.py --context examples/session_input.json

# 단일 템플릿 렌더링
python scripts/render_prompt.py --template system/text_image_qa_explanation_system.j2
```

### 주요 제약사항

- 세션당 3~4턴 제한
- 설명문/요약문 중 하나만 사용 (4턴 시 예외적 동시 허용)
- 추론 질의 가능한 경우 필수 포함
- 계산 요청 세션당 1회 제한
- 표/그래프 참조 금지 (텍스트만 사용)

자세한 내용은 `docs/guide_mapping.md`를 참조하세요.

---

## 라이선스

MIT License

## 참고 라이브러리

- [Google Gemini AI](https://ai.google.dev/)
- [Pydantic](https://docs.pydantic.dev/)
- [Rich](https://rich.readthedocs.io/)
- [Tenacity](https://tenacity.readthedocs.io/)
