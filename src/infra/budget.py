from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# Gemini 3 Pro Preview pricing (USD per 1M tokens)
# Source: Google AI Studio pricing page (<=200K tokens tier)
GEMINI_PRO_PREVIEW_PRICING = {
    "input": 2.0,  # $2.00 per 1M input tokens
    "output": 12.0,  # $12.00 per 1M output tokens
    "cached_input": 0.5,  # $0.50 per 1M cached tokens (estimate)
}

# Note: >200K tokens tier has higher rates:
# Input: $4.00/1M, Output: $18.00/1M


@dataclass
class UsageRecord:
    """단일 LLM 호출의 사용량 기록."""

    model: str = "gemini-3-pro-preview"
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BudgetTracker:
    """gemini-3-pro-preview 모델의 비용 추적 및 예산 관리."""

    def __init__(self, budget_limit_usd: float = 1.0):
        """Initialize the budget tracker.

        Args:
            budget_limit_usd: Maximum budget in USD.
        """
        self.budget_limit_usd = budget_limit_usd
        self.records: List[UsageRecord] = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cached_tokens = 0
        self.total_cost_usd = 0.0

    def record_usage(
        self,
        usage: Optional[Dict[str, int]] = None,
        timestamp: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        *,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        cached_input_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
    ) -> UsageRecord:
        """LLM 사용량 기록 및 비용 계산.

        `usage` 딕셔너리 혹은 개별 토큰 수 인자를 모두 지원한다.
        """
        usage = usage or {}
        if input_tokens is not None:
            usage["input_tokens"] = input_tokens
        if output_tokens is not None:
            usage["output_tokens"] = output_tokens
        if cached_input_tokens is not None:
            usage["cached_input_tokens"] = cached_input_tokens
        if total_tokens is not None:
            usage["total_tokens"] = total_tokens

        # 레거시 키 호환
        input_tokens_val = usage.get("prompt_tokens", usage.get("input_tokens", 0))
        output_tokens_val = usage.get(
            "completion_tokens", usage.get("output_tokens", 0)
        )
        cached_tokens_val = usage.get(
            "cached_input_tokens", usage.get("cached_tokens", 0)
        )
        total_tokens_val = usage.get(
            "total_tokens", input_tokens_val + output_tokens_val
        )

        cost_input = (input_tokens_val / 1_000_000) * GEMINI_PRO_PREVIEW_PRICING[
            "input"
        ]
        cost_output = (output_tokens_val / 1_000_000) * GEMINI_PRO_PREVIEW_PRICING[
            "output"
        ]
        cost_cached = (cached_tokens_val / 1_000_000) * GEMINI_PRO_PREVIEW_PRICING[
            "cached_input"
        ]
        total_cost = cost_input + cost_output + cost_cached

        record = UsageRecord(
            input_tokens=input_tokens_val,
            output_tokens=output_tokens_val,
            cached_input_tokens=cached_tokens_val,
            total_tokens=total_tokens_val,
            cost_usd=total_cost,
            timestamp=timestamp,
            metadata=metadata or {},
        )

        self.records.append(record)
        self.total_input_tokens += input_tokens_val
        self.total_output_tokens += output_tokens_val
        self.total_cached_tokens += cached_tokens_val
        self.total_cost_usd += total_cost

        return record

    def get_total_cost(self) -> float:
        """Get the total cost incurred so far."""
        return self.total_cost_usd

    def get_budget_usage_percent(self) -> float:
        """Get the percentage of budget used."""
        if self.budget_limit_usd <= 0:
            return 0.0
        return (self.total_cost_usd / self.budget_limit_usd) * 100

    def is_budget_exceeded(self, threshold: float = 1.0) -> bool:
        """Check if budget has been exceeded.

        Args:
            threshold: Fraction of budget that triggers exceeded (default 1.0).

        Returns:
            True if budget usage exceeds threshold.
        """
        return self.get_budget_usage_percent() >= (threshold * 100)

    def get_statistics(self) -> Dict[str, Any]:
        """Get usage statistics as a dictionary."""
        return {
            "total_calls": len(self.records),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cached_tokens": self.total_cached_tokens,
            "total_cost_usd": self.total_cost_usd,
            "budget_limit_usd": self.budget_limit_usd,
            "budget_usage_percent": self.get_budget_usage_percent(),
            "remaining_budget_usd": max(0, self.budget_limit_usd - self.total_cost_usd),
        }
