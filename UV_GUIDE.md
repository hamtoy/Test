# UV 패키지 매니저 설정

이 프로젝트는 `uv`를 사용한 빠른 패키지 관리를 지원합니다.

## UV 사용법

```bash
# UV 설치 (한 번만)
pip install uv

# 프로젝트 의존성 설치
uv pip install -r requirements.txt

# 또는 개별 패키지 추가
uv pip install google-generativeai pydantic-settings tenacity jinja2 rich aiofiles python-dotenv pytest

# 프로그램 실행
uv run python -m src.main
```

## UV의 장점

- ⚡ **빠름**: Rust 기반으로 pip보다 10-100배 빠릅니다
- 🔒 **안정성**: 의존성 해결이 더 정확합니다
- 🎯 **간편함**: 가상환경을 자동으로 관리합니다

## 기존 pip 사용도 가능합니다

`requirements.txt`를 그대로 사용할 수 있습니다:

```bash
pip install -r requirements.txt
python -m src.main
```
