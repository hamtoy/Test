"""Tests for the hybrid optimizer module."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.workflow.hybrid_optimizer import HybridWorkflowOptimizer


class TestHybridWorkflowOptimizer:
    """Tests for HybridWorkflowOptimizer class."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock GeminiAgent."""
        agent = MagicMock()
        agent.llm_provider = MagicMock()
        agent.generate_query = AsyncMock(return_value="mocked response")
        return agent

    @pytest.fixture
    def optimizer(self, mock_agent):
        """Create an optimizer instance with mocked dependencies."""
        templates = ["template_a", "template_b"]
        with (
            patch("src.workflow.hybrid_optimizer.LATSSearcher") as MockLATS,
            patch("src.workflow.hybrid_optimizer.MCTSWorkflowOptimizer") as MockMCTS,
        ):
            # Setup mock LATS
            mock_lats_instance = MagicMock()
            mock_lats_instance.run = AsyncMock(return_value=MagicMock())
            MockLATS.return_value = mock_lats_instance

            # Setup mock MCTS
            mock_mcts_instance = MagicMock()
            mock_mcts_instance.optimize_workflow = AsyncMock(
                return_value={"best_template": "template_a", "score": 0.8}
            )
            MockMCTS.return_value = mock_mcts_instance

            opt = HybridWorkflowOptimizer(mock_agent, templates)
            opt.lats = mock_lats_instance
            opt.mcts = mock_mcts_instance
            return opt

    def test_detect_complexity_lats_keywords(self, optimizer):
        """Test complexity detection with LATS-triggering keywords."""
        # Keywords that should trigger LATS
        assert optimizer._detect_complexity("Why does this happen?") == "lats"
        assert optimizer._detect_complexity("Explain the concept") == "lats"
        assert optimizer._detect_complexity("Give me a reason for this") == "lats"
        assert optimizer._detect_complexity("Compare these two options") == "lats"
        assert optimizer._detect_complexity("Analyze the data") == "lats"
        assert optimizer._detect_complexity("What is the relationship?") == "lats"

    def test_detect_complexity_long_query(self, optimizer):
        """Test complexity detection with long queries."""
        # Create a query with more than 50 words
        long_query = " ".join(["word"] * 51)
        assert optimizer._detect_complexity(long_query) == "lats"

    def test_detect_complexity_short_simple_query(self, optimizer):
        """Test complexity detection with short simple queries."""
        assert optimizer._detect_complexity("What is the price?") == "mcts"
        assert optimizer._detect_complexity("List the items") == "mcts"
        assert optimizer._detect_complexity("Show me the result") == "mcts"

    @pytest.mark.asyncio
    async def test_optimize_mcts_mode(self, optimizer):
        """Test optimization with explicit MCTS mode."""
        result = await optimizer.optimize("simple query", mode="mcts")

        assert result["optimizer"] == "MCTS"
        assert "best_template" in result
        assert "score" in result
        assert result["strategy"] == "Template Selection"
        optimizer.mcts.optimize_workflow.assert_called_once_with("simple query")

    @pytest.mark.asyncio
    async def test_optimize_lats_mode(self, optimizer):
        """Test optimization with explicit LATS mode."""
        result = await optimizer.optimize("complex query", mode="lats")

        assert result["optimizer"] == "LATS"
        assert "result" in result
        assert result["strategy"] == "Reasoning Tree"
        optimizer.lats.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_optimize_auto_mode_simple(self, optimizer):
        """Test auto mode routes simple queries to MCTS."""
        result = await optimizer.optimize("What is X?", mode="auto")

        # Simple query should route to MCTS
        assert result["optimizer"] == "MCTS"

    @pytest.mark.asyncio
    async def test_optimize_auto_mode_complex(self, optimizer):
        """Test auto mode routes complex queries to LATS."""
        result = await optimizer.optimize("Explain why this happens", mode="auto")

        # Complex query with "explain" and "why" should route to LATS
        assert result["optimizer"] == "LATS"

    @pytest.mark.asyncio
    async def test_optimize_auto_mode_long_query(self, optimizer):
        """Test auto mode routes long queries to LATS."""
        long_query = " ".join(["word"] * 51)
        result = await optimizer.optimize(long_query, mode="auto")

        assert result["optimizer"] == "LATS"


class TestHybridOptimizerDetectComplexity:
    """Additional tests for complexity detection edge cases."""

    @pytest.fixture
    def optimizer(self):
        """Create optimizer with mocked dependencies for complexity tests."""
        mock_agent = MagicMock()
        mock_agent.llm_provider = MagicMock()

        with (
            patch("src.workflow.hybrid_optimizer.LATSSearcher"),
            patch("src.workflow.hybrid_optimizer.MCTSWorkflowOptimizer"),
        ):
            return HybridWorkflowOptimizer(mock_agent, ["t1", "t2"])

    def test_case_insensitive_keywords(self, optimizer):
        """Test that keyword detection is case insensitive."""
        assert optimizer._detect_complexity("WHY IS THIS?") == "lats"
        assert optimizer._detect_complexity("EXPLAIN please") == "lats"
        assert optimizer._detect_complexity("Compare THESE") == "lats"

    def test_keyword_in_middle_of_query(self, optimizer):
        """Test keywords detected in middle of query."""
        assert optimizer._detect_complexity("I want to analyze data") == "lats"
        assert optimizer._detect_complexity("Please explain this to me") == "lats"

    def test_exactly_50_words(self, optimizer):
        """Test query with exactly 50 words goes to MCTS."""
        query_50_words = " ".join(["word"] * 50)
        assert optimizer._detect_complexity(query_50_words) == "mcts"

    def test_empty_query(self, optimizer):
        """Test empty query defaults to MCTS."""
        assert optimizer._detect_complexity("") == "mcts"
