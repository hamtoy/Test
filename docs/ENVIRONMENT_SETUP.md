# 환경 설정 가이드

## 필수 요구사항

- Python 3.10 이상
- Google Gemini API 키 ([발급 링크](https://makersuite.google.com/app/apikey))

## 빠른 시작

### 1. 환경 변수 설정

`.env.example`을 복사하여 `.env` 파일 생성:

```bash
cp .env.example .env
```

`.env` 파일 편집:

```bash
# 필수
GEMINI_API_KEY=your_actual_api_key_here
```

> **중요**: API 키는 `AIza`로 시작하는 39자 문자열이어야 합니다.

### 2. 의존성 설치

```bash
# uv 사용 (권장)
pip install uv
uv sync

# 또는 pip 사용
pip install -e .
```

### 3. 실행

```bash
# 기본 워크플로우 실행
python -m src.main --mode AUTO --ocr-file example_ocr.txt --cand-file example_candidates.json
```

## 선택 사항

### QA RAG 시스템 사용 시

Neo4j 데이터베이스가 필요합니다. `.env`에 추가:

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

### 개발 환경 (권장)

개발/테스트 도구 설치:

```bash
pip install -e ".[dev]"
pre-commit install
```

빠른 품질 검사:

```bash
pre-commit run --all-files
uv run pytest tests/ --cov=src --cov-fail-under=75
```

## 추가 정보

모든 환경 변수 및 상세 설정은 [README.md](../README.md)를 참조하세요.
