# Test Repository

개인 테스트 및 실험용 저장소입니다. Google Gemini AI를 활용한 다양한 워크플로우와 스크립트를 포함합니다.

## 📂 프로젝트 구조

```
Test/
├── .gitignore
├── README.md
├── DEPLOYMENT_VERIFIED.md
├── UV_GUIDE.md
├── requirements.txt
├── list_models.py           # Gemini 모델 리스트 조회
├── qa_generator.py          # Q&A 자동 생성 스크립트
├── data/                    # 데이터 파일 저장소
│   ├── inputs/
│   └── outputs/
├── src/                     # 소스 코드 패키지
│   ├── __init__.py
│   ├── agent.py
│   ├── config.py
│   ├── data_loader.py
│   ├── logging_setup.py
│   ├── main.py
│   ├── models.py
│   └── utils.py
├── templates/               # Jinja2 템플릿
│   ├── prompt_eval.j2
│   ├── prompt_query_gen.j2
│   ├── prompt_rewrite.j2
│   ├── query_gen_user.j2
│   └── rewrite_user.j2
└── tests/                   # 테스트 스위트
    ├── __init__.py
    ├── test_agent.py
    └── test_dependency_injection.py
```

## 🚀 주요 기능

### 1. QA Generator (`qa_generator.py`)
OCR 텍스트를 기반으로 질의와 답변을 자동 생성하는 스크립트입니다.

**특징:**
- OCR 텍스트에서 자동 질의 생성 (3개 또는 4개 모드)
- 생성된 질의에 대한 답변 자동 생성
- JSON 및 Markdown 형식으로 결과 저장

**사용법:**
```bash
# 환경 변수 설정
export GEMINI_API_KEY=your_api_key_here

# 스크립트 실행
python qa_generator.py
```

### 2. Gemini Workflow (`src/`)
Q&A 응답을 평가하고 재작성하는 프로덕션급 워크플로우 시스템입니다.

**특징:**
- 🤖 지능형 질의 생성
- 📊 다중 후보 평가
- ✍️ 답변 재작성
- 💰 비용 추적
- 🛡️ Rate limiting, 환각 감지

**사용법:**
```bash
# 기본 실행
python -m src.main

# CHAT 모드 실행
python -m src.main --mode CHAT --intent "요약해줘"

# 커스텀 입력 파일 지정
python -m src.main --ocr-file custom.txt --cand-file candidates.json
```

### 3. Model Utilities (`list_models.py`)
사용 가능한 Gemini 모델 리스트를 조회합니다.

## ⚙️ 설치 및 설정

### 필수 요구사항
- Python 3.10 이상
- Google Gemini API 키 ([여기서 발급](https://makersuite.google.com/app/apikey))

### 설치

#### 방법 A: pip 사용
```bash
git clone https://github.com/hamtoy/Test.git
cd Test
pip install -r requirements.txt
```

#### 방법 B: uv 사용 (권장 - 10-100배 빠름)
```bash
pip install uv
cd Test
uv pip install -r requirements.txt
```

자세한 내용은 [UV_GUIDE.md](UV_GUIDE.md)를 참조하세요.

### 환경 변수 설정

`.env` 파일을 프로젝트 루트에 생성:

```bash
# 필수
GEMINI_API_KEY=your_api_key_here

# 선택 (기본값 있음)
GEMINI_MODEL_NAME=gemini-1.5-pro
GEMINI_MAX_OUTPUT_TOKENS=8192
GEMINI_TIMEOUT=120
GEMINI_MAX_CONCURRENCY=5
GEMINI_TEMPERATURE=0.2
GEMINI_CACHE_SIZE=50
GEMINI_CACHE_TTL_MINUTES=10
LOG_LEVEL=INFO
```

## 📦 의존성

주요 라이브러리:
- `google-generativeai` - Gemini API 클라이언트
- `pydantic` - 데이터 검증
- `jinja2` - 템플릿 엔진
- `rich` - 터미널 UI
- `tenacity` - 재시도 로직
- `aiolimiter` - 비동기 rate limiting
- `pytest` - 테스트 프레임워크

전체 목록은 [`requirements.txt`](requirements.txt)를 참조하세요.

## 🧪 테스트

```bash
# 모든 테스트 실행
pytest tests/ -v

# 특정 테스트 파일 실행
pytest tests/test_agent.py -v

# 커버리지 포함 실행
pytest tests/ --cov=src --cov-report=html
```

## 📊 주요 기능 상세

### Hallucination Detection
LLM의 "최선의 후보" 선택이 실제 점수와 일치하는지 자동 검증:

```python
@model_validator(mode='after')
def validate_best_candidate(self):
    actual_best = max(self.evaluations, key=lambda x: x.score)
    if self.best_candidate != actual_best.candidate_id:
        logger.warning("LLM Hallucination Detected - Auto-correcting")
        self.best_candidate = actual_best.candidate_id
```

### Dual Rate Control
- **Semaphore**: 동시 API 호출 제한 (공간적 제어)
- **Rate Limiter**: 분당 요청 수 제한 (시간적 제어)
- `429 Too Many Requests` 에러 방지

### Dependency Injection
테스트 가능한 아키텍처:

```python
# 프로덕션
agent = GeminiAgent(config, jinja_env=real_env)

# 테스트
agent = GeminiAgent(config, jinja_env=mock_env)
```

## 📝 환경 변수

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `GEMINI_API_KEY` | _필수_ | Gemini API 키 |
| `GEMINI_MODEL_NAME` | `gemini-1.5-pro` | 사용할 모델 |
| `GEMINI_MAX_OUTPUT_TOKENS` | `8192` | 최대 출력 토큰 수 |
| `GEMINI_TIMEOUT` | `120` | API 타임아웃 (초) |
| `GEMINI_MAX_CONCURRENCY` | `5` | 최대 동시 요청 수 |
| `GEMINI_TEMPERATURE` | `0.2` | 샘플링 온도 |
| `GEMINI_CACHE_SIZE` | `50` | 컨텍스트 캐시 크기 |
| `GEMINI_CACHE_TTL_MINUTES` | `10` | 캐시 TTL (분) |
| `LOG_LEVEL` | `INFO` | 로깅 레벨 |
| `PROJECT_ROOT` | _자동_ | 프로젝트 루트 경로 |

## 📚 추가 문서

- **[DEPLOYMENT_VERIFIED.md](DEPLOYMENT_VERIFIED.md)** - 배포 검증 문서
- **[UV_GUIDE.md](UV_GUIDE.md)** - UV 패키지 매니저 가이드

## 🎯 용도

이 저장소는 다음과 같은 목적으로 사용됩니다:

- Gemini API 실험 및 테스트
- 워크플로우 프로토타이핑
- Q&A 시스템 개발
- Python 코드 학습 및 실습

## 📄 라이선스

개인 프로젝트 - MIT License

## 🙏 참고

Built with:
- [Google Gemini AI](https://ai.google.dev/)
- [Pydantic](https://docs.pydantic.dev/)
- [Rich](https://rich.readthedocs.io/)
- [Tenacity](https://tenacity.readthedocs.io/)

---

**개인 테스트용 저장소입니다**