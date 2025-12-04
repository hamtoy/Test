"""피드백 기반 Constraint 검증 테스트"""

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
    def test_temporal_expression_check(self, mock_kg):
        """시의성 표현 검증 테스트"""
        validator = CrossValidationSystem(mock_kg)

        # 위반 사례
        answer_bad = "최근 주가가 상승했습니다."
        result = validator._check_temporal_expressions(answer_bad)
        assert len(result) > 0
        assert "시의성 표현" in result[0]

        # 정상 사례 1: 이미지 기준
        answer_good1 = "최근(이미지 기준) 주가가 상승했습니다."
        result = validator._check_temporal_expressions(answer_good1)
        assert len(result) == 0

        # 정상 사례 2: 보고서 기준
        answer_good2 = "올해(보고서 기준) 매출이 증가했습니다."
        result = validator._check_temporal_expressions(answer_good2)
        assert len(result) == 0

    def test_repetition_check(self, mock_kg):
        """반복 표현 검증 테스트"""
        validator = CrossValidationSystem(mock_kg)

        # 위반 사례: '상승했습니다' 3회 반복 (max_repeat=2)
        answer_bad = "주가가 상승했습니다. 매출도 상승했습니다. 이익도 상승했습니다."
        result = validator._check_repetition(answer_bad, max_repeat=2)
        assert len(result) > 0
        assert "과도한 반복" in result[0]

        # 정상 사례
        answer_good = "주가가 상승했습니다. 매출이 증가했습니다."
        result = validator._check_repetition(answer_good, max_repeat=2)
        assert len(result) == 0

    def test_formatting_rules(self, mock_kg):
        """형식 규칙 검증 테스트"""
        validator = CrossValidationSystem(mock_kg)

        # 위반 사례 1: 숫자 불릿 사이 빈 줄
        answer_bad1 = "1. 첫 번째\n\n2. 두 번째"
        result = validator._check_formatting_rules(answer_bad1)
        assert any("문단 구분" in v for v in result)

        # 위반 사례 2: 기호 불릿 사이 빈 줄
        answer_bad2 = "- 첫 번째\n\n- 두 번째"
        result = validator._check_formatting_rules(answer_bad2)
        assert any("문단 구분" in v for v in result)

        # 위반 사례 3: 불릿 혼용
        answer_bad3 = "- 첫 번째\n* 두 번째"
        result = validator._check_formatting_rules(answer_bad3)
        assert any("불릿 표시 일관성" in v for v in result)

        # 정상 사례
        answer_good = "1. 첫 번째\n2. 두 번째"
        result = validator._check_formatting_rules(answer_good)
        assert len(result) == 0

    def test_check_rule_compliance_integration(self, mock_kg):
        """_check_rule_compliance 통합 테스트"""
        validator = CrossValidationSystem(mock_kg)

        # Mock Constraint 설정
        mock_kg.get_constraints_for_query_type.return_value = [
            {
                "id": "temporal_expression_check",
                "type": "content_validation",
                "pattern": "(최근|현재)",
                "description": "시의성 표현 체크",
            }
        ]

        # 위반 사례 테스트
        answer = "최근 데이터에 따르면..."
        result = validator._check_rule_compliance(answer, "target")

        assert result["score"] < 1.0
        assert len(result["violations"]) > 0
        assert any("시의성 표현" in v for v in result["violations"])
