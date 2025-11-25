"""비용 추적 및 예산 관리 모듈."""

from __future__ import annotations

import logging
from typing import Set

from src.constants import PRICING_TIERS, BUDGET_WARNING_THRESHOLDS
from src.exceptions import BudgetExceededError


class CostTracker:
    """API 비용 추적 및 예산 관리."""

    def __init__(self, model_name: str, budget_limit_usd: float | None = None):
        self.model_name = model_name.lower()
        self.budget_limit_usd = budget_limit_usd
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self._budget_warned_thresholds: Set[int] = set()
        self.logger = logging.getLogger(__name__)

    def record_usage(self, input_tokens: int, output_tokens: int) -> None:
        """토큰 사용량 기록."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

    def get_total_cost(self) -> float:
        """
        세션의 총 API 비용 계산 (USD)
        모델별 단가를 constants에 정의된 티어로 계산 (입력 토큰 기반)
        """
        tiers = PRICING_TIERS.get(self.model_name)
        if not tiers:
            # Fallback or raise? Original code raised ValueError
            raise ValueError(f"Unsupported model for pricing: {self.model_name}")

        input_rate = None
        output_rate = None

        for tier in tiers:
            max_tokens = tier["max_input_tokens"]
            if max_tokens is None or self.total_input_tokens <= max_tokens:
                input_rate = tier["input_rate"]
                output_rate = tier["output_rate"]
                break

        if input_rate is None or output_rate is None:
            raise ValueError(
                f"No pricing tier matched for model '{self.model_name}' and tokens {self.total_input_tokens}"
            )

        input_cost = (self.total_input_tokens / 1_000_000) * input_rate
        output_cost = (self.total_output_tokens / 1_000_000) * output_rate
        return input_cost + output_cost

    def get_budget_usage_percent(self) -> float:
        """Return budget usage percent; 0 if no budget configured."""
        if not self.budget_limit_usd:
            return 0.0
        return (self.get_total_cost() / self.budget_limit_usd) * 100

    def check_budget(self) -> None:
        """Raise if total cost exceeds budget."""
        if not self.budget_limit_usd:
            return
        total = self.get_total_cost()
        usage_pct = self.get_budget_usage_percent()

        for threshold, level in BUDGET_WARNING_THRESHOLDS:
            if (
                usage_pct >= threshold
                and threshold not in self._budget_warned_thresholds
            ):
                self.logger.warning(
                    "Budget nearing limit: %s%% used (level=%s)",
                    round(usage_pct, 2),
                    level,
                )
                self._budget_warned_thresholds.add(threshold)

        if total > self.budget_limit_usd:
            raise BudgetExceededError(
                f"Session cost ${total:.4f} exceeded budget ${self.budget_limit_usd:.2f}"
            )
