"""Tests for Neo4j rule upsert manager."""
# mypy: ignore-errors

from unittest.mock import Mock, patch


from src.qa.graph.rule_upsert import RuleUpsertManager


class TestRuleUpsertManager:
    """Tests for RuleUpsertManager."""

    def test_init_with_graph(self):
        """Test initialization with graph driver."""
        mock_graph = Mock()
        manager = RuleUpsertManager(graph=mock_graph)

        assert manager._graph == mock_graph
        assert manager._graph_provider is None

    def test_init_with_graph_provider(self):
        """Test initialization with graph provider."""
        mock_provider = Mock()
        manager = RuleUpsertManager(graph_provider=mock_provider)

        assert manager._graph is None
        assert manager._graph_provider == mock_provider

    def test_init_with_both(self):
        """Test initialization with both graph and provider."""
        mock_graph = Mock()
        mock_provider = Mock()
        manager = RuleUpsertManager(graph=mock_graph, graph_provider=mock_provider)

        assert manager._graph == mock_graph
        assert manager._graph_provider == mock_provider

    @patch.object(RuleUpsertManager, "_upsert_rule_node")
    def test_upsert_auto_generated_rules_success(self, mock_upsert_rule):
        """Test successful upsert of auto-generated rules."""
        mock_graph = Mock()
        manager = RuleUpsertManager(graph=mock_graph)

        mock_upsert_rule.return_value = {"created": 1, "updated": 0}

        patterns = [
            {
                "id": "rule_001",
                "rule": "Always validate input",
                "type_hint": "explanation",
            }
        ]

        result = manager.upsert_auto_generated_rules(patterns, batch_id="test_batch")

        assert result["success"] is True
        assert result["batch_id"] == "test_batch"
        assert "created" in result
        assert "updated" in result
        assert result["errors"] == []

    @patch.object(RuleUpsertManager, "_upsert_rule_node")
    def test_upsert_auto_generated_rules_auto_batch_id(self, mock_upsert_rule):
        """Test auto-generation of batch_id."""
        mock_graph = Mock()
        manager = RuleUpsertManager(graph=mock_graph)

        mock_upsert_rule.return_value = {"created": 1, "updated": 0}

        patterns = [
            {
                "id": "rule_001",
                "rule": "Test rule",
                "type_hint": "explanation",
            }
        ]

        result = manager.upsert_auto_generated_rules(patterns)

        assert result["success"] is True
        assert result["batch_id"].startswith("batch_")
        assert "_" in result["batch_id"]

    def test_upsert_auto_generated_rules_missing_id(self):
        """Test handling of patterns missing id field."""
        mock_graph = Mock()
        manager = RuleUpsertManager(graph=mock_graph)

        patterns = [
            {
                "rule": "Test rule without id",
                "type_hint": "explanation",
            }
        ]

        result = manager.upsert_auto_generated_rules(patterns, batch_id="test")

        assert result["success"] is True
        assert len(result["errors"]) == 1
        assert "id/rule" in result["errors"][0]

    def test_upsert_auto_generated_rules_missing_rule(self):
        """Test handling of patterns missing rule field."""
        mock_graph = Mock()
        manager = RuleUpsertManager(graph=mock_graph)

        patterns = [
            {
                "id": "rule_001",
                "type_hint": "explanation",
            }
        ]

        result = manager.upsert_auto_generated_rules(patterns, batch_id="test")

        assert result["success"] is True
        assert len(result["errors"]) == 1
        assert "id/rule" in result["errors"][0]

    @patch.object(RuleUpsertManager, "_upsert_rule_node")
    def test_upsert_auto_generated_rules_empty_list(self, mock_upsert_rule):
        """Test upsert with empty patterns list."""
        mock_graph = Mock()
        manager = RuleUpsertManager(graph=mock_graph)

        result = manager.upsert_auto_generated_rules([], batch_id="test")

        assert result["success"] is True
        assert result["batch_id"] == "test"
        assert result["errors"] == []
        mock_upsert_rule.assert_not_called()

    @patch.object(RuleUpsertManager, "_upsert_rule_node")
    @patch.object(RuleUpsertManager, "_upsert_constraint_node")
    def test_upsert_with_constraints(self, mock_upsert_constraint, mock_upsert_rule):
        """Test upsert of patterns with constraints."""
        mock_graph = Mock()
        manager = RuleUpsertManager(graph=mock_graph)

        mock_upsert_rule.return_value = {"created": 1, "updated": 0}
        mock_upsert_constraint.return_value = {"created": 1, "updated": 0}

        patterns = [
            {
                "id": "rule_001",
                "rule": "Test rule",
                "type_hint": "explanation",
                "constraint": "Must be under 100 words",
            }
        ]

        result = manager.upsert_auto_generated_rules(patterns, batch_id="test")

        assert result["success"] is True
        mock_upsert_rule.assert_called_once()
        mock_upsert_constraint.assert_called_once()

    @patch.object(RuleUpsertManager, "_upsert_rule_node")
    @patch.object(RuleUpsertManager, "_upsert_best_practice_node")
    def test_upsert_with_best_practices(self, mock_upsert_bp, mock_upsert_rule):
        """Test upsert of patterns with best practices."""
        mock_graph = Mock()
        manager = RuleUpsertManager(graph=mock_graph)

        mock_upsert_rule.return_value = {"created": 1, "updated": 0}
        mock_upsert_bp.return_value = {"created": 1, "updated": 0}

        patterns = [
            {
                "id": "rule_001",
                "rule": "Test rule",
                "type_hint": "explanation",
                "best_practice": "Use clear language",
            }
        ]

        result = manager.upsert_auto_generated_rules(patterns, batch_id="test")

        assert result["success"] is True
        mock_upsert_rule.assert_called_once()
        mock_upsert_bp.assert_called_once()

    @patch.object(RuleUpsertManager, "_upsert_rule_node")
    @patch.object(RuleUpsertManager, "_upsert_example_node")
    def test_upsert_with_examples(self, mock_upsert_example, mock_upsert_rule):
        """Test upsert of patterns with examples."""
        mock_graph = Mock()
        manager = RuleUpsertManager(graph=mock_graph)

        mock_upsert_rule.return_value = {"created": 1, "updated": 0}
        mock_upsert_example.return_value = {"created": 1, "updated": 0}

        patterns = [
            {
                "id": "rule_001",
                "rule": "Test rule",
                "type_hint": "explanation",
                "example_before": "Bad example",
                "example_after": "Good example",
            }
        ]

        result = manager.upsert_auto_generated_rules(patterns, batch_id="test")

        assert result["success"] is True
        mock_upsert_rule.assert_called_once()
        mock_upsert_example.assert_called_once()

    @patch.object(RuleUpsertManager, "_upsert_rule_node")
    def test_upsert_multiple_patterns(self, mock_upsert_rule):
        """Test upsert of multiple patterns."""
        mock_graph = Mock()
        manager = RuleUpsertManager(graph=mock_graph)

        mock_upsert_rule.return_value = {"created": 1, "updated": 0}

        patterns = [
            {
                "id": "rule_001",
                "rule": "Rule 1",
                "type_hint": "explanation",
            },
            {
                "id": "rule_002",
                "rule": "Rule 2",
                "type_hint": "summary",
            },
            {
                "id": "rule_003",
                "rule": "Rule 3",
                "type_hint": "reasoning",
            },
        ]

        result = manager.upsert_auto_generated_rules(patterns, batch_id="test")

        assert result["success"] is True
        assert mock_upsert_rule.call_count == 3

    @patch.object(RuleUpsertManager, "_upsert_rule_node")
    def test_upsert_handles_exceptions(self, mock_upsert_rule):
        """Test that exceptions during upsert are caught and logged."""
        mock_graph = Mock()
        manager = RuleUpsertManager(graph=mock_graph)

        mock_upsert_rule.side_effect = Exception("Database error")

        patterns = [
            {
                "id": "rule_001",
                "rule": "Test rule",
                "type_hint": "explanation",
            }
        ]

        result = manager.upsert_auto_generated_rules(patterns, batch_id="test")

        # Should return success=False when exception occurs
        assert result["success"] is False
        assert len(result["errors"]) > 0
        assert "Database error" in result["errors"][0]

    def test_upsert_auto_generated_rules_without_type_hint(self):
        """Test upsert of pattern without type_hint."""
        mock_graph = Mock()
        manager = RuleUpsertManager(graph=mock_graph)

        with patch.object(manager, "_upsert_rule_node") as mock_upsert:
            mock_upsert.return_value = {"created": 1, "updated": 0}

            patterns = [
                {
                    "id": "rule_001",
                    "rule": "Test rule",
                    # No type_hint provided
                }
            ]

            result = manager.upsert_auto_generated_rules(patterns, batch_id="test")

            assert result["success"] is True
            # Should call with empty string for type_hint
            call_args = mock_upsert.call_args
            assert call_args[1]["type_hint"] == ""
