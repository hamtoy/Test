"""Rich UI 패널 렌더링."""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from rich.console import Console
from rich.panel import Panel

from src.constants import (
    COST_PANEL_TEMPLATE,
    PANEL_TITLE_BUDGET,
    PANEL_TITLE_COST,
    PANEL_TITLE_QUERIES,
)

if TYPE_CHECKING:
    from src.agent import GeminiAgent


console = Console()


def render_cost_panel(agent: GeminiAgent) -> Panel:
    """비용, 토큰 사용량, 캐시 통계를 표시하는 Rich Panel을 생성합니다.

    Args:
        agent: 사용량 통계를 포함하는 GeminiAgent 인스턴스

    Returns:
        비용 및 사용량 정보가 설정된 Rich Panel 객체
    """
    cost_fn = getattr(agent, "get_total_cost", None)
    cost_info = COST_PANEL_TEMPLATE.format(
        cost=cost_fn() if callable(cost_fn) else 0.0,
        input_tokens=agent.total_input_tokens,
        output_tokens=agent.total_output_tokens,
        cache_hits=agent.cache_hits,
        cache_misses=agent.cache_misses,
    )
    return Panel(cost_info, title=PANEL_TITLE_COST, border_style="blue")


def render_budget_panel(agent: GeminiAgent) -> Panel:
    """예산 정보 패널을 생성합니다.

    Args:
        agent: 예산 사용량 정보를 포함하는 GeminiAgent 인스턴스

    Returns:
        예산 사용량 정보가 설정된 Rich Panel 객체
    """
    usage_fn = getattr(agent, "get_budget_usage_percent", None)
    usage = usage_fn() if callable(usage_fn) else 0.0
    content = f"Budget usage: {usage:.2f}%"
    return Panel(content, title=PANEL_TITLE_BUDGET, border_style="red")


def display_queries(queries: List[str]) -> None:
    """생성된 질의 리스트를 Rich Panel로 콘솔에 출력합니다.

    Args:
        queries: 출력할 질의 문자열 리스트
    """
    console.print(
        Panel(
            "\n".join([f"{i + 1}. {q}" for i, q in enumerate(queries)]),
            title=PANEL_TITLE_QUERIES,
            border_style="green",
        )
    )
