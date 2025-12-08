# mypy: ignore-errors
"""피드백 기반 Constraint 검증 테스트 (Phase 4 업데이트)"""

from unittest.mock import MagicMock

import pytest

from src.analysis.cross_validation import CrossValidationSystem
from src.qa.rag_system import QAKnowledgeGraph


@pytest.fixture
def mock_kg():
    kg = MagicMock(spec=QAKnowledgeGraph)
    # 기본적으로 빈 리스트 반환
    kg.get_constraints_for_query_type.return_value = []
    return kg


class TestFeedbackConstraints:
    def test_temporal_expression_check_disabled(self, mock_kg):
        """Phase 4: 시의성 표현 검증 비활성화 테스트"""
        validator = CrossValidationSystem(mock_kg)

        # Phase 4: 이제 모든 시의성 표현이 허용됨
        answer_with_temporal = "최근 주가가 상승했습니다."
        result = validator._check_temporal_expressions(answer_with_temporal)
        assert len(result) == 0  # 검증 비활성화

        # 기준 표기가 없어도 허용됨
        answer_no_marker = "현재 시장 상황은 좋습니다."
        result = validator._check_temporal_expressions(answer_no_marker)
        assert len(result) == 0

    def test_repetition_check_disabled(self, mock_kg):
        """Phase 4: 명사 반복 검증 비활성화 테스트"""
        validator = CrossValidationSystem(mock_kg)

        # Phase 4: 명사 반복이 허용됨
        answer_with_repetition = (
            "시장 상황을 보면 시장이 어렵습니다. 노동 시장도 노동력 부족이 문제입니다."
        )
        result = validator._check_repetition(answer_with_repetition)
        assert len(result) == 0  # 검증 비활성화

    def test_formatting_rules(self, mock_kg):
        """형식 규칙 검증 테스트 (Phase 4: 문단 구분 규칙 제거)"""
        validator = CrossValidationSystem(mock_kg)

        # Phase 4: 문단 구분 규칙 제거됨 - 불릿 일관성만 검사
        # 위반 사례: 불릿 혼용
        answer_bad = "- 첫 번째\n* 두 번째"
        result = validator._check_formatting_rules(answer_bad)
        assert any("불릿 표시 일관성" in v for v in result)

        # 정상 사례: 일관된 불릿
        answer_good1 = "1. 첫 번째\n2. 두 번째"
        result = validator._check_formatting_rules(answer_good1)
        assert len(result) == 0

        answer_good2 = "- 첫 번째\n- 두 번째"
        result = validator._check_formatting_rules(answer_good2)
        assert len(result) == 0

    def test_predicate_repetition_check_3_items(self, mock_kg):
        """서술어 반복 검증: 목록 3개 이하"""
        validator = CrossValidationSystem(mock_kg)

        # 위반 사례: 3개 목록에서 서술어 반복
        answer_bad = (
            "1. 금리가 상승했습니다\n2. 물가가 상승했습니다\n3. 환율이 하락했습니다"
        )
        result = validator._check_predicate_repetition(answer_bad)
        assert len(result) > 0
        assert "3개 이하는 동일 서술어 불가" in result[0]

        # 정상 사례: 3개 목록에서 모두 다른 서술어
        answer_good = (
            "1. 금리가 상승했습니다\n2. 물가가 증가했습니다\n3. 환율이 하락했습니다"
        )
        result = validator._check_predicate_repetition(answer_good)
        assert len(result) == 0

    def test_predicate_repetition_check_5_items(self, mock_kg):
        """서술어 반복 검증: 목록 5개 (50% 미만 허용)"""
        validator = CrossValidationSystem(mock_kg)

        # 정상 사례: 5개 목록에서 2회 반복 (50% 미만)
        answer_good = (
            "1. 금리가 상승했습니다\n"
            "2. 물가가 상승했습니다\n"
            "3. 환율이 하락했습니다\n"
            "4. 주가가 증가했습니다\n"
            "5. 채권이 안정됩니다"
        )
        result = validator._check_predicate_repetition(answer_good)
        assert len(result) == 0

        # 위반 사례: 5개 목록에서 3회 반복 (50% 이상)
        answer_bad1 = (
            "1. 금리가 상승했습니다\n"
            "2. 물가가 상승했습니다\n"
            "3. 환율이 상승했습니다\n"
            "4. 주가가 하락했습니다\n"
            "5. 채권이 안정됩니다"
        )
        result = validator._check_predicate_repetition(answer_bad1)
        assert len(result) > 0
        assert "최대 2회" in result[0]  # 5개 목록의 50% 미만은 2회

        # 위반 사례: 2개 이상의 서술어가 동시에 반복
        answer_bad2 = (
            "1. 금리가 상승했습니다\n"
            "2. 물가가 상승했습니다\n"
            "3. 환율이 하락했습니다\n"
            "4. 주가가 하락했습니다\n"
            "5. 채권이 안정됩니다"
        )
        result = validator._check_predicate_repetition(answer_bad2)
        assert len(result) > 0
        assert "2개 이상의 서술어 동시 반복 불가" in result[0]

    def test_formatting_rules_with_predicate_check(self, mock_kg):
        """형식 규칙이 서술어 검증을 호출하는지 확인"""
        validator = CrossValidationSystem(mock_kg)

        # 목록형 답변에서 서술어 반복 검증
        answer = (
            "1. 금리가 상승했습니다\n2. 물가가 상승했습니다\n3. 환율이 상승했습니다"
        )
        result = validator._check_formatting_rules(answer)
        # 3개 이하 목록에서 서술어 반복 위반 감지
        assert len(result) > 0
        assert "동일 서술어 불가" in result[0]

    def test_check_rule_compliance_integration(self, mock_kg):
        """_check_rule_compliance 통합 테스트 (Phase 4 업데이트)"""
        validator = CrossValidationSystem(mock_kg)

        # Mock Constraint 설정
        mock_kg.get_constraints_for_query_type.return_value = [
            {
                "id": "temporal_expression_check",
                "type": "content_validation",
                "pattern": "(최근|현재)",
                "description": "시의성 표현 체크",
            },
        ]

        # Phase 4: 시의성 표현 검증이 비활성화되어 위반 없음
        answer = "최근 데이터에 따르면..."
        result = validator._check_rule_compliance(answer, "target")

        # 검증이 비활성화되었으므로 위반 없음
        assert result["score"] == 1.0
        assert len(result["violations"]) == 0
