# CSV 기반 검증 규칙 시스템

이 모듈은 CSV 파일과 YAML 파일에서 검증 규칙을 동적으로 로드하고 적용하는 시스템을 제공합니다.

## 구조

```
src/validation/
├── __init__.py          # 모듈 초기화
├── py.typed             # 타입 힌트 지원
└── rule_parser.py       # CSV/YAML 파서 및 규칙 관리자
```

## 주요 클래스

### RuleCSVParser

CSV 파일과 YAML 파일에서 검증 규칙을 파싱합니다.

**지원 파일:**
- `guide.csv`: 기본 검증 규칙 (시의성 표현, 문장 수 등)
- `qna.csv`: 상세 검증 체크리스트 (질의/답변/작업 규칙)
- `patterns.yaml`: 패턴 기반 검증 규칙 (금지된 패턴, 포맷팅 규칙)

**주요 메서드:**
- `parse_guide_csv()`: guide.csv 파싱
- `parse_qna_csv()`: qna.csv 파싱
- `parse_patterns_yaml()`: patterns.yaml 파싱
- `get_all_rules()`: 모든 규칙 통합 반환

### RuleManager

규칙 캐싱 및 조회를 관리합니다.

**주요 메서드:**
- `load_rules()`: 규칙 로드
- `get_temporal_rules()`: 시의성 표현 규칙 조회
- `get_sentence_rules()`: 문장 수 규칙 조회
- `get_question_checklist()`: 질의 체크리스트 조회
- `get_answer_checklist()`: 답변 체크리스트 조회

## 통합

### UnifiedValidator 통합

`src/qa/validator.py`의 `UnifiedValidator` 클래스에 CSV 기반 규칙이 통합되어 있습니다.

**새로운 검증 메서드:**
- `validate_sentence_count(answer)`: 동적 문장 수 규칙 적용
- `validate_temporal_expressions(text)`: 시의성 표현 검증
- `validate_forbidden_patterns(text)`: 금지된 패턴 검증
- `validate_formatting(text)`: 포맷팅 규칙 검증

## 사용 예시

### 기본 사용법

```python
from src.validation.rule_parser import RuleCSVParser, RuleManager

# 파서 생성
parser = RuleCSVParser(
    guide_path="data/neo4j/guide.csv",
    qna_path="data/neo4j/qna.csv",
    patterns_path="config/patterns.yaml"
)

# 규칙 매니저 생성 및 로드
manager = RuleManager(parser)
manager.load_rules()

# 규칙 조회
temporal_rules = manager.get_temporal_rules()
sentence_rules = manager.get_sentence_rules()
```

### UnifiedValidator 사용

```python
from src.qa.validator import UnifiedValidator

# 검증기 생성 (CSV 규칙 자동 로드)
validator = UnifiedValidator()

# 검증 실행
question = "질문 텍스트"
answer = "답변 텍스트"
result = validator.validate_all(answer, "explanation", question)

# 결과 확인
print(f"위반 사항: {len(result.violations)}")
print(f"점수: {result.score}")
```

## 설정 파일

### config/patterns.yaml

```yaml
forbidden_patterns:
  전체이미지: '\b전체\s*이미지(에 대해)?\s*(설명|요약)\b'
  표참조: '\b표\s*(에 따르면|에서 보이듯|참조)\b'

formatting_patterns:
  prose_bold_violation:
    pattern: '(?<!^)(?<!- )(?<!\d\. )\*\*[^*]+\*\*'
    description: '줄글 본문 내 볼드체 사용 금지'
    severity: 'error'
```

## 테스트

```bash
# 단위 테스트 실행
python -m pytest tests/unit/validation/ -v

# 예시 스크립트 실행
PYTHONPATH=. python examples/csv_validation_usage.py
```

## 특징

✅ **동적 규칙 로드**: CSV/YAML 파일 수정만으로 규칙 업데이트  
✅ **캐싱**: 규칙을 메모리에 캐싱하여 성능 최적화  
✅ **타입 안정성**: mypy strict mode 지원  
✅ **하위 호환성**: 기존 코드에 영향 없이 통합  
✅ **확장 가능**: 새로운 규칙 타입 추가 용이  

## 기여

새로운 검증 규칙을 추가하려면:

1. `config/patterns.yaml`에 패턴 추가
2. 필요시 `RuleCSVParser`에 파싱 로직 추가
3. `UnifiedValidator`에 검증 메서드 추가
4. 테스트 작성 및 실행
