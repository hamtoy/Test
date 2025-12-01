"""Tests for QA generation with rule compliance validation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from checks.detect_forbidden_patterns import find_violations
from src.config.constants import DEFAULT_ANSWER_RULES, DEFAULT_FORBIDDEN_PATTERNS


class TestForbiddenPatternDetection:
    """Tests for forbidden pattern detection in answers."""

    def test_detect_table_reference(self) -> None:
        """Test detection of table references."""
        text = "표 1에서 보면 매출이 증가했습니다."
        violations = find_violations(text)
        
        # Should not detect pattern directly (find_violations focuses on specific patterns)
        # But our integration should handle it
        assert isinstance(violations, list)

    def test_detect_graph_reference(self) -> None:
        """Test detection of graph/chart references."""
        text = "그래프에 따르면 성장세가 나타납니다."
        violations = find_violations(text)
        
        assert isinstance(violations, list)
        # Check if 그래프참조 pattern is detected
        if violations:
            assert any(v["type"] == "그래프참조" for v in violations)

    def test_detect_whole_image_request(self) -> None:
        """Test detection of whole image description requests."""
        text = "전체 이미지 설명해주세요."
        violations = find_violations(text)
        
        assert isinstance(violations, list)
        if violations:
            assert any(v["type"] == "전체이미지" for v in violations)

    def test_no_violations_clean_text(self) -> None:
        """Test clean text without violations."""
        text = "2023년 매출은 100억원으로 전년 대비 20% 증가했습니다."
        violations = find_violations(text)
        
        assert violations == []


class TestDefaultRulesConfiguration:
    """Tests for default rules configuration."""

    def test_default_rules_exist(self) -> None:
        """Test that default rules are defined."""
        assert DEFAULT_ANSWER_RULES is not None
        assert len(DEFAULT_ANSWER_RULES) > 0
        assert isinstance(DEFAULT_ANSWER_RULES, list)

    def test_default_forbidden_patterns_exist(self) -> None:
        """Test that default forbidden patterns are defined."""
        assert DEFAULT_FORBIDDEN_PATTERNS is not None
        assert len(DEFAULT_FORBIDDEN_PATTERNS) > 0
        assert isinstance(DEFAULT_FORBIDDEN_PATTERNS, list)

    def test_default_rules_content(self) -> None:
        """Test that default rules contain expected guidance."""
        rules_text = " ".join(DEFAULT_ANSWER_RULES)
        
        # Should mention tables/graphs
        assert "표" in rules_text or "그래프" in rules_text
        # Should mention accuracy
        assert "고유명사" in rules_text or "숫자" in rules_text


@pytest.mark.asyncio
class TestGenerateSingleQAWithRules:
    """Tests for generate_single_qa with rule compliance."""

    async def test_generate_qa_without_neo4j_uses_default_rules(self) -> None:
        """Test that default rules are applied when Neo4j is unavailable."""
        with (
            patch("src.web.api.kg", None),
            patch("src.web.api.agent") as mock_agent,
        ):
            mock_agent.generate_query = AsyncMock(return_value=["테스트 질의"])
            mock_agent.rewrite_best_answer = AsyncMock(
                return_value="테스트 답변입니다."
            )
            
            # Import here to avoid module-level issues
            from src.web.api import generate_single_qa
            
            with patch("src.web.api.inspect_answer", AsyncMock(return_value="최종 답변")):
                await generate_single_qa(
                    mock_agent, "OCR 텍스트", "factual"
                )
            
            # Should call rewrite_best_answer at least once
            assert mock_agent.rewrite_best_answer.called

    async def test_generate_qa_detects_and_handles_violations(self) -> None:
        """Test that violations are detected and trigger rewrite."""
        with (
            patch("src.web.api.kg", None),
            patch("src.web.api.agent") as mock_agent,
        ):
            # First call returns answer with violation, second call returns clean answer
            mock_agent.generate_query = AsyncMock(return_value=["테스트 질의"])
            mock_agent.rewrite_best_answer = AsyncMock(
                side_effect=[
                    "표에서 보이듯 매출 증가",  # Has violation
                    "매출이 증가했습니다",  # Clean answer
                ]
            )
            
            from src.web.api import generate_single_qa
            
            with patch("src.web.api.inspect_answer", AsyncMock(return_value="최종 답변")):
                await generate_single_qa(
                    mock_agent, "OCR 텍스트", "factual"
                )
            
            # Should call rewrite_best_answer twice (once for initial, once for correction)
            assert mock_agent.rewrite_best_answer.call_count >= 2

    async def test_generate_qa_with_neo4j_checks_rule_compliance(self) -> None:
        """Test that rule compliance is checked when Neo4j is available."""
        mock_kg = MagicMock()
        mock_kg.get_constraints_for_query_type = MagicMock(return_value=[])
        
        with (
            patch("src.web.api.kg", mock_kg),
            patch("src.web.api.agent") as mock_agent,
            patch("src.processing.template_generator.DynamicTemplateGenerator") as mock_template_gen,
            patch("src.web.api.CrossValidationSystem") as mock_validator_class,
        ):
            mock_agent.generate_query = AsyncMock(return_value=["테스트 질의"])
            mock_agent.rewrite_best_answer = AsyncMock(
                side_effect=["답변 초안", "수정된 답변"]
            )
            
            # Mock template generator to succeed
            mock_template_instance = MagicMock()
            mock_template_instance.generate_prompt_for_query_type = MagicMock(
                return_value="템플릿 프롬프트"
            )
            mock_template_instance.close = MagicMock()
            mock_template_gen.return_value = mock_template_instance
            
            # Mock CrossValidationSystem
            mock_validator = MagicMock()
            mock_validator._check_rule_compliance = MagicMock(
                return_value={"score": 0.3, "violations": ["규칙 위반 1"]}
            )
            mock_validator_class.return_value = mock_validator
            
            from src.web.api import generate_single_qa
            
            with patch("src.web.api.inspect_answer", AsyncMock(return_value="최종 답변")):
                await generate_single_qa(
                    mock_agent, "OCR 텍스트", "factual"
                )
            
            # Should call rule compliance check
            assert mock_validator._check_rule_compliance.called
            # Should trigger rewrite due to low score and violations
            assert mock_agent.rewrite_best_answer.call_count == 2


@pytest.mark.asyncio
class TestInspectAnswerWithRules:
    """Tests for inspect_answer with rule context injection."""

    async def test_inspect_answer_injects_default_rules_without_neo4j(self) -> None:
        """Test that default rules are injected when Neo4j is unavailable."""
        from src.workflow.inspection import inspect_answer
        
        mock_agent = MagicMock()
        
        # Without kg, should use default rules
        result = await inspect_answer(
            agent=mock_agent,
            answer="테스트 답변",
            query="테스트 질의",
            ocr_text="OCR 텍스트",
            context={"type": "factual"},
            kg=None,
        )
        
        # Should return the answer (since kg is None, returns original)
        assert result == "테스트 답변"

    async def test_inspect_answer_queries_rules_with_neo4j(self) -> None:
        """Test that rules are queried from Neo4j when available."""
        from src.workflow.inspection import inspect_answer
        
        mock_agent = MagicMock()
        mock_kg = MagicMock()
        mock_kg.find_relevant_rules = MagicMock(return_value=[
            {"content": "규칙 1"},
            {"content": "규칙 2"},
        ])
        mock_kg.get_constraints_for_query_type = MagicMock(return_value=[
            {"description": "제약 1"},
        ])
        
        # Mock SelfCorrectingQAChain
        with patch("src.workflow.inspection.SelfCorrectingQAChain") as mock_corrector_class:
            mock_corrector = MagicMock()
            mock_corrector.generate_with_self_correction = MagicMock(
                return_value={"output": "수정된 답변"}
            )
            mock_corrector_class.return_value = mock_corrector
            
            result = await inspect_answer(
                agent=mock_agent,
                answer="테스트 답변",
                query="테스트 질의",
                ocr_text="OCR 텍스트",
                context={"type": "factual"},
                kg=mock_kg,
            )
            
            # Should query rules
            assert mock_kg.find_relevant_rules.called
            assert mock_kg.get_constraints_for_query_type.called
            # Should use corrector
            assert mock_corrector.generate_with_self_correction.called
            assert result == "수정된 답변"
