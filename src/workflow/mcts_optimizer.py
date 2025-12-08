import logging
import math
import random
from dataclasses import dataclass, field
from typing import Any, Optional

from src.agent.core import GeminiAgent

logger = logging.getLogger(__name__)


@dataclass
class MCTSNode:
    """Node in the MCTS tree representing a template choice."""

    state: str  # Template name or action
    parent: Optional["MCTSNode"] = None
    children: list["MCTSNode"] = field(default_factory=list)
    visits: int = 0
    total_reward: float = 0.0
    untried_actions: list[str] = field(default_factory=list)

    @property
    def avg_reward(self) -> float:
        """Calculate the average reward for this node."""
        return self.total_reward / self.visits if self.visits > 0 else 0.0

    def ucb1(self, exploration_weight: float = 1.414) -> float:
        """Calculate the UCB1 score for node selection.

        Args:
            exploration_weight: Balance between exploration and exploitation.

        Returns:
            The UCB1 score for this node.
        """
        if self.visits == 0:
            return float("inf")
        if self.parent is None:
            return float("inf")
        return self.avg_reward + exploration_weight * math.sqrt(
            math.log(self.parent.visits) / self.visits,
        )


class MCTSWorkflowOptimizer:
    """MCTS implementation for fast template/parameter selection."""

    def __init__(
        self,
        agent: GeminiAgent,
        available_templates: list[str],
        iterations: int = 20,
    ):
        """Initialize the MCTS workflow optimizer.

        Args:
            agent: The Gemini agent for content generation.
            available_templates: List of template names to explore.
            iterations: Number of MCTS iterations to run.
        """
        self.agent = agent
        self.templates = available_templates
        self.iterations = iterations

    async def optimize_workflow(self, query: str) -> dict[str, Any]:
        """Run MCTS to find the best template for the query."""
        root = MCTSNode(state="ROOT", untried_actions=self.templates.copy())

        for _ in range(self.iterations):
            node = self._select(root)
            if node.untried_actions:
                node = self._expand(node)
            reward = await self._simulate(node, query)
            self._backpropagate(node, reward)

        # Best child is the one with highest visit count (robustness)
        best_node = (
            max(root.children, key=lambda n: n.visits) if root.children else root
        )

        return {
            "best_template": best_node.state,
            "score": best_node.avg_reward,
            "iterations": self.iterations,
        }

    def _select(self, node: MCTSNode) -> MCTSNode:
        while node.children and not node.untried_actions:
            node = max(node.children, key=lambda n: n.ucb1())
        return node

    def _expand(self, node: MCTSNode) -> MCTSNode:
        action = node.untried_actions.pop()
        child = MCTSNode(state=action, parent=node, untried_actions=[])
        node.children.append(child)
        return child

    async def _simulate(self, node: MCTSNode, query: str) -> float:
        """Simulate execution: In reality, this might use a lighter model or cache."""
        # template_name = node.state
        try:
            # 실제 API 호출 대신 가벼운 시뮬레이션 또는 캐시된 결과 사용 권장
            # 여기서는 예시로 Agent 호출 (실제 구현 시 비용 고려 필요)
            # response = await self.agent.generate_query(query, template_name=template_name)

            # Mock Reward Calculation (비용/길이 기반)
            # 실제로는 결과의 품질을 평가하는 로직이 필요함
            latency_sim = random.uniform(0.5, 2.0)
            return 1.0 / latency_sim  # 단순 예시: 빠를수록 높은 점수
        except Exception:
            return 0.0

    def _backpropagate(self, node: MCTSNode, reward: float) -> None:
        current: MCTSNode | None = node
        while current:
            current.visits += 1
            current.total_reward += reward
            current = current.parent
