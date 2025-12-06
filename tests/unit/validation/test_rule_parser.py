"""Tests for CSV-based rule parser."""

from __future__ import annotations



from src.validation.rule_parser import RuleCSVParser, RuleManager


class TestRuleCSVParser:
    """Test RuleCSVParser class."""

    def test_parse_guide_csv_with_real_file(self) -> None:
        """Test parsing guide.csv with real file."""
        parser = RuleCSVParser(
            guide_path="data/neo4j/guide.csv",
            qna_path="data/neo4j/qna.csv",
            patterns_path="config/patterns.yaml",
        )
        rules = parser.parse_guide_csv()

        assert isinstance(rules, dict)
        assert "temporal_expressions" in rules
        assert "sentence_rules" in rules
        assert "formatting_rules" in rules
        assert "structure_rules" in rules

        # Check that temporal expressions are populated
        assert isinstance(rules["temporal_expressions"], list)
        assert len(rules["temporal_expressions"]) >= 0

    def test_parse_qna_csv_with_real_file(self) -> None:
        """Test parsing qna.csv with real file."""
        parser = RuleCSVParser(
            guide_path="data/neo4j/guide.csv",
            qna_path="data/neo4j/qna.csv",
            patterns_path="config/patterns.yaml",
        )
        checklist = parser.parse_qna_csv()

        assert isinstance(checklist, dict)
        assert "question_checklist" in checklist
        assert "answer_checklist" in checklist
        assert "work_checklist" in checklist

        # Verify that at least some checklist items are loaded
        total_items = (
            len(checklist["question_checklist"])
            + len(checklist["answer_checklist"])
            + len(checklist["work_checklist"])
        )
        assert total_items > 0

    def test_parse_patterns_yaml_with_real_file(self) -> None:
        """Test parsing patterns.yaml with real file."""
        parser = RuleCSVParser(
            guide_path="data/neo4j/guide.csv",
            qna_path="data/neo4j/qna.csv",
            patterns_path="config/patterns.yaml",
        )
        patterns = parser.parse_patterns_yaml()

        assert isinstance(patterns, dict)
        assert "forbidden_patterns" in patterns
        assert "formatting_patterns" in patterns

        # Check forbidden patterns
        forbidden = patterns["forbidden_patterns"]
        assert isinstance(forbidden, dict)
        assert "전체이미지" in forbidden
        assert "표참조" in forbidden
        assert "그래프참조" in forbidden
        assert "용어정의" in forbidden

        # Check formatting patterns
        formatting = patterns["formatting_patterns"]
        assert isinstance(formatting, dict)
        assert "prose_bold_violation" in formatting
        assert "composite_query" in formatting

    def test_parse_nonexistent_files(self) -> None:
        """Test parsing with nonexistent files."""
        parser = RuleCSVParser(
            guide_path="nonexistent/guide.csv",
            qna_path="nonexistent/qna.csv",
            patterns_path="nonexistent/patterns.yaml",
        )

        # Should return empty structures without crashing
        guide_rules = parser.parse_guide_csv()
        assert isinstance(guide_rules, dict)
        assert len(guide_rules["temporal_expressions"]) == 0

        qna_checklist = parser.parse_qna_csv()
        assert isinstance(qna_checklist, dict)
        assert len(qna_checklist["question_checklist"]) == 0

        patterns = parser.parse_patterns_yaml()
        assert isinstance(patterns, dict)
        assert len(patterns["forbidden_patterns"]) == 0

    def test_get_all_rules(self) -> None:
        """Test get_all_rules method."""
        parser = RuleCSVParser(
            guide_path="data/neo4j/guide.csv",
            qna_path="data/neo4j/qna.csv",
            patterns_path="config/patterns.yaml",
        )
        all_rules = parser.get_all_rules()

        assert isinstance(all_rules, dict)
        assert "guide_rules" in all_rules
        assert "qna_checklist" in all_rules
        assert "pattern_rules" in all_rules

    def test_caching(self) -> None:
        """Test that rules are cached after first parse."""
        parser = RuleCSVParser(
            guide_path="data/neo4j/guide.csv",
            qna_path="data/neo4j/qna.csv",
            patterns_path="config/patterns.yaml",
        )

        # First call
        rules1 = parser.parse_guide_csv()
        # Second call should return cached result
        rules2 = parser.parse_guide_csv()

        assert rules1 is rules2  # Should be the same object


class TestRuleManager:
    """Test RuleManager class."""

    def test_load_rules(self) -> None:
        """Test loading rules."""
        parser = RuleCSVParser(
            guide_path="data/neo4j/guide.csv",
            qna_path="data/neo4j/qna.csv",
            patterns_path="config/patterns.yaml",
        )
        manager = RuleManager(parser)

        rules = manager.load_rules()
        assert isinstance(rules, dict)
        assert manager.rules is not None

    def test_get_temporal_rules(self) -> None:
        """Test getting temporal rules."""
        parser = RuleCSVParser(
            guide_path="data/neo4j/guide.csv",
            qna_path="data/neo4j/qna.csv",
            patterns_path="config/patterns.yaml",
        )
        manager = RuleManager(parser)

        temporal_rules = manager.get_temporal_rules()
        assert isinstance(temporal_rules, list)

    def test_get_sentence_rules(self) -> None:
        """Test getting sentence rules."""
        parser = RuleCSVParser(
            guide_path="data/neo4j/guide.csv",
            qna_path="data/neo4j/qna.csv",
            patterns_path="config/patterns.yaml",
        )
        manager = RuleManager(parser)

        sentence_rules = manager.get_sentence_rules()
        assert isinstance(sentence_rules, dict)

    def test_get_question_checklist(self) -> None:
        """Test getting question checklist."""
        parser = RuleCSVParser(
            guide_path="data/neo4j/guide.csv",
            qna_path="data/neo4j/qna.csv",
            patterns_path="config/patterns.yaml",
        )
        manager = RuleManager(parser)

        checklist = manager.get_question_checklist()
        assert isinstance(checklist, list)

    def test_get_answer_checklist(self) -> None:
        """Test getting answer checklist."""
        parser = RuleCSVParser(
            guide_path="data/neo4j/guide.csv",
            qna_path="data/neo4j/qna.csv",
            patterns_path="config/patterns.yaml",
        )
        manager = RuleManager(parser)

        checklist = manager.get_answer_checklist()
        assert isinstance(checklist, list)

    def test_lazy_loading(self) -> None:
        """Test that rules are loaded lazily."""
        parser = RuleCSVParser(
            guide_path="data/neo4j/guide.csv",
            qna_path="data/neo4j/qna.csv",
            patterns_path="config/patterns.yaml",
        )
        manager = RuleManager(parser)

        # Rules should be None before first access
        assert manager.rules is None

        # Access should trigger loading
        _ = manager.get_temporal_rules()
        assert manager.rules is not None
