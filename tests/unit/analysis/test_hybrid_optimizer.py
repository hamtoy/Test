"""Tests for the hybrid workflow optimizer module."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.workflow.hybrid_optimizer import HybridWorkflowOptimizer


class TestHybridWorkflowOptimizer:
    """Tests for HybridWorkflowOptimizer."""

    @pytest.fixture
    def mock_agent(self) -> Any:
        """Create a mock GeminiAgent."""
        agent = MagicMock()
        agent.llm_provider = MagicMock()
        return agent

    @pytest.fixture
    def templates(self) -> Any:
        """Sample templates for testing."""
        return ["template_a", "template_b", "template_c"]

    @pytest.fixture
    def optimizer(self, mock_agent: Any, templates: Any) -> Any:
        """Create an optimizer instance with mocked dependencies."""
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
            # Store mocks for verification
            opt._mock_lats = mock_lats_instance  # type: ignore[attr-defined]
            opt._mock_mcts = mock_mcts_instance  # type: ignore[attr-defined]
            return opt

    def test_detect_complexity_lats_keywords(self, optimizer: Any) -> None:
        """Test complexity detection for LATS keywords."""
        # Test 'why' keyword
        assert optimizer._detect_complexity("Why does this happen?") == "lats"

        # Test 'explain' keyword
        assert optimizer._detect_complexity("Explain the process") == "lats"

        # Test 'reason' keyword
        assert optimizer._detect_complexity("What is the reason?") == "lats"

        # Test 'compare' keyword
        assert optimizer._detect_complexity("Compare A and B") == "lats"

        # Test 'analyze' keyword
        assert optimizer._detect_complexity("Analyze this data") == "lats"

        # Test 'relationship' keyword
        assert optimizer._detect_complexity("What is the relationship?") == "lats"

    def test_detect_complexity_case_insensitive(self, optimizer: Any) -> None:
        """Test complexity detection is case insensitive."""
        assert optimizer._detect_complexity("WHY does this happen?") == "lats"
        assert optimizer._detect_complexity("EXPLAIN the process") == "lats"

    def test_detect_complexity_mcts_short(self, optimizer: Any) -> None:
        """Test complexity detection returns mcts for short queries."""
        assert optimizer._detect_complexity("What is X?") == "mcts"
        assert optimizer._detect_complexity("List items") == "mcts"

    def test_detect_complexity_long_query(self, optimizer: Any) -> None:
        """Test complexity detection for long queries."""
        # Create a query with more than 50 words
        words = ["word"] * 55
        long_query = " ".join(words)
        assert optimizer._detect_complexity(long_query) == "lats"

    def test_detect_complexity_default_mcts(self, optimizer: Any) -> None:
        """Test complexity detection defaults to mcts."""
        assert optimizer._detect_complexity("Simple query here") == "mcts"

    @pytest.mark.asyncio
    async def test_optimize_lats_mode(self, optimizer: Any) -> None:
        """Test optimization with explicit LATS mode."""
        result = await optimizer.optimize("Test query", mode="lats")

        assert result["optimizer"] == "LATS"
        assert result["strategy"] == "Reasoning Tree"
        assert "result" in result
        optimizer._mock_lats.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_optimize_lats_with_state_injection(self, optimizer: Any) -> None:
        """Test LATS optimization injects query, ocr_text, current_answer into initial state."""
        result = await optimizer.optimize(
            "Test query",
            mode="lats",
            ocr_text="OCR 텍스트 내용",
            current_answer="현재 답변",
        )

        assert result["optimizer"] == "LATS"
        # Verify run was called with initial_state containing the injected values
        call_args = optimizer._mock_lats.run.call_args
        assert call_args is not None
        # The initial_state is passed as a keyword argument
        initial_state = call_args.kwargs.get("initial_state")
        assert initial_state is not None
        assert initial_state.query == "Test query"
        assert initial_state.ocr_text == "OCR 텍스트 내용"
        assert initial_state.current_answer == "현재 답변"

    def test_detect_complexity_short_simple_query(self, optimizer: Any) -> None:
        """Test complexity detection with short simple queries."""
        assert optimizer._detect_complexity("What is the price?") == "mcts"
        assert optimizer._detect_complexity("List the items") == "mcts"
        assert optimizer._detect_complexity("Show me the result") == "mcts"

    @pytest.mark.asyncio
    async def test_optimize_mcts_mode(self, optimizer: Any) -> None:
        """Test optimization with explicit MCTS mode."""
        result = await optimizer.optimize("Test query", mode="mcts")

        assert result["optimizer"] == "MCTS"
        assert result["strategy"] == "Template Selection"
        assert result["best_template"] == "template_a"
        assert result["score"] == 0.8
        optimizer._mock_mcts.optimize_workflow.assert_called_once_with("Test query")

    @pytest.mark.asyncio
    async def test_optimize_auto_mode_selects_lats(self, optimizer: Any) -> None:
        """Test auto mode selects LATS for complex queries."""
        result = await optimizer.optimize("Why does this happen?", mode="auto")

        assert result["optimizer"] == "LATS"
        optimizer._mock_lats.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_optimize_auto_mode_selects_mcts(self, optimizer: Any) -> None:
        """Test auto mode selects MCTS for simple queries."""
        result = await optimizer.optimize("What is X?", mode="auto")

        assert result["optimizer"] == "MCTS"
        optimizer._mock_mcts.optimize_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_optimize_auto_default_fallback(
        self, mock_agent: Any, templates: Any
    ) -> None:
        """Test auto mode defaults to mcts when detection returns unknown."""
        with (
            patch("src.workflow.hybrid_optimizer.LATSSearcher") as mock_lats,
            patch("src.workflow.hybrid_optimizer.MCTSWorkflowOptimizer") as mock_mcts,
        ):
            mock_lats_instance = MagicMock()
            mock_lats_instance.run = AsyncMock(return_value={})
            mock_lats.return_value = mock_lats_instance

            mock_mcts_instance = MagicMock()
            mock_mcts_instance.optimize_workflow = AsyncMock(
                return_value={"best_template": "t", "score": 0.5}
            )
            mock_mcts.return_value = mock_mcts_instance

            opt = HybridWorkflowOptimizer(mock_agent, templates)

            # Patch _detect_complexity to return something other than lats/mcts
            with patch.object(opt, "_detect_complexity", return_value="unknown"):
                result = await opt.optimize("query", mode="auto")
                assert result["optimizer"] == "MCTS"


class TestHybridWorkflowOptimizerInit:
    """Tests for HybridWorkflowOptimizer initialization."""

    def test_init_creates_lats(self) -> None:
        """Test that initialization creates LATS searcher."""
        mock_agent = MagicMock()
        mock_agent.llm_provider = MagicMock()

        with (
            patch("src.workflow.hybrid_optimizer.LATSSearcher") as mock_lats,
            patch("src.workflow.hybrid_optimizer.MCTSWorkflowOptimizer"),
        ):
            HybridWorkflowOptimizer(mock_agent, ["template"])

            mock_lats.assert_called_once_with(llm_provider=mock_agent.llm_provider)

    def test_init_creates_mcts(self) -> None:
        """Test that initialization creates MCTS optimizer."""
        mock_agent = MagicMock()
        mock_agent.llm_provider = MagicMock()
        templates = ["template_a", "template_b"]

        with (
            patch("src.workflow.hybrid_optimizer.LATSSearcher"),
            patch("src.workflow.hybrid_optimizer.MCTSWorkflowOptimizer") as mock_mcts,
        ):
            HybridWorkflowOptimizer(mock_agent, templates)

            mock_mcts.assert_called_once_with(mock_agent, templates)


class TestHybridOptimizerDetectComplexity:
    """Additional tests for complexity detection edge cases."""

    @pytest.fixture
    def optimizer(self) -> Any:
        """Create optimizer with mocked dependencies for complexity tests."""
        mock_agent = MagicMock()
        mock_agent.llm_provider = MagicMock()

        with (
            patch("src.workflow.hybrid_optimizer.LATSSearcher"),
            patch("src.workflow.hybrid_optimizer.MCTSWorkflowOptimizer"),
        ):
            return HybridWorkflowOptimizer(mock_agent, ["t1", "t2"])

    def test_case_insensitive_keywords(self, optimizer: Any) -> None:
        """Test that keyword detection is case insensitive."""
        assert optimizer._detect_complexity("WHY IS THIS?") == "lats"
        assert optimizer._detect_complexity("EXPLAIN please") == "lats"
        assert optimizer._detect_complexity("Compare THESE") == "lats"

    def test_keyword_in_middle_of_query(self, optimizer: Any) -> None:
        """Test keywords detected in middle of query."""
        assert optimizer._detect_complexity("I want to analyze data") == "lats"
        assert optimizer._detect_complexity("Please explain this to me") == "lats"

    def test_exactly_50_words(self, optimizer: Any) -> None:
        """Test query with exactly 50 words goes to MCTS."""
        query_50_words = " ".join(["word"] * 50)
        assert optimizer._detect_complexity(query_50_words) == "mcts"

    def test_empty_query(self, optimizer: Any) -> None:
        """Test empty query defaults to MCTS."""
        assert optimizer._detect_complexity("") == "mcts"
