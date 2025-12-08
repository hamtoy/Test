"""비용 추적 모듈.

API 호출 비용 계산 및 예산 관리 기능 제공.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any

from src.config import constants as _constants
from src.config.exceptions import BudgetExceededError

if TYPE_CHECKING:
    from src.config import AppConfig


def _get_pricing_tiers() -> Any:
    """PRICING_TIERS를 동적으로 가져옴 (테스트 패칭 지원)."""
    agent_mod = sys.modules.get("src.agent")
    if agent_mod and hasattr(agent_mod, "PRICING_TIERS"):
        return agent_mod.PRICING_TIERS
    return _constants.PRICING_TIERS


def _get_budget_warning_thresholds() -> list[tuple[int, str]]:
    """BUDGET_WARNING_THRESHOLDS를 동적으로 가져옴 (테스트 패칭 지원)."""
    agent_mod = sys.modules.get("src.agent")
    if agent_mod and hasattr(agent_mod, "BUDGET_WARNING_THRESHOLDS"):
        result: list[tuple[int, str]] = agent_mod.BUDGET_WARNING_THRESHOLDS
        return result
    return _constants.BUDGET_WARNING_THRESHOLDS


class CostTracker:
    """API 비용 추적 및 예산 관리 클래스.

    토큰 사용량에 기반한 비용 계산과 예산 초과 감지를 담당합니다.
    """

    def __init__(self, config: AppConfig) -> None:
        """CostTracker 초기화.

        Args:
            config: 애플리케이션 설정 (모델명, 예산 한도 등)
        """
        self.config = config
        self.logger = logging.getLogger("GeminiWorkflow")
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self._budget_warned_thresholds: set[int] = set()
        self._model_name_override: str | None = None

    @property
    def model_name(self) -> str:
        """모델명 반환 (테스트에서 오버라이드 가능)."""
        return self._model_name_override or self.config.model_name

    @model_name.setter
    def model_name(self, value: str) -> None:
        """모델명 설정 (테스트 지원)."""
        self._model_name_override = value

    def add_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """토큰 사용량 누적.

        Args:
            input_tokens: 입력 토큰 수
            output_tokens: 출력 토큰 수
        """
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

    # Backward compatibility: alias for tests expecting record_usage
    def record_usage(self, input_tokens: int, output_tokens: int) -> None:
        """토큰 사용량 기록 (하위 호환성 wrapper)."""
        self.add_tokens(input_tokens, output_tokens)

    def get_total_cost(self) -> float:
        """세션의 총 API 비용 계산 (USD).

        모델별 단가를 constants에 정의된 티어로 계산합니다.

        Returns:
            총 비용 (USD)

        Raises:
            ValueError: 지원하지 않는 모델이거나 티어 매칭 실패 시
        """
        model_name = self.model_name.lower()
        pricing_tiers = _get_pricing_tiers()
        tiers = pricing_tiers.get(model_name)
        if not tiers:
            raise ValueError(f"Unsupported model for pricing: {model_name}")

        input_rate = output_rate = None
        for tier in tiers:
            max_tokens = tier["max_input_tokens"]
            if max_tokens is None or self.total_input_tokens <= max_tokens:
                input_rate = tier["input_rate"]
                output_rate = tier["output_rate"]
                break

        if input_rate is None or output_rate is None:
            raise ValueError(
                f"No pricing tier matched for model '{model_name}' "
                f"and tokens {self.total_input_tokens}",
            )

        input_cost = (self.total_input_tokens / 1_000_000) * input_rate
        output_cost = (self.total_output_tokens / 1_000_000) * output_rate
        return float(input_cost + output_cost)

    def get_budget_usage_percent(self) -> float:
        """예산 사용률 반환.

        Returns:
            예산 사용률 (%). 예산 미설정 시 0.0
        """
        if not self.config.budget_limit_usd:
            return 0.0
        return (self.get_total_cost() / self.config.budget_limit_usd) * 100

    def check_budget(self) -> None:
        """예산 초과 여부 확인.

        경고 임계치 도달 시 로깅하고, 예산 초과 시 예외 발생.

        Raises:
            BudgetExceededError: 예산 초과 시
        """
        if not self.config.budget_limit_usd:
            return
        total = self.get_total_cost()
        usage_pct = self.get_budget_usage_percent()

        budget_thresholds = _get_budget_warning_thresholds()
        for threshold, level in budget_thresholds:
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

        if total > self.config.budget_limit_usd:
            raise BudgetExceededError(
                f"Session cost ${total:.4f} exceeded budget "
                f"${self.config.budget_limit_usd:.2f}",
            )
