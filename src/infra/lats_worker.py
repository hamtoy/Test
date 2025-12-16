"""LATS (Language Agent Tree Search) worker utilities.

This module contains LATS-specific logic extracted from worker.py
for better separation of concerns and testability.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from src.features.lats import LATSSearcher, SearchState, ValidationResult

if TYPE_CHECKING:
    from src.agent import GeminiAgent
    from src.infra.worker import OCRTask

logger = logging.getLogger("worker.lats")

# LATS action configuration
ALLOWED_ACTION_PREFIXES: frozenset[str] = frozenset(
    {
        "clean",
        "summarize",
        "clarify",
        "validate",
        "rerank",
    }
)

ALLOWED_FLOW: dict[str, set[str]] = {
    "clean": {"summarize", "clarify", "validate", "rerank", "clean"},
    "summarize": {"clarify", "validate", "rerank", "summarize"},
    "clarify": {"validate", "rerank", "clarify"},
    "validate": {"rerank", "validate"},
    "rerank": {"rerank"},
}

BLOCKED_KEYWORDS: tuple[str, ...] = ("drop ", "delete ", "remove ")


def get_action_prefix(action: str) -> str:
    """Extract the prefix for an action (before ':' if present)."""
    return action.split(":", 1)[0] if ":" in action else action


def check_repeat_penalty(
    state: SearchState, prefix: str
) -> tuple[bool, float, str | None]:
    """Check for action repetition penalties."""
    repeats = sum(1 for a in state.focus_history if a.startswith(prefix))
    if repeats >= 3:
        return False, 1.0, "too many repeats"
    if repeats == 2:
        return True, 0.5, None
    return True, 0.0, None


def check_flow_penalty(state: SearchState, prefix: str) -> float:
    """Check for flow violation penalties."""
    if not state.focus_history:
        return 0.0
    last_prefix = get_action_prefix(state.focus_history[-1])
    allowed_next = ALLOWED_FLOW.get(last_prefix)
    if allowed_next is not None and prefix not in allowed_next:
        return 0.5
    return 0.0


def basic_validation(state: SearchState, action: str) -> tuple[bool, float, str | None]:
    """Perform basic LATS action validation."""
    if action.startswith(("invalid", "forbidden")):
        return False, 1.0, "invalid action"
    penalty = 0.2 if action in state.focus_history else 0.0
    prefix = get_action_prefix(action)
    ok, rep_penalty, reason = check_repeat_penalty(state, prefix)
    if not ok:
        return False, 1.0, reason
    penalty += rep_penalty
    penalty += check_flow_penalty(state, prefix)
    return True, penalty, None


def has_blocked_keyword(action: str) -> bool:
    """Check if action contains blocked keywords."""
    lower = action.lower()
    return any(bad in lower for bad in BLOCKED_KEYWORDS)


def is_unrecognized_prefix(action: str) -> bool:
    """Check if action has an unrecognized prefix."""
    prefix = get_action_prefix(action).lower()
    return bool(prefix) and prefix not in ALLOWED_ACTION_PREFIXES


async def check_graph_constraints(
    action: str, provider: Any
) -> ValidationResult | None:
    """Check LATS action against graph constraints."""
    if not provider:
        return None
    try:
        session_ctx = provider.session()
        async with session_ctx as session:
            if has_blocked_keyword(action):
                return ValidationResult(
                    allowed=False,
                    reason="blocked keyword",
                    penalty=1.0,
                )
            result = await session.run(
                """
                WITH $action AS act
                RETURN
                  act CONTAINS 'error' AS bad_pattern,
                  act STARTS WITH 'forbidden:' AS bad_prefix
                """,
                action=action,
            )
            data = await result.single()
            if data and (data.get("bad_pattern") or data.get("bad_prefix")):
                return ValidationResult(
                    allowed=False,
                    reason="graph constraint",
                    penalty=1.0,
                )
            if is_unrecognized_prefix(action):
                return ValidationResult(
                    allowed=True,
                    reason="unrecognized action",
                    penalty=0.5,
                )
    except Exception as exc:  # noqa: BLE001
        return ValidationResult(allowed=False, reason=str(exc))
    return None


async def validate_action(
    state: SearchState,
    action: str,
    provider: Any,
) -> ValidationResult:
    """Validate a LATS action with all checks."""
    ok, penalty, reason = basic_validation(state, action)
    if not ok:
        return ValidationResult(allowed=False, reason=reason, penalty=penalty)
    provider_result = await check_graph_constraints(action, provider)
    if provider_result is not None:
        return provider_result
    return ValidationResult(allowed=True, penalty=penalty)


def read_ocr_text(image_path: str) -> str:
    """Read OCR text from file for LATS processing."""
    from pathlib import Path

    try:
        return Path(image_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


async def propose_from_agent(agent: GeminiAgent | None, ocr_text: str) -> list[str]:
    """Generate action proposals using GeminiAgent."""
    if not agent or not ocr_text:
        return []
    try:
        queries = await agent.generate_query(ocr_text, None)
        return [q for q in queries if q]
    except Exception as exc:  # noqa: BLE001
        logger.debug("LATS propose via agent failed: %s", exc)
        return []


async def propose_from_llm(provider: Any) -> list[str]:
    """Generate action proposals using LLM provider."""
    prompt = (
        "Propose 3 next actions (comma separated) for OCR post-processing. "
        "Include at least one clean and one summarize variant."
    )
    try:
        resp = await provider.generate_content_async(prompt=prompt)
        return [a.strip() for a in resp.content.split(",") if a.strip()]
    except Exception as exc:  # noqa: BLE001
        logger.debug("LLM propose failed, fallback to defaults: %s", exc)
        return []


def get_default_candidates(request_id: str) -> list[str]:
    """Get default LATS action candidates."""
    return [
        f"clean:{request_id}",
        f"summarize:{request_id}",
        f"clarify:{request_id}",
    ]


def dedup_actions(actions: list[str]) -> list[str]:
    """Remove duplicate actions while preserving order."""
    dedup: list[str] = []
    seen: set[str] = set()
    for act in actions:
        if act and act not in seen:
            dedup.append(act)
            seen.add(act)
    return dedup


def reorder_for_failure(actions: list[str], last_failure: str | None) -> list[str]:
    """Reorder actions based on last failure."""
    if not last_failure:
        return actions
    return [a for a in actions if last_failure not in a] + [
        a for a in actions if last_failure in a
    ]


def ensure_required_actions(actions: list[str], request_id: str) -> list[str]:
    """Ensure required action types are present."""
    required = {
        "clean": f"clean:{request_id}",
        "summarize": f"summarize:{request_id}",
        "clarify": f"clarify:{request_id}",
    }
    for prefix, act in required.items():
        if not any(a.startswith(prefix + ":") for a in actions):
            actions.append(act)
    return actions


def make_proposer(
    task: OCRTask,
    agent: GeminiAgent | None,
    provider: Any,
) -> Callable[[Any], Awaitable[list[str]]]:
    """Create a LATS action proposer function."""

    async def propose(node: Any) -> list[str]:
        candidates: list[str] = []
        if agent:
            ocr_text = read_ocr_text(task.image_path)
            candidates.extend(await propose_from_agent(agent, ocr_text))
        if provider and len(candidates) < 2:
            candidates.extend(await propose_from_llm(provider))
        if not candidates:
            candidates = get_default_candidates(task.request_id)
        dedup = dedup_actions(candidates)
        dedup = reorder_for_failure(dedup, node.state.last_failure_reason)
        dedup = ensure_required_actions(dedup, task.request_id)
        return dedup[:3]

    return propose


def get_action_type(action: str | None) -> str:
    """Extract action type from action string."""
    if not action:
        return ""
    return get_action_prefix(action)


def get_base_score(action_type: str) -> float:
    """Get base score for an action type."""
    return {
        "clean": 0.9,
        "summarize": 0.8,
        "clarify": 0.85,
        "validate": 0.7,
        "rerank": 0.75,
    }.get(action_type, 0.5)


def normalize_action_output(
    action_output: Any,
    action_type: str,
    original_text: str,
) -> tuple[float, str, dict[str, Any]]:
    """Normalize action output to standard format."""
    if isinstance(action_output, dict):
        base_score = float(action_output.get("quality_score", 0.5))
        return base_score, original_text, action_output
    text = str(action_output)
    meta = {"type": action_type or "", "text": text}
    return get_base_score(action_type), text, meta


def calculate_quality_penalty(output_text: str) -> float:
    """Calculate quality penalty based on output."""
    if len(output_text) < 10:
        return 0.3
    if "error" in output_text.lower():
        return 0.5
    return 0.0


def extract_total_tokens(usage: dict[str, Any], fallback: int) -> int:
    """Extract total token count from usage dict."""
    token_total = usage.get("total_tokens")
    if token_total is not None:
        return int(token_total)
    if "prompt_tokens" in usage or "completion_tokens" in usage:
        return int(usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0))
    if "input_tokens" in usage or "output_tokens" in usage:
        return int(usage.get("input_tokens", 0) + usage.get("output_tokens", 0))
    return fallback


def update_budget(node: Any, tokens: int, executor: Any, tracker: Any) -> None:
    """Update LATS budget based on usage."""
    usage = getattr(executor, "last_llm_usage", None)
    if usage:
        usage_dict = dict(usage)
        record = tracker.record_usage(usage_dict)
        token_total = extract_total_tokens(usage_dict, tokens)
        node.state = node.state.update_budget(tokens=token_total, cost=record.cost_usd)
        return
    node.state = node.state.update_budget(tokens=tokens)


async def run_lats_search(
    task: OCRTask,
    config: Any,
    redis_client: Any,
    lats_agent: GeminiAgent | None,
    llm_provider: Any,
    graph_provider: Any,
    process_task_fn: Callable[[OCRTask], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    """Run LATS tree search for a task.

    Args:
        task: OCR task to process
        config: Application configuration
        redis_client: Redis client for caching
        lats_agent: Gemini agent for proposals
        llm_provider: LLM provider for generation
        graph_provider: Graph provider for validation
        process_task_fn: Function to process individual tasks

    Returns:
        Best result from LATS search
    """
    from src.caching.redis_cache import RedisEvalCache
    from src.config.constants import DEFAULT_CACHE_TTL_SECONDS
    from src.features.action_executor import ActionExecutor
    from src.infra.budget import BudgetTracker

    eval_cache = RedisEvalCache(
        redis_client=redis_client,
        ttl=DEFAULT_CACHE_TTL_SECONDS,
    )
    budget_tracker = BudgetTracker(
        budget_limit_usd=getattr(config, "budget_limit_usd", 1.0),
    )

    async def graph_validator(
        state: SearchState,
        action: str,
    ) -> ValidationResult:
        return await validate_action(state, action, graph_provider)

    propose_actions = make_proposer(task, lats_agent, llm_provider)

    async def evaluate_action(node: Any) -> float:
        executor = ActionExecutor(llm_provider=llm_provider)
        result = await process_task_fn(task)
        original_text = result.get("ocr_text", "")
        tokens = len(original_text.split())

        cache_key = f"{node.state.hash_key()}::{node.action}"
        cached_score = await eval_cache.get(cache_key)
        if cached_score is not None:
            node.state = node.state.update_budget(tokens=tokens)
            return float(cached_score + node.reward)

        action_output = await executor.execute_action(
            action=node.action or "clean",
            text=original_text,
            max_length=120,
            use_llm=bool(llm_provider),
        )

        action_type = get_action_type(node.action)
        base_score, processed_text, action_meta = normalize_action_output(
            action_output,
            action_type,
            original_text,
        )
        output_text = (
            processed_text
            if isinstance(action_output, str)
            else str(action_meta.get("text", ""))
        )
        final_score = max(0.0, base_score - calculate_quality_penalty(output_text))

        result["processed_text"] = processed_text
        result["action_output"] = action_meta
        node.result = result

        update_budget(node, tokens, executor, budget_tracker)
        await eval_cache.set(cache_key, final_score)

        return float(final_score + node.reward)

    searcher = LATSSearcher(
        llm_provider=llm_provider,
        graph_validator=graph_validator,
        propose_actions=propose_actions,
        evaluate_action=evaluate_action,
        budget_tracker=budget_tracker,
        max_visits=8,
        max_depth=4,
        exploration_constant=2.0,
        token_budget=getattr(config, "max_output_tokens", 8192),
        cost_budget=0.5,
    )
    best = await searcher.run(SearchState())
    return best.result or {}


# Re-export for backward compatibility
__all__ = [
    "ALLOWED_ACTION_PREFIXES",
    "ALLOWED_FLOW",
    "BLOCKED_KEYWORDS",
    "get_action_prefix",
    "check_repeat_penalty",
    "check_flow_penalty",
    "basic_validation",
    "has_blocked_keyword",
    "is_unrecognized_prefix",
    "check_graph_constraints",
    "validate_action",
    "read_ocr_text",
    "propose_from_agent",
    "propose_from_llm",
    "get_default_candidates",
    "dedup_actions",
    "reorder_for_failure",
    "ensure_required_actions",
    "make_proposer",
    "get_action_type",
    "get_base_score",
    "normalize_action_output",
    "calculate_quality_penalty",
    "extract_total_tokens",
    "update_budget",
    "run_lats_search",
]
