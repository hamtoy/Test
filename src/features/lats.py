from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, List, Optional

from pydantic import BaseModel, Field

from src.core.interfaces import GenerationResult, LLMProvider


class SearchState(BaseModel):
    """Tree 탐색용 상태 객체. 직렬화/예산 추적을 지원합니다."""

    turns: List[dict[str, Any]] = Field(default_factory=list)
    cumulative_tokens: int = 0
    cumulative_cost: float = 0.0
    last_failure_reason: Optional[str] = None
    focus_history: List[str] = Field(default_factory=list)

    def add_turn(self, action: str) -> "SearchState":
        new_state = self.model_copy(deep=True)
        new_state.turns.append({"action": action})
        new_state.focus_history.append(action)
        return new_state

    def update_budget(self, tokens: int = 0, cost: float = 0.0) -> "SearchState":
        updated = self.model_copy(deep=True)
        updated.cumulative_tokens += max(0, tokens)
        updated.cumulative_cost += max(0.0, cost)
        return updated

    def hash_key(self) -> str:
        """간단한 캐시 키."""
        return str(
            hash((tuple(self.focus_history), len(self.turns), self.cumulative_tokens))
        )


@dataclass
class ValidationResult:
    allowed: bool
    reason: Optional[str] = None
    penalty: float = 0.0


@dataclass
class SearchNode:
    state: SearchState
    action: Optional[str] = None
    reward: float = 0.0
    visits: int = 0
    parent: Optional["SearchNode"] = None
    reflection: Optional[str] = None
    children: List["SearchNode"] = field(default_factory=list)
    result: Optional[dict[str, Any]] = None

    @property
    def depth(self) -> int:
        d = 0
        cur = self.parent
        while cur:
            d += 1
            cur = cur.parent
        return d


GraphValidator = Callable[[SearchState, str], Awaitable[ValidationResult]]
ActionProposer = Callable[[SearchNode], Awaitable[List[str]]]
ActionEvaluator = Callable[[SearchNode], Awaitable[float]]


