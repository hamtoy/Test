"""Shared utilities for agent services.

This module contains helper functions used across multiple service classes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.config.constants import RULE_LOOKUP_OCR_SNIPPET_LENGTH
from src.config.exceptions import APIRateLimitError

if TYPE_CHECKING:
    from src.agent import GeminiAgent


_FORMATTING_RULES_FETCH_FAILED = "Formatting rules 조회 실패: %s"


async def call_model_with_rate_limit_handling(
    agent: GeminiAgent,
    model: Any,
    payload: str,
    *,
    operation: str,
) -> str:
    """Execute model call with rate limit error handling.

    Args:
        agent: The GeminiAgent instance.
        model: The generative model to call.
        payload: The prompt text to send.
        operation: Description of the operation for error messages.

    Returns:
        The response text from the model.

    Raises:
        APIRateLimitError: If rate limit is exceeded.
    """
    try:
        return await agent.retry_handler.call(model, payload)
    except Exception as exc:  # noqa: BLE001
        if agent._is_rate_limit_error(exc):  # noqa: SLF001
            raise APIRateLimitError(
                f"Rate limit exceeded during {operation}: {exc}",
            ) from exc
        raise


def load_guide_context_shared(
    agent: GeminiAgent,
    query_type: str,
    context_stage: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Load guide rules and common mistakes from CSV (shared helper).

    Args:
        agent: The GeminiAgent instance.
        query_type: Type of query (explanation, reasoning, etc).
        context_stage: Stage context (query, rewrite, etc).

    Returns:
        Tuple of (guide_rules, common_mistakes) lists.
    """
    guide_rules: list[dict[str, str]] = []
    common_mistakes: list[dict[str, str]] = []
    try:
        from src.qa.template_rules import (
            get_all_template_context,
            get_neo4j_config,
        )

        neo4j_config = get_neo4j_config()
        if neo4j_config.get("neo4j_password"):
            template_context = get_all_template_context(
                query_type=query_type,
                neo4j_uri=neo4j_config["neo4j_uri"],
                neo4j_user=neo4j_config["neo4j_user"],
                neo4j_password=neo4j_config["neo4j_password"],
                include_mistakes=True,
                context_stage=context_stage,
            )
            guide_rules = template_context.get("guide_rules", []) or []
            common_mistakes = template_context.get("common_mistakes", []) or []
    except Exception as exc:  # noqa: BLE001
        agent.logger.debug("CSV 가이드 조회 실패 (선택사항): %s", exc)
    return guide_rules, common_mistakes


__all__ = [
    "RULE_LOOKUP_OCR_SNIPPET_LENGTH",
    "_FORMATTING_RULES_FETCH_FAILED",
    "call_model_with_rate_limit_handling",
    "load_guide_context_shared",
]
