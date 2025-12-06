"""Tests for Neo4j rule upsert manager."""
# mypy: ignore-errors

from unittest.mock import Mock, patch

import pytest

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

    def test_upsert_rule_node_with_graph(self):
        """Test _upsert_rule_node with sync graph driver."""
        mock_session = Mock()
        mock_session.run.return_value = []  # Empty existing

        mock_graph = Mock()
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_session)
        mock_context.__exit__ = Mock(return_value=None)
        mock_graph.session.return_value = mock_context

        manager = RuleUpsertManager(graph=mock_graph)

        result = manager._upsert_rule_node(
            rule_id="rule_001",
            description="Test rule",
            type_hint="explanation",
            batch_id="batch_123",
            timestamp="2024-01-01T00:00:00",
        )

        assert result["created"] is True
        assert mock_session.run.call_count == 2  # check + upsert

    def test_upsert_rule_node_update_existing(self):
        """Test _upsert_rule_node updating existing rule."""
        mock_session = Mock()
        # Simulate existing rule
        mock_session.run.return_value = [{"existing_batch_id": "old_batch"}]

        mock_graph = Mock()
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_session)
        mock_context.__exit__ = Mock(return_value=None)
        mock_graph.session.return_value = mock_context

        manager = RuleUpsertManager(graph=mock_graph)

        result = manager._upsert_rule_node(
            rule_id="rule_001",
            description="Updated rule",
            type_hint="explanation",
            batch_id="batch_123",
            timestamp="2024-01-01T00:00:00",
        )

        assert result["created"] is False

    def test_upsert_rule_node_no_graph_or_provider(self):
        """Test _upsert_rule_node raises error when no graph/provider."""
        manager = RuleUpsertManager()

        with pytest.raises(ValueError, match="Graph driver must be initialized"):
            manager._upsert_rule_node(
                rule_id="rule_001",
                description="Test",
                type_hint="explanation",
                batch_id="batch",
                timestamp="2024-01-01",
            )

    def test_upsert_constraint_node_with_graph(self):
        """Test _upsert_constraint_node with sync graph driver."""
        mock_session = Mock()
        mock_session.run.return_value = []

        mock_graph = Mock()
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_session)
        mock_context.__exit__ = Mock(return_value=None)
        mock_graph.session.return_value = mock_context

        manager = RuleUpsertManager(graph=mock_graph)

        result = manager._upsert_constraint_node(
            constraint_id="const_001",
            description="Test constraint",
            rule_id="rule_001",
            batch_id="batch_123",
            timestamp="2024-01-01T00:00:00",
        )

        assert result["created"] is True

    def test_upsert_constraint_node_no_graph_or_provider(self):
        """Test _upsert_constraint_node raises error when no graph/provider."""
        manager = RuleUpsertManager()

        with pytest.raises(ValueError, match="Graph driver must be initialized"):
            manager._upsert_constraint_node(
                constraint_id="const_001",
                description="Test",
                rule_id="rule_001",
                batch_id="batch",
                timestamp="2024-01-01",
            )

    def test_upsert_best_practice_node_with_graph(self):
        """Test _upsert_best_practice_node with sync graph driver."""
        mock_session = Mock()
        mock_session.run.return_value = []

        mock_graph = Mock()
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_session)
        mock_context.__exit__ = Mock(return_value=None)
        mock_graph.session.return_value = mock_context

        manager = RuleUpsertManager(graph=mock_graph)

        result = manager._upsert_best_practice_node(
            bp_id="bp_001",
            text="Best practice text",
            rule_id="rule_001",
            batch_id="batch_123",
            timestamp="2024-01-01T00:00:00",
        )

        assert result["created"] is True

    def test_upsert_best_practice_node_no_graph_or_provider(self):
        """Test _upsert_best_practice_node raises error when no graph/provider."""
        manager = RuleUpsertManager()

        with pytest.raises(ValueError, match="Graph driver must be initialized"):
            manager._upsert_best_practice_node(
                bp_id="bp_001",
                text="Test",
                rule_id="rule_001",
                batch_id="batch",
                timestamp="2024-01-01",
            )

    def test_upsert_example_node_with_graph(self):
        """Test _upsert_example_node with sync graph driver."""
        mock_session = Mock()
        mock_session.run.return_value = []

        mock_graph = Mock()
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_session)
        mock_context.__exit__ = Mock(return_value=None)
        mock_graph.session.return_value = mock_context

        manager = RuleUpsertManager(graph=mock_graph)

        result = manager._upsert_example_node(
            example_id="ex_001",
            before="Before text",
            after="After text",
            rule_id="rule_001",
            batch_id="batch_123",
            timestamp="2024-01-01T00:00:00",
        )

        assert result["created"] is True

    def test_upsert_example_node_no_graph_or_provider(self):
        """Test _upsert_example_node raises error when no graph/provider."""
        manager = RuleUpsertManager()

        with pytest.raises(ValueError, match="Graph driver must be initialized"):
            manager._upsert_example_node(
                example_id="ex_001",
                before="Before",
                after="After",
                rule_id="rule_001",
                batch_id="batch",
                timestamp="2024-01-01",
            )

    def test_get_rules_by_batch_id_with_graph(self):
        """Test get_rules_by_batch_id with sync graph driver."""
        mock_session = Mock()
        mock_record1 = {
            "labels": ["Rule"],
            "id": "rule_001",
            "created_at": "2024-01-01",
        }
        mock_record2 = {
            "labels": ["Constraint"],
            "id": "const_001",
            "created_at": "2024-01-01",
        }
        mock_session.run.return_value = [mock_record1, mock_record2]

        mock_graph = Mock()
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_session)
        mock_context.__exit__ = Mock(return_value=None)
        mock_graph.session.return_value = mock_context

        manager = RuleUpsertManager(graph=mock_graph)

        result = manager.get_rules_by_batch_id("batch_123")

        assert len(result) == 2
        assert result[0]["id"] == "rule_001"

    def test_get_rules_by_batch_id_no_graph_or_provider(self):
        """Test get_rules_by_batch_id raises error when no graph/provider."""
        manager = RuleUpsertManager()

        with pytest.raises(ValueError, match="Graph driver must be initialized"):
            manager.get_rules_by_batch_id("batch_123")

    def test_rollback_batch_with_graph(self):
        """Test rollback_batch with sync graph driver."""
        mock_session = Mock()
        mock_session.run.side_effect = [
            [{"cnt": 5}],  # count query
            None,  # delete query
        ]

        mock_graph = Mock()
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_session)
        mock_context.__exit__ = Mock(return_value=None)
        mock_graph.session.return_value = mock_context

        manager = RuleUpsertManager(graph=mock_graph)

        result = manager.rollback_batch("batch_123")

        assert result["success"] is True
        assert result["deleted_count"] == 5

    def test_rollback_batch_no_nodes(self):
        """Test rollback_batch when no nodes exist."""
        mock_session = Mock()
        mock_session.run.side_effect = [
            [],  # empty count result
            None,
        ]

        mock_graph = Mock()
        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_session)
        mock_context.__exit__ = Mock(return_value=None)
        mock_graph.session.return_value = mock_context

        manager = RuleUpsertManager(graph=mock_graph)

        result = manager.rollback_batch("batch_123")

        assert result["success"] is True
        assert result["deleted_count"] == 0

    def test_rollback_batch_no_graph_or_provider(self):
        """Test rollback_batch raises error when no graph/provider."""
        manager = RuleUpsertManager()

        with pytest.raises(ValueError, match="Graph driver must be initialized"):
            manager.rollback_batch("batch_123")

    def test_upsert_auto_generated_rules_with_all_fields(self):
        """Test upsert with all optional fields present."""
        mock_graph = Mock()
        mock_session = Mock()
        mock_session.run.return_value = []

        mock_context = Mock()
        mock_context.__enter__ = Mock(return_value=mock_session)
        mock_context.__exit__ = Mock(return_value=None)
        mock_graph.session.return_value = mock_context

        manager = RuleUpsertManager(graph=mock_graph)

        patterns = [
            {
                "id": "rule_001",
                "rule": "Test rule",
                "type_hint": "explanation",
                "constraint": "Must be concise",
                "best_practice": "Use clear language",
                "example_before": "Bad example",
                "example_after": "Good example",
            }
        ]

        result = manager.upsert_auto_generated_rules(patterns, batch_id="test")

        assert result["success"] is True
        assert result["created"]["rules"] == 1
        assert result["created"]["constraints"] == 1
        assert result["created"]["best_practices"] == 1
        assert result["created"]["examples"] == 1

    def test_upsert_auto_generated_rules_updates_existing(self):
        """Test that existing nodes are updated, not created."""
        mock_graph = Mock()
        manager = RuleUpsertManager(graph=mock_graph)

        # Mock all upsert methods to return updated (created: False)
        with (
            patch.object(manager, "_upsert_rule_node") as mock_rule,
            patch.object(manager, "_upsert_constraint_node") as mock_constraint,
            patch.object(manager, "_upsert_best_practice_node") as mock_bp,
            patch.object(manager, "_upsert_example_node") as mock_example,
        ):
            mock_rule.return_value = {"created": False}  # Updated, not created
            mock_constraint.return_value = {"created": False}
            mock_bp.return_value = {"created": False}
            mock_example.return_value = {"created": False}

            patterns = [
                {
                    "id": "rule_001",
                    "rule": "Updated rule",
                    "type_hint": "explanation",
                    "constraint": "Updated constraint",
                    "best_practice": "Updated best practice",
                    "example_before": "Updated before",
                    "example_after": "Updated after",
                }
            ]

            result = manager.upsert_auto_generated_rules(patterns, batch_id="test")

            assert result["success"] is True
            # Should count as updates, not creates
            assert result["updated"]["rules"] == 1
            assert result["updated"]["constraints"] == 1
            assert result["updated"]["best_practices"] == 1
            assert result["updated"]["examples"] == 1
            # Creates should be 0
            assert result["created"]["rules"] == 0
            assert result["created"]["constraints"] == 0
            assert result["created"]["best_practices"] == 0
            assert result["created"]["examples"] == 0
