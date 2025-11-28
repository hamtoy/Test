"""Tests for the MCTS workflow optimizer module."""

import math
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.workflow.mcts_optimizer import MCTSNode, MCTSWorkflowOptimizer


class TestMCTSNode:
    """Tests for MCTSNode dataclass."""

    def test_avg_reward_zero_visits(self):
        """Test avg_reward returns 0 when no visits."""
        node = MCTSNode(state="test")
        assert node.avg_reward == 0.0

    def test_avg_reward_with_visits(self):
        """Test avg_reward calculation with visits."""
        node = MCTSNode(state="test", visits=4, total_reward=2.0)
        assert node.avg_reward == 0.5

    def test_ucb1_zero_visits(self):
        """Test UCB1 returns infinity when node has no visits."""
        parent = MCTSNode(state="root", visits=10)
        child = MCTSNode(state="child", parent=parent, visits=0)
        assert child.ucb1() == float("inf")

    def test_ucb1_no_parent(self):
        """Test UCB1 returns infinity when node has no parent."""
        node = MCTSNode(state="root", visits=5, total_reward=2.5)
        assert node.ucb1() == float("inf")

    def test_ucb1_calculation(self):
        """Test UCB1 calculation."""
        parent = MCTSNode(state="root", visits=10)
        child = MCTSNode(
            state="child", parent=parent, visits=4, total_reward=2.0
        )
        
        # UCB1 = avg_reward + exploration_weight * sqrt(ln(parent_visits) / visits)
        expected_avg = 0.5
        expected_exploration = 1.414 * math.sqrt(math.log(10) / 4)
        expected = expected_avg + expected_exploration
        
        assert abs(child.ucb1() - expected) < 0.001

    def test_node_initialization(self):
        """Test MCTSNode initialization with defaults."""
        node = MCTSNode(state="test")
        assert node.state == "test"
        assert node.parent is None
        assert node.children == []
        assert node.visits == 0
        assert node.total_reward == 0.0
        assert node.untried_actions == []

    def test_node_with_parent(self):
        """Test MCTSNode with parent."""
        parent = MCTSNode(state="parent")
        child = MCTSNode(state="child", parent=parent)
        assert child.parent is parent


class TestMCTSWorkflowOptimizer:
    """Tests for MCTSWorkflowOptimizer."""

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
        return MCTSWorkflowOptimizer(mock_agent, templates, iterations=5)

    @pytest.mark.asyncio
    async def test_optimize_workflow(self, optimizer):
        """Test basic workflow optimization."""
        result = await optimizer.optimize_workflow("Test query")
        
        assert "best_template" in result
        assert "score" in result
        assert "iterations" in result
        assert result["iterations"] == 5

    @pytest.mark.asyncio
    async def test_optimize_finds_template(self, optimizer, templates):
        """Test that optimization finds a template from available ones."""
        result = await optimizer.optimize_workflow("Test query")
        
        # Best template should be one of the available templates or ROOT
        assert result["best_template"] in templates or result["best_template"] == "ROOT"

    def test_select_unexpanded_node(self, optimizer):
        """Test _select returns node with untried actions."""
        root = MCTSNode(state="ROOT", untried_actions=["action1"])
        result = optimizer._select(root)
        assert result is root

    def test_select_traverses_tree(self, optimizer):
        """Test _select traverses to node with highest UCB1."""
        root = MCTSNode(state="ROOT")
        child1 = MCTSNode(
            state="child1", parent=root, visits=5, total_reward=2.5
        )
        child2 = MCTSNode(
            state="child2", parent=root, visits=5, total_reward=4.0
        )
        root.children = [child1, child2]
        root.visits = 10
        
        result = optimizer._select(root)
        # Should select child2 (higher reward)
        assert result is child2

    def test_expand(self, optimizer):
        """Test _expand creates a new child node."""
        root = MCTSNode(state="ROOT", untried_actions=["action1", "action2"])
        child = optimizer._expand(root)
        
        assert child.state == "action2"  # Last action popped
        assert child.parent is root
        assert child in root.children
        assert len(root.untried_actions) == 1

    @pytest.mark.asyncio
    async def test_simulate(self, optimizer):
        """Test _simulate returns a reward."""
        node = MCTSNode(state="template_a")
        reward = await optimizer._simulate(node, "Test query")
        
        # Reward should be between 0 and some positive value
        assert reward >= 0

    def test_backpropagate(self, optimizer):
        """Test _backpropagate updates node statistics."""
        root = MCTSNode(state="ROOT")
        child = MCTSNode(state="child", parent=root)
        grandchild = MCTSNode(state="grandchild", parent=child)
        
        optimizer._backpropagate(grandchild, 0.5)
        
        assert grandchild.visits == 1
        assert grandchild.total_reward == 0.5
        assert child.visits == 1
        assert child.total_reward == 0.5
        assert root.visits == 1
        assert root.total_reward == 0.5

    @pytest.mark.asyncio
    async def test_optimize_empty_templates(self, mock_agent):
        """Test optimization with no templates."""
        optimizer = MCTSWorkflowOptimizer(mock_agent, [], iterations=3)
        result = await optimizer.optimize_workflow("Test")
        
        assert result["best_template"] == "ROOT"

    @pytest.mark.asyncio
    async def test_optimize_single_template(self, mock_agent):
        """Test optimization with single template."""
        optimizer = MCTSWorkflowOptimizer(mock_agent, ["only_template"], iterations=5)
        result = await optimizer.optimize_workflow("Test")
        
        # With only one template, it should be selected
        assert result["best_template"] in ["only_template", "ROOT"]

    @pytest.mark.asyncio
    async def test_simulate_exception_handling(self, optimizer):
        """Test _simulate handles exceptions gracefully."""
        node = MCTSNode(state="error_template")
        
        # Simulate should not raise, even if internal logic fails
        reward = await optimizer._simulate(node, "Test query")
        assert isinstance(reward, float)
