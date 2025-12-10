#!/usr/bin/env python3
"""CSV 기반 검증 규칙 시스템 사용 예시.

이 스크립트는 새로운 CSV 기반 검증 규칙 시스템의 사용법을 보여줍니다.
"""

from __future__ import annotations

from src.qa.validator import UnifiedValidator
from src.validation.rule_parser import RuleCSVParser, RuleManager


def example_basic_usage() -> None:
    """기본 사용 예시."""
    print("=== CSV 기반 검증 규칙 시스템 기본 사용법 ===\n")

    # 1. 파서 생성 및 규칙 로드
    parser = RuleCSVParser(
        guide_path="data/neo4j/guide.csv",
        qna_path="data/neo4j/qna.csv",
        patterns_path="config/patterns.yaml",
    )

    # 2. 규칙 매니저 생성
    manager = RuleManager(parser)
    manager.load_rules()

    # 3. 규칙 조회
    print("📋 로드된 규칙:")
    print(f"  - 시의성 표현: {manager.get_temporal_rules()}")
    print(f"  - 문장 수 규칙: {manager.get_sentence_rules()}")
    print(f"  - 질의 체크리스트: {len(manager.get_question_checklist())}개 항목")
    print(f"  - 답변 체크리스트: {len(manager.get_answer_checklist())}개 항목")
    print()


def example_validator_usage() -> None:
    """통합 검증기 사용 예시."""
    print("=== UnifiedValidator 사용법 ===\n")

    # 검증기 생성 (CSV 규칙 자동 로드)
    validator = UnifiedValidator()

    # 테스트 데이터
    question = "전체 이미지를 설명해줘"
    answer = "이미지는 다음과 같은 내용을 보여줍니다. 첫 번째 내용입니다. 두 번째 내용입니다."

    # 검증 실행
    result = validator.validate_all(answer, "explanation", question)

    # 결과 출력
    print("검증 결과:")
    print(f"  - 위반 사항: {len(result.violations)}개")
    for violation in result.violations:
        vtype = violation.get("type", "unknown")
        message = violation.get("message") or violation.get("description", "")
        severity = violation.get("severity", "info")
        print(f"    [{severity.upper()}] {vtype}: {message}")

    print(f"  - 경고: {len(result.warnings)}개")
    for warning in result.warnings:
        print(f"    - {warning}")

    print(f"  - 점수: {result.score}")
    print()


def example_individual_validators() -> None:
    """개별 검증 메서드 사용 예시."""
    print("=== 개별 검증 메서드 사용법 ===\n")

    validator = UnifiedValidator()

    # 문장 수 검증
    answer_short = "짧은 답변입니다."
    violations = validator.validate_sentence_count(answer_short)
    print(f"📝 문장 수 검증 (짧은 답변): {len(violations)}개 위반")
    for v in violations:
        print(f"   - {v['message']}")
    print()

    # 시의성 표현 검증
    answer_temporal = "현재 상황을 보면 최근 동향이 좋습니다."
    violations = validator.validate_temporal_expressions(answer_temporal)
    print(f"⏰ 시의성 표현 검증: {len(violations)}개 발견")
    for v in violations:
        print(f"   - {v['message']}")
    print()

    # 금지된 패턴 검증
    question_forbidden = "전체 이미지에 대해 설명해줘"
    violations = validator.validate_forbidden_patterns(question_forbidden)
    print(f"🚫 금지된 패턴 검증: {len(violations)}개 위반")
    for v in violations:
        print(f"   - {v['type']}: {v['match']}")
    print()


def main() -> None:
    """메인 함수."""
    print("\n" + "=" * 60)
    print("CSV 기반 검증 규칙 시스템 사용 예시")
    print("=" * 60 + "\n")

    example_basic_usage()
    example_validator_usage()
    example_individual_validators()

    print("=" * 60)
    print("✅ 모든 예시 실행 완료!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
