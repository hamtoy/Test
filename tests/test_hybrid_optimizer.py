"""Tests for the hybrid workflow optimizer module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.workflow.hybrid_optimizer import HybridWorkflowOptimizer


class TestHybridWorkflowOptimizer:
    """Tests for HybridWorkflowOptimizer."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock GeminiAgent."""
        agent = MagicMock()
        agent.llm_provider = MagicMock()
        return agent

    @pytest.fixture
    def templates(self):
        """Sample templates for testing."""
        return ["template_a", "template_b", "template_c"]

    @pytest.fixture
    def optimizer(self, mock_agent, templates):
        """Create an optimizer instance."""
        with patch("src.workflow.hybrid_optimizer.LATSSearcher") as mock_lats, \
             patch("src.workflow.hybrid_optimizer.MCTSWorkflowOptimizer") as mock_mcts:
            # Configure mocks
            mock_lats_instance = MagicMock()
            mock_lats_instance.run = AsyncMock(return_value={"result": "lats_result"})
            mock_lats.return_value = mock_lats_instance
            
            mock_mcts_instance = MagicMock()
            mock_mcts_instance.optimize_workflow = AsyncMock(
                return_value={"best_template": "template_a", "score": 0.8}
            )
            mock_mcts.return_value = mock_mcts_instance
            
            opt = HybridWorkflowOptimizer(mock_agent, templates)
            # Store mocks for verification
            opt._mock_lats = mock_lats_instance
            opt._mock_mcts = mock_mcts_instance
            return opt

    def test_detect_complexity_lats_keywords(self, optimizer):
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

    def test_detect_complexity_case_insensitive(self, optimizer):
        """Test complexity detection is case insensitive."""
        assert optimizer._detect_complexity("WHY does this happen?") == "lats"
        assert optimizer._detect_complexity("EXPLAIN the process") == "lats"

    def test_detect_complexity_mcts_short(self, optimizer):
        """Test complexity detection returns mcts for short queries."""
        assert optimizer._detect_complexity("What is X?") == "mcts"
        assert optimizer._detect_complexity("List items") == "mcts"

    def test_detect_complexity_long_query(self, optimizer):
        """Test complexity detection for long queries."""
        # Create a query with more than 50 words
        words = ["word"] * 55
        long_query = " ".join(words)
        assert optimizer._detect_complexity(long_query) == "lats"

    def test_detect_complexity_default_mcts(self, optimizer):
        """Test complexity detection defaults to mcts."""
        assert optimizer._detect_complexity("Simple query here") == "mcts"

    @pytest.mark.asyncio
    async def test_optimize_lats_mode(self, optimizer):
        """Test optimization with explicit LATS mode."""
        result = await optimizer.optimize("Test query", mode="lats")
        
        assert result["optimizer"] == "LATS"
        assert result["strategy"] == "Reasoning Tree"
        assert "result" in result
        optimizer._mock_lats.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_optimize_mcts_mode(self, optimizer):
        """Test optimization with explicit MCTS mode."""
        result = await optimizer.optimize("Test query", mode="mcts")
        
        assert result["optimizer"] == "MCTS"
        assert result["strategy"] == "Template Selection"
        assert result["best_template"] == "template_a"
        assert result["score"] == 0.8
        optimizer._mock_mcts.optimize_workflow.assert_called_once_with("Test query")

    @pytest.mark.asyncio
    async def test_optimize_auto_mode_selects_lats(self, optimizer):
        """Test auto mode selects LATS for complex queries."""
        result = await optimizer.optimize("Why does this happen?", mode="auto")
        
        assert result["optimizer"] == "LATS"
        optimizer._mock_lats.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_optimize_auto_mode_selects_mcts(self, optimizer):
        """Test auto mode selects MCTS for simple queries."""
        result = await optimizer.optimize("What is X?", mode="auto")
        
        assert result["optimizer"] == "MCTS"
        optimizer._mock_mcts.optimize_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_optimize_auto_default_fallback(self, mock_agent, templates):
        """Test auto mode defaults to mcts when detection returns unknown."""
        with patch("src.workflow.hybrid_optimizer.LATSSearcher") as mock_lats, \
             patch("src.workflow.hybrid_optimizer.MCTSWorkflowOptimizer") as mock_mcts:
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

    def test_init_creates_lats(self):
        """Test that initialization creates LATS searcher."""
        mock_agent = MagicMock()
        mock_agent.llm_provider = MagicMock()
        
        with patch("src.workflow.hybrid_optimizer.LATSSearcher") as mock_lats, \
             patch("src.workflow.hybrid_optimizer.MCTSWorkflowOptimizer") as mock_mcts:
            optimizer = HybridWorkflowOptimizer(mock_agent, ["template"])
            
            mock_lats.assert_called_once_with(llm_provider=mock_agent.llm_provider)

    def test_init_creates_mcts(self):
        """Test that initialization creates MCTS optimizer."""
        mock_agent = MagicMock()
        mock_agent.llm_provider = MagicMock()
        templates = ["template_a", "template_b"]
        
        with patch("src.workflow.hybrid_optimizer.LATSSearcher") as mock_lats, \
             patch("src.workflow.hybrid_optimizer.MCTSWorkflowOptimizer") as mock_mcts:
            optimizer = HybridWorkflowOptimizer(mock_agent, templates)
            
            mock_mcts.assert_called_once_with(mock_agent, templates)
