"""Comprehensive tests for src/qa/graph/rule_manager.py."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from src.qa.graph.rule_manager import RuleManager


class TestRuleManager:
    """Test RuleManager class."""

    def test_init(self) -> None:
        """Test RuleManager initialization."""
        mock_session_func = Mock()
        manager = RuleManager(mock_session_func)

        assert manager.graph_session == mock_session_func

    def test_update_rule_success(self) -> None:
        """Test successful rule update."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_single = MagicMock()
        mock_single.get.return_value = 1
        mock_result.single.return_value = mock_single
        mock_session.run.return_value = mock_result

        mock_session_func = MagicMock()
        mock_session_func.return_value.__enter__.return_value = mock_session

        manager = RuleManager(mock_session_func)

        with patch("src.qa.graph.rule_manager.clear_global_rule_cache") as mock_clear:
            manager.update_rule("rule_123", "Updated rule text")

            mock_session.run.assert_called_once()
            mock_clear.assert_called_once()

    def test_update_rule_graph_unavailable(self) -> None:
        """Test update_rule when graph is unavailable."""
        mock_session_func = MagicMock()
        mock_session_func.return_value.__enter__.return_value = None

        manager = RuleManager(mock_session_func)

        with patch("src.qa.graph.rule_manager.clear_global_rule_cache") as mock_clear:
            manager.update_rule("rule_123", "New text")

            # Should not clear cache when graph is unavailable
            mock_clear.assert_not_called()

    def test_update_rule_no_result(self) -> None:
        """Test update_rule when query returns no result."""
        mock_session = MagicMock()
        mock_session.run.return_value = None

        mock_session_func = MagicMock()
        mock_session_func.return_value.__enter__.return_value = mock_session

        manager = RuleManager(mock_session_func)

        with patch("src.qa.graph.rule_manager.clear_global_rule_cache") as mock_clear:
            manager.update_rule("rule_123", "New text")

            mock_clear.assert_called_once()

    def test_add_rule_success(self) -> None:
        """Test successful rule addition."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_single = MagicMock()
        mock_single.get.return_value = "new_rule_id"
        mock_result.single.return_value = mock_single
        mock_session.run.return_value = mock_result

        mock_session_func = MagicMock()
        mock_session_func.return_value.__enter__.return_value = mock_session

        manager = RuleManager(mock_session_func)

        with patch("src.qa.graph.rule_manager.clear_global_rule_cache") as mock_clear:
            result_id = manager.add_rule("explanation", "New rule text")

            assert result_id == "new_rule_id"
            mock_session.run.assert_called_once()
            mock_clear.assert_called_once()

    def test_add_rule_graph_unavailable(self) -> None:
        """Test add_rule when graph is unavailable."""
        mock_session_func = MagicMock()
        mock_session_func.return_value.__enter__.return_value = None

        manager = RuleManager(mock_session_func)

        with patch("src.qa.graph.rule_manager.clear_global_rule_cache") as mock_clear:
            result_id = manager.add_rule("explanation", "New rule")

            # Should return a UUID when graph is unavailable
            assert result_id is not None
            assert len(result_id) > 0
            # Should not clear cache when graph is unavailable
            mock_clear.assert_not_called()

    def test_add_rule_no_result(self) -> None:
        """Test add_rule when query returns no result."""
        mock_session = MagicMock()
        mock_session.run.return_value = None

        mock_session_func = MagicMock()
        mock_session_func.return_value.__enter__.return_value = mock_session

        manager = RuleManager(mock_session_func)

        with patch("src.qa.graph.rule_manager.clear_global_rule_cache") as mock_clear:
            result_id = manager.add_rule("explanation", "New rule")

            assert result_id is not None
            mock_clear.assert_called_once()

    def test_add_rule_result_no_record(self) -> None:
        """Test add_rule when result has no record."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result

        mock_session_func = MagicMock()
        mock_session_func.return_value.__enter__.return_value = mock_session

        manager = RuleManager(mock_session_func)

        with patch("src.qa.graph.rule_manager.clear_global_rule_cache") as mock_clear:
            result_id = manager.add_rule("explanation", "New rule")

            assert result_id is not None
            mock_clear.assert_called_once()

    def test_delete_rule_success(self) -> None:
        """Test successful rule deletion."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_summary = MagicMock()
        mock_summary.counters.nodes_deleted = 1
        mock_result.consume.return_value = mock_summary
        mock_session.run.return_value = mock_result

        mock_session_func = MagicMock()
        mock_session_func.return_value.__enter__.return_value = mock_session

        manager = RuleManager(mock_session_func)

        with patch("src.qa.graph.rule_manager.clear_global_rule_cache") as mock_clear:
            manager.delete_rule("rule_123")

            mock_session.run.assert_called_once()
            mock_clear.assert_called_once()

    def test_delete_rule_graph_unavailable(self) -> None:
        """Test delete_rule when graph is unavailable."""
        mock_session_func = MagicMock()
        mock_session_func.return_value.__enter__.return_value = None

        manager = RuleManager(mock_session_func)

        with patch("src.qa.graph.rule_manager.clear_global_rule_cache") as mock_clear:
            manager.delete_rule("rule_123")

            # Should not clear cache when graph is unavailable
            mock_clear.assert_not_called()

    def test_delete_rule_no_result(self) -> None:
        """Test delete_rule when query returns no result."""
        mock_session = MagicMock()
        mock_session.run.return_value = None

        mock_session_func = MagicMock()
        mock_session_func.return_value.__enter__.return_value = mock_session

        manager = RuleManager(mock_session_func)

        with patch("src.qa.graph.rule_manager.clear_global_rule_cache") as mock_clear:
            manager.delete_rule("rule_123")

            mock_clear.assert_called_once()

    def test_delete_rule_no_summary(self) -> None:
        """Test delete_rule when result has no summary."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.consume.return_value = None
        mock_session.run.return_value = mock_result

        mock_session_func = MagicMock()
        mock_session_func.return_value.__enter__.return_value = mock_session

        manager = RuleManager(mock_session_func)

        with patch("src.qa.graph.rule_manager.clear_global_rule_cache") as mock_clear:
            manager.delete_rule("rule_123")

            mock_clear.assert_called_once()

    def test_delete_rule_summary_no_counters(self) -> None:
        """Test delete_rule when summary counters has no nodes_deleted attribute."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_summary = MagicMock()
        mock_counters = MagicMock(spec=[])  # counters exists but has no nodes_deleted
        mock_summary.counters = mock_counters
        mock_result.consume.return_value = mock_summary
        mock_session.run.return_value = mock_result

        mock_session_func = MagicMock()
        mock_session_func.return_value.__enter__.return_value = mock_session

        manager = RuleManager(mock_session_func)

        with patch("src.qa.graph.rule_manager.clear_global_rule_cache") as mock_clear:
            # Should handle missing nodes_deleted attribute gracefully via getattr default
            manager.delete_rule("rule_123")

            mock_clear.assert_called_once()
