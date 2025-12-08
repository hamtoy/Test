"""Shared constants for pricing, validation, and operational defaults."""

from typing import Final, TypedDict


class PricingTier(TypedDict):
    """Pricing tier configuration for token-based billing."""

    max_input_tokens: int | None
    input_rate: float
    output_rate: float


# Pricing per 1M tokens (USD) for Gemini models.
# Ordered tiers: first match wins.
PRICING_TIERS: Final[dict[str, list[PricingTier]]] = {
    # Default model
    "gemini-flash-latest": [
        # Pricing per 1M tokens, all context lengths (see latest Gemini pricing)
        {"max_input_tokens": None, "input_rate": 0.30, "output_rate": 2.50},
    ],
    # Backward compatibility
    "gemini-3-pro-preview": [
        {"max_input_tokens": None, "input_rate": 0.30, "output_rate": 2.50},
    ],
}

GEMINI_API_KEY_LENGTH: Final[int] = 39
DEFAULT_RPM_LIMIT: Final[int] = 60
DEFAULT_RPM_WINDOW_SECONDS: Final[int] = 60


# ===== Token and Output Configuration =====

# Default max output tokens for LLM generation
DEFAULT_MAX_OUTPUT_TOKENS: Final[int] = 2048

# Max output tokens for settings (GEMINI_MAX_OUTPUT_TOKENS env var default)
DEFAULT_SETTINGS_MAX_OUTPUT_TOKENS: Final[int] = 8192

# Max output tokens for quick operations (e.g., LATS expansion)
LATS_EXPANSION_MAX_OUTPUT_TOKENS: Final[int] = 50

# 서식 규칙: 줄글 볼드 패턴 및 허용 컨텍스트
PROSE_BOLD_PATTERN: Final[str] = r"(?<!^)(?<!- )(?<!\d\. )\*\*[^*]+\*\*"
ALLOWED_BOLD_CONTEXTS: Final[list[str]] = [
    r"^-\s+\*\*",  # 목록 항목 시작
    r"^\d+\.\s+\*\*",  # 숫자 목록 항목 시작
    r"^\*\*[^*]+\*\*$",  # 소제목 (줄 전체 볼드)
    r"^\*\*[^*]+\*\*\s*$",  # 소제목 (끝 공백 포함)
]

# ===== API Pipeline Configuration =====

# Max characters for OCR text truncation in QA generation
QA_GENERATION_OCR_TRUNCATE_LENGTH: Final[int] = 3000
# Phase 2B: Cache key OCR truncation length (same as generation for consistency)
QA_CACHE_OCR_TRUNCATE_LENGTH: Final[int] = 3000
# Phase 2B: Estimated time saved per cache hit (seconds) - used for metrics
ESTIMATED_CACHE_HIT_TIME_SAVINGS: Final[int] = 9  # Average of 6-12s range


# QA generation timeout settings (seconds)
QA_SINGLE_GENERATION_TIMEOUT: Final[int] = 60
QA_BATCH_GENERATION_TIMEOUT: Final[int] = 120
# QA batch generation order (first sequential, rest parallel)
QA_BATCH_TYPES: Final[list[str]] = [
    "global_explanation",
    "reasoning",
    "target_short",
    "target_long",
]
# Optional 3-type batch (global_explanation, reasoning, target_short)
QA_BATCH_TYPES_THREE: Final[list[str]] = [
    "global_explanation",
    "reasoning",
    "target_short",
]

# Workspace generation timeout settings (seconds)
WORKSPACE_GENERATION_TIMEOUT: Final[int] = 90
WORKSPACE_UNIFIED_TIMEOUT: Final[int] = 90


# ===== Cache TTL Configuration (seconds) =====

# Default TTL for cache entries (4 hours - optimized for better hit rate)
DEFAULT_CACHE_TTL_SECONDS: Final[int] = 14400

# TTL for system prompts (1 hour - rarely changes)
SYSTEM_PROMPT_TTL_SECONDS: Final[int] = 3600

# TTL for rules cache (1 hour)
RULES_CACHE_TTL_SECONDS: Final[int] = 3600

# Max wait time for batch processing (1 hour)
BATCH_MAX_WAIT_SECONDS: Final[float] = 3600.0


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


# ===== Default Answer Rules =====

# Default rules applied when Neo4j is unavailable
DEFAULT_ANSWER_RULES: Final[list[str]] = [
    "표나 그래프를 직접 언급하지 마세요",
    "고유명사와 숫자는 원문 그대로 유지하세요",
    "추측성 표현(~인 것 같다, ~로 보인다)을 피하세요",
    "OCR 텍스트에 없는 정보를 추가하지 마세요",
]

# Default forbidden patterns for answer validation
DEFAULT_FORBIDDEN_PATTERNS: Final[list[str]] = [
    r"표\s*\d+",
    r"그래프|차트|도표",
    r"위\s*그림|아래\s*표",
]
