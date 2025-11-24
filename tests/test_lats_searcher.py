from __future__ import annotations

import math
from typing import List

import pytest

from src.core.interfaces import GenerationResult, LLMProvider
from src.lats_searcher import (
    LATSSearcher,
    SearchNode,
    SearchState,
    ValidationResult,
)


class _FakeLLM(LLMProvider):
    def __init__(self, responses: List[str]):
        self.responses = responses
        self.calls = 0

    async def generate_content_async(self, prompt: str, **_kwargs):  # noqa: ANN001
        content = self.responses[self.calls % len(self.responses)]
        self.calls += 1
        return GenerationResult(content=content)

    async def count_tokens(self, text: str) -> int:  # noqa: ARG002
        return len(text.split())


@pytest.mark.asyncio
async def test_lats_finds_best_child_with_mock_callbacks():
    actions = {"root": ["a1", "a2"], "a1": [], "a2": []}
    rewards = {"a1": 0.2, "a2": 0.8}

    async def propose(node: SearchNode):
        return actions.get(node.action or "root", [])

    async def evaluate(node: SearchNode):
        return rewards.get(node.action or "", 0.0)

    searcher = LATSSearcher(
        llm_provider=None,
        graph_validator=None,
        propose_actions=propose,
        evaluate_action=evaluate,
        max_visits=4,
    )
    best = await searcher.run(SearchState())

    assert best.action == "a2"
    assert math.isclose(best.reward, 0.8)


@pytest.mark.asyncio
async def test_graph_validator_prunes_actions():
    async def propose(node: SearchNode):  # noqa: ARG001
        return ["bad", "good"]

    async def graph_validator(_state: SearchState, action: str):
        return ValidationResult(allowed=action != "bad")

    async def evaluate(node: SearchNode):
        return 0.5 if node.action == "good" else 0.0

    searcher = LATSSearcher(
        llm_provider=None,
        graph_validator=graph_validator,
        propose_actions=propose,
        evaluate_action=evaluate,
        max_visits=2,
    )
    best = await searcher.run(SearchState())
    assert best.action == "good"
    assert best.reward == 0.5


@pytest.mark.asyncio
async def test_graph_penalty_reduces_score():
    async def propose(node: SearchNode):  # noqa: ARG001
        return ["penalty"]

    async def graph_validator(_state: SearchState, action: str):
        return ValidationResult(allowed=True, penalty=0.3 if action == "penalty" else 0)

    async def evaluate(node: SearchNode):
        return 1.0

    searcher = LATSSearcher(
        llm_provider=None,
        graph_validator=graph_validator,
        propose_actions=propose,
        evaluate_action=evaluate,
        max_visits=1,
    )
    best = await searcher.run(SearchState())
    assert best.reward == 0.7


@pytest.mark.asyncio
async def test_should_terminate_on_budget_and_depth():
    state = SearchState(cumulative_tokens=60000, cumulative_cost=2.0)
    searcher = LATSSearcher(
        llm_provider=None, max_visits=1, token_budget=50000, cost_budget=1.0
    )
    node = SearchNode(state=state)
    assert searcher.should_terminate(node)


@pytest.mark.asyncio
async def test_reflection_uses_llm():
    llm = _FakeLLM(["insight"])
    searcher = LATSSearcher(llm_provider=llm)
    text = await searcher.reflect_on_error("boom", context="ctx")
    assert "insight" in text


@pytest.mark.asyncio
async def test_reflection_without_llm_returns_fallback():
    searcher = LATSSearcher(llm_provider=None)
    text = await searcher.reflect_on_error("boom")
    assert "Reflection unavailable" in text
