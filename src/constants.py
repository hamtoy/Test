"""
Shared constants for pricing, validation, and operational defaults.
"""

from typing import Final, List, Optional, TypedDict


class PricingTier(TypedDict):
    max_input_tokens: Optional[int]
    input_rate: float
    output_rate: float


# Pricing per 1M tokens (USD) for Gemini models.
# Ordered tiers: first match wins.
PRICING_TIERS: Final[dict[str, List[PricingTier]]] = {
    "gemini-3-pro-preview": [
        {"max_input_tokens": 200_000, "input_rate": 2.00, "output_rate": 12.00},
        {"max_input_tokens": None, "input_rate": 4.00, "output_rate": 18.00},
    ],
}

GEMINI_API_KEY_LENGTH: Final[int] = 39
DEFAULT_RPM_LIMIT: Final[int] = 60
DEFAULT_RPM_WINDOW_SECONDS: Final[int] = 60
MIN_CACHE_TOKENS: Final[int] = 2048
BUDGET_WARNING_THRESHOLDS: Final[list[tuple[int, str]]] = [
    (80, "WARNING"),
    (90, "HIGH"),
    (95, "CRITICAL"),
]
PANEL_TITLE_QUERIES: Final[str] = "[bold green]Generated Strategic Queries[/bold green]"
PANEL_TITLE_BUDGET: Final[str] = "Budget Exceeded"
PANEL_TITLE_COST: Final[str] = "[bold blue]Cost Summary[/bold blue]"
PROMPT_EDIT_CANDIDATES: Final[str] = (
    "위 질의를 보고 후보 답변 파일(input_candidates.json)을 수정하시겠습니까? (수정 후 Enter)"
)
COST_PANEL_TEMPLATE: Final[str] = (
    "[bold cyan]💰 Total Session Cost:[/bold cyan] ${cost:.4f} USD\n"
    "[bold green]📊 Token Usage:[/bold green] {input_tokens:,} input / {output_tokens:,} output\n"
    "[bold magenta]🚀 Cache Stats:[/bold magenta] {cache_hits} hits / {cache_misses} misses"
)
PROGRESS_WAITING_TEMPLATE: Final[str] = "[cyan]Turn {turn_id}: Waiting...[/cyan]"
PROGRESS_DONE_TEMPLATE: Final[str] = "[green]Turn {turn_id}: Done[/green]"
PROGRESS_RESTORED_TEMPLATE: Final[str] = "[green]Turn {turn_id}: Restored[/green]"
PROGRESS_PROCESSING_TEMPLATE: Final[str] = "[cyan]Turn {turn_id}: Processing...[/cyan]"
PROGRESS_FAILED_TEMPLATE: Final[str] = "[red]Turn {turn_id}: Failed[/red]"
PANEL_TURN_TITLE_TEMPLATE: Final[str] = "Turn {turn_id} Result"

# Pattern for masking sensitive API keys in logs (e.g., Google API keys).
SENSITIVE_PATTERN: Final[str] = r"AIza[0-9A-Za-z_-]{35}"
