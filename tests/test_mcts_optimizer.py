"""Tests for the MCTS optimizer module."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from src.workflow.mcts_optimizer import MCTSNode, MCTSWorkflowOptimizer


class TestMCTSNode:
    """Tests for MCTSNode class."""

    def test_node_creation(self):
        """Test basic node creation."""
        node = MCTSNode(state="test_template")
        assert node.state == "test_template"
        assert node.parent is None
        assert node.children == []
        assert node.visits == 0
        assert node.total_reward == 0.0
        assert node.untried_actions == []

    def test_node_with_parent(self):
        """Test node creation with parent."""
        parent = MCTSNode(state="ROOT")
        child = MCTSNode(state="child", parent=parent)
        assert child.parent == parent
        assert child.state == "child"

    def test_avg_reward_zero_visits(self):
        """Test avg_reward with zero visits."""
        node = MCTSNode(state="test")
        assert node.avg_reward == 0.0

    def test_avg_reward_with_visits(self):
        """Test avg_reward with visits."""
        node = MCTSNode(state="test")
        node.visits = 4
        node.total_reward = 10.0
        assert node.avg_reward == 2.5

    def test_ucb1_zero_visits(self):
        """Test UCB1 with zero visits returns infinity."""
        node = MCTSNode(state="test")
        assert node.ucb1() == float("inf")

    def test_ucb1_no_parent(self):
        """Test UCB1 with no parent returns infinity."""
        node = MCTSNode(state="test")
        node.visits = 5
        assert node.ucb1() == float("inf")

    def test_ucb1_with_parent_and_visits(self):
        """Test UCB1 calculation with parent and visits."""
        parent = MCTSNode(state="ROOT")
        parent.visits = 10
        child = MCTSNode(state="child", parent=parent)
        child.visits = 3
        child.total_reward = 2.0

        ucb1_value = child.ucb1()
        # Should be a finite positive number
        assert ucb1_value > 0
        assert ucb1_value < float("inf")


class TestMCTSWorkflowOptimizer:
    """Tests for MCTSWorkflowOptimizer class."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock GeminiAgent."""
        agent = MagicMock()
        agent.generate_query = AsyncMock(return_value="mocked response")
        return agent

    @pytest.fixture
    def optimizer(self, mock_agent):
        """Create an optimizer instance."""
        templates = ["template_a", "template_b", "template_c"]
        return MCTSWorkflowOptimizer(mock_agent, templates, iterations=5)

    @pytest.mark.asyncio
    async def test_optimize_workflow_basic(self, optimizer):
        """Test basic workflow optimization."""
        result = await optimizer.optimize_workflow("test query")

        assert "best_template" in result
        assert "score" in result
        assert "iterations" in result
        assert result["iterations"] == 5

    @pytest.mark.asyncio
    async def test_optimize_workflow_returns_template(self, optimizer):
        """Test that optimization returns a valid template."""
        result = await optimizer.optimize_workflow("analyze this query")

        # The best template should be one of the available templates or ROOT
        valid_states = ["template_a", "template_b", "template_c", "ROOT"]
        assert result["best_template"] in valid_states

    def test_select_node(self, optimizer):
        """Test node selection."""
        root = MCTSNode(state="ROOT", untried_actions=["a", "b"])
        # With untried actions, select should return the root
        selected = optimizer._select(root)
        assert selected == root

    def test_select_with_children(self, optimizer):
        """Test selection traverses to best child."""
        root = MCTSNode(state="ROOT", untried_actions=[])
        child1 = MCTSNode(state="child1", parent=root)
        child1.visits = 10
        child1.total_reward = 5.0
        child2 = MCTSNode(state="child2", parent=root)
        child2.visits = 5
        child2.total_reward = 4.0
        root.children = [child1, child2]
        root.visits = 15

        selected = optimizer._select(root)
        # Should select one of the children based on UCB1
        assert selected in [child1, child2]

    def test_expand_node(self, optimizer):
        """Test node expansion."""
        root = MCTSNode(state="ROOT", untried_actions=["action1", "action2"])

        new_node = optimizer._expand(root)

        assert new_node.state == "action2"  # Last action popped
        assert new_node.parent == root
        assert new_node in root.children
        assert len(root.untried_actions) == 1

    @pytest.mark.asyncio
    async def test_simulate_returns_reward(self, optimizer):
        """Test simulation returns a reward."""
        node = MCTSNode(state="template_a")

        reward = await optimizer._simulate(node, "test query")

        # Reward should be positive (1/latency where latency is 0.5-2.0)
        assert 0.0 < reward <= 2.0

    def test_backpropagate(self, optimizer):
        """Test backpropagation updates node stats."""
        root = MCTSNode(state="ROOT")
        root.visits = 5
        root.total_reward = 2.0

        child = MCTSNode(state="child", parent=root)
        child.visits = 1
        child.total_reward = 0.5

        optimizer._backpropagate(child, 1.0)

        # Both child and root should have updated stats
        assert child.visits == 2
        assert child.total_reward == 1.5
        assert root.visits == 6
        assert root.total_reward == 3.0

    def test_backpropagate_root_only(self, optimizer):
        """Test backpropagation on root node only."""
        root = MCTSNode(state="ROOT")

        optimizer._backpropagate(root, 0.5)

        assert root.visits == 1
        assert root.total_reward == 0.5