class LATSSearcher:
    """간단한 LATS 스타일 탐색기 (Selection-Expansion-Evaluation-Backpropagation)."""

    def __init__(
        self,
        llm_provider: Optional[LLMProvider],
        graph_validator: Optional[GraphValidator] = None,
        propose_actions: Optional[ActionProposer] = None,
        evaluate_action: Optional[ActionEvaluator] = None,
        budget_tracker: Optional[Any] = None,  # BudgetTracker instance
        max_visits: int = 10,
        max_depth: int = 3,
        exploration_constant: float = math.sqrt(2),
        token_budget: int = 10000,
        cost_budget: float = 1.0,
    ):
        self.llm_provider = llm_provider
        self.graph_validator = graph_validator
        self.propose_actions = propose_actions
        self.evaluate_action = evaluate_action
        self.budget_tracker = budget_tracker
        self.max_visits = max_visits
        self.max_depth = max_depth
        self.exploration_constant = exploration_constant
        self.token_budget = token_budget
        self.cost_budget = cost_budget
        self.total_visits = 0

    def should_terminate(self, node: SearchNode) -> bool:
        return (
            node.depth >= self.max_depth
            or self.total_visits >= self.max_visits
            or node.state.cumulative_tokens >= self.token_budget
            or node.state.cumulative_cost >= self.cost_budget
        )

    async def run(self, initial_state: Optional[SearchState] = None) -> SearchNode:
        root = SearchNode(state=initial_state or SearchState())
        best = root

        while self.total_visits < self.max_visits:
            leaf = self._select(root)
            if self.should_terminate(leaf):
                reward = leaf.reward
            else:
                expanded = await self._expand(leaf)
                if expanded:
                    leaf = expanded[0]
                reward = await self._evaluate(leaf)
            if reward > best.reward or (leaf.reflection and best is root):
                best = leaf
            self._backpropagate(leaf, reward)
            self.total_visits += 1

        return best

    def _select(self, node: SearchNode) -> SearchNode:
        current = node
        while current.children:
            current = max(
                current.children,
                key=lambda child: self._uct_score(child, current.visits or 1),
            )
        return current

    async def _expand(self, node: SearchNode) -> List[SearchNode]:
        actions: List[str] = []
        if self.propose_actions:
            actions = await self.propose_actions(node)
        elif self.llm_provider:
            prompt = "Suggest next actions for tree search (comma separated)."
            gen = await self.llm_provider.generate_content_async(prompt=prompt)
            actions = [a.strip() for a in gen.content.split(",") if a.strip()]

        if not actions:
            return []

        valid_action_validation_pairs: List[tuple[str, ValidationResult]] = []

        # Parallel validation for performance (only if multiple actions and validator exists)
        if self.graph_validator and len(actions) > 1:
            # Validate all actions in parallel
            validations = await asyncio.gather(
                *[self.graph_validator(node.state, action) for action in actions],
                return_exceptions=True,
            )

            # Filter valid actions and handle exceptions
            for action, validation in zip(actions, validations):
                if isinstance(validation, BaseException):
                    # Log but continue if validation fails
                    continue
                if validation.allowed:
                    valid_action_validation_pairs.append((action, validation))
        elif self.graph_validator:
            # Sequential for single action
            for action in actions:
                validation = await self.graph_validator(node.state, action)
                if validation.allowed:
                    valid_action_validation_pairs.append((action, validation))
        else:
            # No validator: allow all actions
            valid_action_validation_pairs = [
                (action, ValidationResult(allowed=True)) for action in actions
            ]

        # Create child nodes for valid actions
        new_children: List[SearchNode] = []
        for action, validation in valid_action_validation_pairs:
            child_state = node.state.add_turn(action)
            child = SearchNode(
                state=child_state,
                action=action,
                parent=node,
            )
            # Apply penalty from validation
            child.reward -= validation.penalty
            node.children.append(child)
            new_children.append(child)

        return new_children

    async def _evaluate(self, node: SearchNode) -> float:
        try:
            if self.evaluate_action:
                score = await self.evaluate_action(node)
            elif self.llm_provider:
                prompt = f"Score this action from 0-1: {node.action}"
                result: GenerationResult = (
                    await self.llm_provider.generate_content_async(prompt=prompt)
                )
                try:
                    score = float(result.content.strip())
                except ValueError:
                    score = 0.0
                tokens = result.usage.get("total_tokens", 0)
                if tokens:
                    node.state = node.state.update_budget(tokens=tokens)
            else:
                score = 0.0
        except Exception as exc:  # noqa: BLE001
            node.reflection = await self.reflect_on_error(str(exc), node.action or "")
            score = -1.0

        effective = score + node.reward if node.reward < 0 else score
        if score < 0:
            node.reward = effective
        else:
            node.reward = max(node.reward, effective)
        return effective

    def _backpropagate(self, node: SearchNode, reward: float) -> None:
        cur: Optional[SearchNode] = node
        while cur:
            cur.visits += 1
            cur.reward = max(cur.reward, reward)
            cur = cur.parent

    def _uct_score(self, node: SearchNode, total_parent_visits: int) -> float:
        if node.visits == 0:
            return math.inf
        exploitation = node.reward / node.visits
        exploration = self.exploration_constant * math.sqrt(
            math.log(total_parent_visits + 1) / node.visits
        )
        return exploitation + exploration

    async def reflect_on_error(self, error: str, context: str = "") -> str:
        if not self.llm_provider:
            return f"Reflection unavailable: {error[:50]}"
        prompt = (
            f"Error: {error[:200]}\nContext: {context[:200]}\n"
            "Give a short cause (max 20 words)."
        )
        result = await self.llm_provider.generate_content_async(
            prompt=prompt, temperature=0, max_output_tokens=50
        )
        return result.content.strip()
