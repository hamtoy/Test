# UV 패키지 매니저 가이드

이 프로젝트는 `uv`를 사용한 빠른 패키지 관리를 지원합니다. `uv`는 Rust로 작성된 Python 패키지 매니저로, `pip`보다 10-100배 빠릅니다.

## UV 설치

```bash
pip install uv
```

## UV 사용법

### 의존성 설치

프로젝트는 `pyproject.toml`을 사용하여 의존성을 관리합니다.

```bash
# 런타임 의존성만 설치
uv sync

# 개발/테스트/문서 의존성까지 모두 설치
uv sync --extra dev
```

### 가상환경 활성화

`uv sync`는 자동으로 `.venv` 디렉토리에 가상환경을 생성합니다.

```bash
# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate
```

### 프로그램 실행

```bash
# 가상환경 활성화 후
python -m src.main

# 또는 uv run 사용 (자동으로 가상환경 활성화)
uv run python -m src.main

# 샘플 데이터로 실행
uv run python -m src.main --mode AUTO --ocr-file example_ocr.txt --cand-file example_candidates.json
```

### 패키지 추가

```bash
# 런타임 의존성 추가
uv add package-name

# 개발 의존성 추가
uv add --dev package-name
```

## UV의 장점

- ⚡ **빠름**: Rust 기반으로 pip보다 10-100배 빠릅니다
- 🔒 **안정성**: 의존성 해결이 더 정확합니다
- 🎯 **간편함**: 가상환경을 자동으로 관리합니다
- 📦 **최신 표준**: `pyproject.toml` 기반 워크플로우 지원

## 기존 pip 사용도 가능합니다

`pip`를 사용하려면:

```bash
# editable 설치
pip install -e .

# 개발/테스트/문서 의존성까지 설치
pip install -e ".[dev]"

# 프로그램 실행
python -m src.main
```

## 참고

- UV 공식 문서: [https://github.com/astral-sh/uv](https://github.com/astral-sh/uv)
- 자세한 기여 방법은 [CONTRIBUTING.md](CONTRIBUTING.md)를 참조하세요
- 전체 사용법은 [README.md](README.md)를 참조하세요
