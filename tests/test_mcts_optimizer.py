"""Tests for the MCTS workflow optimizer module."""

import math
from unittest.mock import AsyncMock, MagicMock

import pytest
"""Tests for the MCTS optimizer module."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from src.workflow.mcts_optimizer import MCTSNode, MCTSWorkflowOptimizer


class TestMCTSNode:
    """Tests for MCTSNode dataclass."""

    def test_avg_reward_zero_visits(self):
        """Test avg_reward returns 0 when no visits."""
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
