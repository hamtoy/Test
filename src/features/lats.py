"""Language Agent Tree Search (LATS) implementation.

This module provides the LATS reasoning engine, which uses Monte Carlo Tree Search (MCTS)
to enable the agent to explore multiple reasoning paths, perform self-reflection,
and backtrack from dead ends. It supports parallel child node evaluation for performance.
"""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from src.config.constants import LATS_EXPANSION_MAX_OUTPUT_TOKENS
from src.core.interfaces import GenerationResult, LLMProvider

if TYPE_CHECKING:
    from src.features.action_executor import ActionExecutor

logger = logging.getLogger(__name__)


class SearchState(BaseModel):
    """Tree 탐색용 상태 객체. 직렬화/예산 추적을 지원합니다."""

    turns: list[dict[str, Any]] = Field(default_factory=list)
    cumulative_tokens: int = 0
    cumulative_cost: float = 0.0
    last_failure_reason: str | None = None
    focus_history: list[str] = Field(default_factory=list)

    # LATS 상태 주입을 위한 필드
    query: str | None = None
    ocr_text: str | None = None
    current_answer: str | None = None

    def add_turn(self, action: str) -> SearchState:
        """Add a new turn to the search state.

        Args:
            action: The action taken in this turn.

        Returns:
            A new SearchState with the turn added.
        """
        new_state = self.model_copy(deep=True)
        new_state.turns.append({"action": action})
        new_state.focus_history.append(action)
        return new_state

    def update_budget(self, tokens: int = 0, cost: float = 0.0) -> SearchState:
        """Update the cumulative budget tracking.

        Args:
            tokens: Number of tokens used.
            cost: Cost incurred.

        Returns:
            A new SearchState with updated budget.
        """
        updated = self.model_copy(deep=True)
        updated.cumulative_tokens += max(0, tokens)
        updated.cumulative_cost += max(0.0, cost)
        return updated

    def hash_key(self) -> str:
        """간단한 캐시 키."""
        return str(
            hash((tuple(self.focus_history), len(self.turns), self.cumulative_tokens)),
        )


@dataclass
class ValidationResult:
    """Result of validating an action against graph constraints."""

    allowed: bool
    reason: str | None = None
    penalty: float = 0.0


@dataclass
class SearchNode:
    """Node in the LATS search tree."""

    state: SearchState
    action: str | None = None
    reward: float = 0.0
    visits: int = 0
    parent: SearchNode | None = None
    reflection: str | None = None
    children: list[SearchNode] = field(default_factory=list)
    result: dict[str, Any] | None = None

    @property
    def depth(self) -> int:
        """Calculate the depth of this node in the search tree."""
        d = 0
        cur = self.parent
        while cur:
            d += 1
            cur = cur.parent
        return d


GraphValidator = Callable[[SearchState, str], Awaitable[ValidationResult]]
ActionProposer = Callable[[SearchNode], Awaitable[list[str]]]
ActionEvaluator = Callable[[SearchNode], Awaitable[float]]


