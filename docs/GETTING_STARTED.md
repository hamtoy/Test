# 시작 가이드 (Getting Started)

이 가이드는 Gemini 워크플로우 Q&A 시스템을 처음 사용하는 분들을 위한 단계별 튜토리얼입니다.

## 📋 사전 요구사항

- **Python 3.10 이상**
- **Google Gemini API 키** ([발급 링크](https://makersuite.google.com/app/apikey))

### 선택 요구사항 (RAG 시스템 사용 시)

- Neo4j 데이터베이스 ([Aura 무료](https://neo4j.com/cloud/aura-free/))
- Notion 계정 (규칙 데이터 소스)

---

## 🚀 설치 및 설정

### 1단계: 저장소 클론

```bash
git clone https://github.com/hamtoy/Test.git
cd Test
```

### 2단계: 의존성 설치

```bash
# 기본 설치 (핵심 기능만)
pip install -e .

# 또는 전체 기능 설치
pip install -e ".[all]"

# 개발 환경 (테스트, 린트 도구 포함)
pip install -e ".[dev]"
```

설치 옵션에 대한 자세한 내용은 [설정 가이드](CONFIGURATION.md)를 참조하세요.

### 3단계: 환경 변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 편집하여 API 키를 설정합니다:

```bash
# 필수 설정
GEMINI_API_KEY=AIza... # 발급받은 API 키
```

### 4단계: API 키 확인

```bash
python -m src.list_models
```

성공하면 사용 가능한 모델 목록이 표시됩니다.

---

## 🎯 첫 번째 워크플로우 실행

### 대화형 메뉴 모드

```bash
python -m src.main
```

다음과 같은 메뉴가 표시됩니다:

```
═══ Gemini Workflow System ═══
규칙 준수 리라이팅 · 검수 반려 방지

상태: Neo4j ✓ | LATS ✓

1. 🔄 질의 생성 및 평가
2. ✅ 검수 (질의/답변)
3. 📊 캐시 통계 분석
4. 🚪 종료

선택 [1]:
```

### 기본 워크플로우

1. **`1` 선택** - 질의 생성 및 평가
2. **OCR 파일명 입력** (기본: `input_ocr.txt`)
3. **후보 답변 파일명 입력** (기본: `input_candidates.json`)
4. **사용자 의도 입력** (선택사항)
5. **결과 확인**

---

## 📁 입력 파일 준비

### OCR 텍스트 파일

`data/inputs/input_ocr.txt`:

```text
이것은 OCR로 인식된 텍스트입니다.
여기에 분석할 내용을 작성합니다.
```

### 후보 답변 파일

`data/inputs/input_candidates.json`:

```json
{
  "A": "첫 번째 후보 답변입니다.",
  "B": "두 번째 후보 답변입니다.",
  "C": "세 번째 후보 답변입니다."
}
```

---

## 📊 결과 확인

### 출력 파일

결과는 `data/outputs/` 디렉토리에 저장됩니다:

```
data/outputs/result_turn_1_20250129_120000.md
```

### 콘솔 출력 예시

```
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

---

## 🔧 일반적인 문제 해결

### API 키 오류

```
GEMINI_API_KEY validation failed:
  - Must start with 'AIza'
```

**해결 방법:**
1. `.env` 파일에서 API 키 형식 확인 (AIza로 시작, 39자)
2. 공백이나 따옴표가 없는지 확인

### 템플릿 디렉토리 오류

```
Templates directory missing: /path/to/templates
```

**해결 방법:**
1. `templates/` 디렉토리가 있는지 확인
2. `PROJECT_ROOT` 환경 변수 설정

---

## ⏭️ 다음 단계

- [설정 가이드](CONFIGURATION.md) - 모든 환경 변수 설명
- [고급 기능](ADVANCED_FEATURES.md) - LATS, RAG, 멀티모달
- [캐싱 전략](CACHING.md) - 비용 최적화
- [문제 해결](TROUBLESHOOTING.md) - 일반적인 오류 해결
