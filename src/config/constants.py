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


class CacheConfig:
    """Context Caching 설정.

    Gemini API의 Context Caching 기능에 대한 설정 및 제약사항을 정의합니다.

    References:
        https://ai.google.dev/gemini-api/docs/caching
    """

    # Gemini API 제약: 2048 토큰 미만은 캐싱 불가
    MIN_TOKENS_FOR_CACHING: Final[int] = 2048

    MIN_TOKENS_RATIONALE: Final[str] = """
    2048 토큰은 Gemini Context Caching API의 최소 임계값입니다.
    이는 비용 절감의 breakeven point가 아니라, API의 기술적 제약사항입니다.

    - 2048 토큰 이상: 캐싱 API 사용 가능
    - 2048 토큰 미만: 일반 API로 자동 fallback

    이 값은 변경할 수 없습니다 (Google이 정한 제약).
    """


# Backward compatibility: keep MIN_CACHE_TOKENS as alias
MIN_CACHE_TOKENS: Final[int] = CacheConfig.MIN_TOKENS_FOR_CACHING
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
PANEL_TURN_BODY_TEMPLATE: Final[str] = (
    "[bold]Query:[/bold] {query}\n\n"
    "[bold]Best Candidate:[/bold] {best_candidate}\n"
    "[bold]Rewritten:[/bold] {rewritten}..."
)
USER_INTERRUPT_MESSAGE: Final[str] = "\n[bold red][!] 사용자 중단[/bold red]"
LOG_MESSAGES: Final[dict[str, str]] = {
    "budget_exceeded": "Budget limit exceeded: {error}",
    "reload_failed": "데이터 재로딩 실패: {error}",
    "cache_skipped": "Context cache creation skipped: {error}",
    "workflow_failed": "Workflow Failed: {error}",
    "turn_exception": "Turn 실행 중 예외 발생: {error}",
}

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
