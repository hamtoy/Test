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

ERROR_MESSAGES: Final[dict[str, str]] = {
    "api_key_missing": "GEMINI_API_KEY is not set. Please check your .env file.",
    "api_key_prefix": (
        "GEMINI_API_KEY validation failed:\n"
        "  - Must start with 'AIza'\n"
        "  - See: https://makersuite.google.com/app/apikey"
    ),
    "api_key_length": (
        "GEMINI_API_KEY validation failed:\n"
        "  - Got {got} characters\n"
        "  - Must be exactly {length} characters (starts with 'AIza')\n"
        "  - See: https://makersuite.google.com/app/apikey"
    ),
    "api_key_format": (
        "GEMINI_API_KEY validation failed:\n"
        "  - Invalid format (expected 'AIza' + 35 safe chars)\n"
        "  - See: https://makersuite.google.com/app/apikey"
    ),
    "concurrency_range": "max_concurrency must be between 1 and 20",
    "timeout_range": "timeout must be between 30 and 600 seconds",
    "temperature_range": "temperature must be between 0.0 and 2.0",
    "cache_ttl_range": "cache_ttl_minutes must be between 1 and 1440",
    "log_level_invalid": "log_level must be one of {allowed}",
    "budget_positive": "budget_limit_usd must be positive when set",
    "cache_stats_min_entries": "cache_stats_max_entries must be >= 1",
}

# Pattern for masking sensitive API keys in logs (e.g., Google API keys).
SENSITIVE_PATTERN: Final[str] = r"AIza[0-9A-Za-z_-]{35}"
