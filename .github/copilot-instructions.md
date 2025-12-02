# GitHub Copilot Instructions

## 코드 스타일 및 품질 체크리스트

### ⚠️ PR 생성 전 필수 사항

모든 PR을 생성하기 **전에** 다음 명령어들을 **반드시** 실행해야 합니다:

```bash
# 1. 코드 포맷팅 (자동 수정)
uv run ruff format .

# 2. 린트 검사 및 자동 수정
uv run ruff check --fix .

# 3. 타입 체크
uv run mypy src/ scripts/

# 4. 테스트 실행
uv run pytest
```

### 🎯 중요 규칙

1. **절대 `ruff format`을 건너뛰지 마세요**
   - CI에서 `ruff format --check`가 실패하면 안 됩니다
   - 포맷팅 오류로 인한 PR은 반복적인 문제를 야기합니다

2. **Deprecated Imports 사용 금지**
   - 구버전 import 경로를 사용하지 마세요
   - 예시:
     - ❌ `from src.utils import ...`
     - ✅ `from src.infra.utils import ...`
     - ❌ `from src.constants import ...`
     - ✅ `from src.config.constants import ...`

3. **타입 힌트 필수**
   - 모든 함수에 타입 힌트를 추가하세요
   - `mypy --strict` 모드를 지향합니다

4. **테스트 커버리지 유지**
   - 새로운 코드에는 반드시 테스트를 작성하세요
   - 최소 80% 커버리지를 유지하세요

### 📁 프로젝트 구조

```
src/
├── agent/          # 에이전트 코어 로직
├── analysis/       # 분석 모듈
├── config/         # 설정 관리
├── core/           # 핵심 인터페이스 및 모델
├── features/       # 기능 모듈
├── graph/          # Neo4j 그래프
├── infra/          # 인프라 (로깅, 헬스체크)
├── llm/            # LLM 관련
├── qa/             # QA 시스템
├── workflow/       # 워크플로우 로직
└── web/            # 웹 API
```

### 🚫 금지 사항

- ❌ `--no-verify`로 pre-commit hook 건너뛰기
- ❌ 테스트 없이 코드 변경
- ❌ 타입 힌트 없는 새 함수
- ❌ CI 실패를 무시하고 PR 병합
- ❌ 하드코딩된 설정값 (환경 변수 사용)

### ✅ 권장 워크플로우

1. 기능 브랜치 생성
2. 코드 작성
3. 테스트 작성
4. Pre-commit 체크 통과 확인
5. **ruff format & check 실행**
6. 테스트 실행
7. PR 생성
8. CI 통과 확인
9. 리뷰 후 병합

### 🔧 자주 사용하는 명령어

```bash
# 전체 품질 체크
uv run ruff format . && uv run ruff check --fix . && uv run mypy src/ && uv run pytest

# Pre-commit hook 수동 실행
pre-commit run --all-files

# 특정 파일만 포맷팅
uv run ruff format path/to/file.py

# 커버리지 리포트
uv run pytest --cov=src --cov-report=html
```

---

> 💡 **참고**: 이 가이드라인을 따르면 반복적인 포맷팅 PR을 방지하고 코드 품질을 높일 수 있습니다.