class LATSSearcher:
    """간단한 LATS 스타일 탐색기 (Selection-Expansion-Evaluation-Backpropagation)."""

    def __init__(
        self,
        llm_provider: LLMProvider | None,
        graph_validator: GraphValidator | None = None,
        propose_actions: ActionProposer | None = None,
        evaluate_action: ActionEvaluator | None = None,
        budget_tracker: Any | None = None,  # BudgetTracker instance
        action_executor: ActionExecutor | None = None,
        max_visits: int = 10,
        max_depth: int = 3,
        exploration_constant: float = math.sqrt(2),
        token_budget: int = 10000,
        cost_budget: float = 1.0,
        concurrency_limit: int = 5,
        validation_penalty: float = 0.3,
    ):
        """Initialize the LATS searcher.

        Args:
            llm_provider: LLM provider for generating content.
            graph_validator: Optional validator for graph constraints.
            propose_actions: Optional action proposer function.
            evaluate_action: Optional action evaluator function.
            budget_tracker: Optional budget tracking instance.
            action_executor: Optional ActionExecutor for concrete validation.
            max_visits: Maximum number of node visits.
            max_depth: Maximum search depth.
            exploration_constant: UCB1 exploration constant.
            token_budget: Maximum token budget.
            cost_budget: Maximum cost budget.
            concurrency_limit: Maximum concurrent LLM API calls (for rate limiting).
            validation_penalty: Penalty applied to nodes that fail concrete validation.
        """
        self.llm_provider = llm_provider
        self.graph_validator = graph_validator
        self.propose_actions = propose_actions
        self.evaluate_action = evaluate_action
        self.budget_tracker = budget_tracker
        self.action_executor = action_executor
        self.max_visits = max_visits
        self.max_depth = max_depth
        self.exploration_constant = exploration_constant
        self.token_budget = token_budget
        self.cost_budget = cost_budget
        self.concurrency_limit = concurrency_limit
        self.validation_penalty = validation_penalty
        self._semaphore: asyncio.Semaphore | None = None
        self.total_visits = 0

    def should_terminate(self, node: SearchNode) -> bool:
        """Check if the search should terminate at this node."""
        return (
            node.depth >= self.max_depth
            or self.total_visits >= self.max_visits
            or node.state.cumulative_tokens >= self.token_budget
            or node.state.cumulative_cost >= self.cost_budget
        )

    async def run(self, initial_state: SearchState | None = None) -> SearchNode:
        """Run the LATS search algorithm.

        Args:
            initial_state: Optional initial search state.

        Returns:
            The best node found during search.
        """
        # Initialize semaphore for rate limiting
        self._semaphore = asyncio.Semaphore(self.concurrency_limit)
        root = SearchNode(state=initial_state or SearchState())
        best = root

        while self.total_visits < self.max_visits:
            leaf = self._select(root)
            if self.should_terminate(leaf):
                reward = leaf.reward
            else:
                expanded = await self._expand(leaf)
                if expanded:
                    # Parallel evaluation of expanded children with rate limiting
                    rewards = await self._evaluate_children_parallel(expanded)
                    # Find best child from this expansion
                    best_idx = max(range(len(rewards)), key=lambda i, r=rewards: r[i])  # type: ignore[misc]
                    leaf = expanded[best_idx]
                    reward = rewards[best_idx]
                else:
                    reward = await self._evaluate(leaf)
            if reward > best.reward or (leaf.reflection and best is root):
                best = leaf
            self._backpropagate(leaf, reward)
            self.total_visits += 1

        return best

    async def _evaluate_children_parallel(
        self,
        children: list[SearchNode],
    ) -> list[float]:
        """Evaluate multiple child nodes in parallel with rate limiting.

        Args:
            children: List of child nodes to evaluate.

        Returns:
            List of reward scores for each child.
        """
        if not children:
            return []

        async def evaluate_with_semaphore(child: SearchNode) -> float:
            """Evaluate a single child with semaphore for rate limiting."""
            async with self._semaphore or asyncio.Semaphore(self.concurrency_limit):
                return await self._evaluate(child)

        # Use asyncio.gather for parallel evaluation
        rewards = await asyncio.gather(
            *[evaluate_with_semaphore(child) for child in children],
        )
        return list(rewards)

    def _select(self, node: SearchNode) -> SearchNode:
        current = node
        while current.children:
            parent_visits = current.visits or 1

            def _uct(
                child: SearchNode,
                parent_visits: int = parent_visits,
            ) -> float:
                return self._uct_score(child, parent_visits)

            current = max(current.children, key=_uct)
        return current

    async def _expand(self, node: SearchNode) -> list[SearchNode]:
        actions = await self._propose_actions_for_expand(node)
        if not actions:
            return []

        valid_pairs = await self._validate_actions_for_expand(node, actions)
        if not valid_pairs:
            return []

        return self._create_children(node, valid_pairs)

    async def _propose_actions_for_expand(self, node: SearchNode) -> list[str]:
        if self.propose_actions:
            return await self.propose_actions(node)
        if not self.llm_provider:
            return []
        prompt = "Suggest next actions for tree search (comma separated)."
        gen = await self.llm_provider.generate_content_async(prompt=prompt)
        return [a.strip() for a in gen.content.split(",") if a.strip()]

    async def _validate_actions_for_expand(
        self,
        node: SearchNode,
        actions: list[str],
    ) -> list[tuple[str, ValidationResult]]:
        if not self.graph_validator:
            return [(action, ValidationResult(allowed=True)) for action in actions]
        if len(actions) > 1:
            return await self._validate_actions_parallel(node, actions)
        return await self._validate_actions_sequential(node, actions)

    async def _validate_actions_parallel(
        self,
        node: SearchNode,
        actions: list[str],
    ) -> list[tuple[str, ValidationResult]]:
        if not self.graph_validator:
            return []

        async def validate_with_semaphore(
            action: str,
        ) -> tuple[str, ValidationResult | BaseException]:
            """Validate action with semaphore for rate limiting."""
            async with self._semaphore or asyncio.Semaphore(self.concurrency_limit):
                try:
                    result = await self.graph_validator(node.state, action)  # type: ignore[misc]
                    return (action, result)
                except Exception as e:  # noqa: BLE001
                    return (action, e)

        results = await asyncio.gather(
            *[validate_with_semaphore(action) for action in actions],
        )
        pairs: list[tuple[str, ValidationResult]] = []
        for action, validation in results:
            if isinstance(validation, BaseException):
                continue
            if validation.allowed:
                pairs.append((action, validation))
        return pairs

    async def _validate_actions_sequential(
        self,
        node: SearchNode,
        actions: list[str],
    ) -> list[tuple[str, ValidationResult]]:
        if not self.graph_validator:
            return []
        pairs: list[tuple[str, ValidationResult]] = []
        for action in actions:
            validation = await self.graph_validator(node.state, action)
            if validation.allowed:
                pairs.append((action, validation))
        return pairs

    def _create_children(
        self,
        node: SearchNode,
        valid_pairs: list[tuple[str, ValidationResult]],
    ) -> list[SearchNode]:
        new_children: list[SearchNode] = []
        for action, validation in valid_pairs:
            child_state = node.state.add_turn(action)
            child = SearchNode(state=child_state, action=action, parent=node)
            child.reward -= validation.penalty
            node.children.append(child)
            new_children.append(child)
        return new_children

    async def _evaluate(self, node: SearchNode) -> float:
        """Evaluate a node's score, integrating ActionExecutor for concrete validation."""
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

            # Concrete validation using ActionExecutor (if available)
            validation_passed = await self._run_concrete_validation(node)
            if not validation_passed:
                score -= self.validation_penalty
                logger.debug(
                    "Node %s failed concrete validation, applying penalty %.2f",
                    node.action,
                    self.validation_penalty,
                )

        except Exception as exc:  # noqa: BLE001
            node.reflection = await self.reflect_on_error(str(exc), node.action or "")
            score = -1.0

        effective = score + node.reward if node.reward < 0 else score
        if score < 0:
            node.reward = effective
        else:
            node.reward = max(node.reward, effective)

        logger.debug(
            "Node depth=%d action=%s evaluated score=%.3f effective=%.3f",
            node.depth,
            node.action,
            score,
            effective,
        )
        return effective

    async def _run_concrete_validation(self, node: SearchNode) -> bool:
        """Run concrete validation using ActionExecutor.

        Args:
            node: The node to validate.

        Returns:
            True if validation passes (or no executor available), False otherwise.
        """
        if not self.action_executor:
            return True  # No executor, skip validation

        if not node.action:
            return True  # No action to validate

        try:
            # Use ActionExecutor to validate the current state/action
            result = await self.action_executor.execute_action(
                action="validate",
                text=node.action,
                use_llm=False,  # Use deterministic validation for speed
            )
            # Check quality_score from validation result
            if isinstance(result, dict):
                quality_score = float(result.get("quality_score", 1.0))
                passed = quality_score >= 0.5
                if not passed:
                    logger.debug(
                        "Concrete validation failed for action=%s quality=%.2f",
                        node.action,
                        quality_score,
                    )
                return passed
            return True
        except Exception as e:  # noqa: BLE001
            logger.warning("ActionExecutor validation error: %s", e)
            return True  # Don't penalize on executor errors

    def _backpropagate(self, node: SearchNode, reward: float) -> None:
        cur: SearchNode | None = node
        while cur:
            cur.visits += 1
            cur.reward = max(cur.reward, reward)
            cur = cur.parent

    def _uct_score(self, node: SearchNode, total_parent_visits: int) -> float:
        if node.visits == 0:
            return math.inf
        exploitation = node.reward / node.visits
        exploration = self.exploration_constant * math.sqrt(
            math.log(total_parent_visits + 1) / node.visits,
        )
        return exploitation + exploration

    async def reflect_on_error(self, error: str, context: str = "") -> str:
        """Reflect on an error using the LLM provider.

        Args:
            error: The error message to reflect on.
            context: Optional context for the error.

        Returns:
            A short reflection on the error cause.
        """
        if not self.llm_provider:
            return f"Reflection unavailable: {error[:50]}"
        prompt = (
            f"Error: {error[:200]}\nContext: {context[:200]}\n"
            "Give a short cause (max 20 words)."
        )
        result = await self.llm_provider.generate_content_async(
            prompt=prompt,
            temperature=0,
            max_output_tokens=LATS_EXPANSION_MAX_OUTPUT_TOKENS,
        )
        return result.content.strip()
