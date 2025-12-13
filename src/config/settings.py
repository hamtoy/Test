"""Application Configuration Settings.

Pydantic-based configuration management with environment variable loading
and comprehensive validation for the Gemini QA system.
"""

# mypy: disable-error-code=misc
import logging
import os
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config.constants import (
    ERROR_MESSAGES,
    GEMINI_API_KEY_LENGTH,
    MIN_CACHE_TOKENS,
    QA_BATCH_GENERATION_TIMEOUT,
    QA_SINGLE_GENERATION_TIMEOUT,
    WORKSPACE_GENERATION_TIMEOUT,
    WORKSPACE_UNIFIED_TIMEOUT,
    CacheConfig,
)

logger = logging.getLogger(__name__)


class LLMSettingsMixin(BaseSettings):
    """LLM-related configuration settings (Mixin).

    Handles API keys, model selection, tokens, timeouts, concurrency,
    temperature, caching, and budget management.
    """

    api_key: str = Field(..., alias="GEMINI_API_KEY")
    model_name: Literal["gemini-flash-latest"] = Field(
        "gemini-flash-latest",
        alias="GEMINI_MODEL_NAME",
    )
    max_output_tokens: int = Field(4096, alias="GEMINI_MAX_OUTPUT_TOKENS")
    max_output_tokens_explanation: int | None = Field(
        3072,
        alias="GEMINI_MAX_OUTPUT_TOKENS_EXPLANATION",
    )
    max_output_tokens_reasoning: int | None = Field(
        1536,
        alias="GEMINI_MAX_OUTPUT_TOKENS_REASONING",
    )
    max_output_tokens_target_short: int | None = Field(
        256,
        alias="GEMINI_MAX_OUTPUT_TOKENS_TARGET_SHORT",
    )
    max_output_tokens_target_long: int | None = Field(
        1024,
        alias="GEMINI_MAX_OUTPUT_TOKENS_TARGET_LONG",
    )
    timeout: int = Field(120, alias="GEMINI_TIMEOUT")
    timeout_max: int = Field(3600, alias="GEMINI_TIMEOUT_MAX")
    max_concurrency: int = Field(10, alias="GEMINI_MAX_CONCURRENCY")
    cache_size: int = Field(50, alias="GEMINI_CACHE_SIZE")
    temperature: float = Field(0.2, alias="GEMINI_TEMPERATURE")
    cache_ttl_minutes: int = Field(360, alias="GEMINI_CACHE_TTL_MINUTES")
    cache_min_tokens: int = Field(MIN_CACHE_TOKENS, alias="GEMINI_CACHE_MIN_TOKENS")
    budget_limit_usd: float | None = Field(None, alias="BUDGET_LIMIT_USD")

    @model_validator(mode="after")
    def check_timeout_consistency(self) -> "LLMSettingsMixin":
        """Timeout <= timeout_max 확인."""
        if self.timeout > self.timeout_max:
            raise ValueError(
                f"timeout ({self.timeout}s) must be <= timeout_max ({self.timeout_max}s)",
            )
        return self

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate Gemini API key format with detailed error messages."""
        if not v:
            raise ValueError(
                "❌ GEMINI_API_KEY is required.\n"
                "   Get one at: https://aistudio.google.com/app/apikey\n"
                "   Set in .env: GEMINI_API_KEY=AIza...",
            )

        if v == "your_api_key_here":
            raise ValueError(
                "❌ GEMINI_API_KEY is a placeholder. "
                "Replace with actual key from https://aistudio.google.com",
            )

        if len(v) != GEMINI_API_KEY_LENGTH:
            raise ValueError(
                f"❌ API key length is {len(v)}, expected {GEMINI_API_KEY_LENGTH}.\n"
                f"   Your key: {v[:10]}...{v[-4:]}\n"
                f"   Check if copied correctly from https://aistudio.google.com/app/apikey",
            )

        if not v.startswith("AIza"):
            raise ValueError(
                f"❌ API key must start with 'AIza', got '{v[:10]}...'\n"
                f"   Make sure you copied the full key",
            )

        if not re.match(r"^AIza[0-9A-Za-z_\-]{35}$", v):
            raise ValueError(
                f"❌ API key format invalid. Key contains invalid characters.\n"
                f"   Valid chars: A-Z, a-z, 0-9, _, -\n"
                f"   Your key: {v[:10]}...{v[-4:]}",
            )

        logger.debug("API key validated successfully")
        return v

    @field_validator("model_name")
    @classmethod
    def enforce_single_model(cls, v: str) -> str:
        """Enforce use of the supported Gemini model only."""
        if v != "gemini-flash-latest":
            raise ValueError(
                "Unsupported model. This system only allows 'gemini-flash-latest'.",
            )
        return v

    @field_validator(
        "max_output_tokens",
        "max_output_tokens_explanation",
        "max_output_tokens_reasoning",
        "max_output_tokens_target_short",
        "max_output_tokens_target_long",
    )
    @classmethod
    def validate_max_output_tokens(cls, v: int | None) -> int | None:
        if v is None:
            return None
        if v < 1:
            raise ValueError("max_output_tokens must be >= 1")
        return v

    @field_validator("max_concurrency")
    @classmethod
    def validate_concurrency(cls, v: int) -> int:
        """Validate concurrency is within allowed range."""
        if not 1 <= v <= 100:
            raise ValueError(f"Concurrency must be between 1 and 100, got {v}")

        if v > 20:
            logger.warning(
                "High concurrency (%d) may trigger rate limiting. "
                "Consider increasing GEMINI_MAX_CONCURRENCY or reducing batch size.",
                v,
            )

        return v

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate timeout is within allowed range."""
        if not 30 <= v <= 3600:
            raise ValueError(f"Timeout must be between 30 and 3600 seconds, got {v}")
        return v

    @field_validator("timeout_max")
    @classmethod
    def validate_timeout_max(cls, v: int) -> int:
        """Validate timeout_max is at least 30 seconds."""
        if v < 30:
            raise ValueError("Timeout max must be at least 30 seconds")
        return v

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature is within allowed range."""
        if not 0.0 <= v <= 2.0:
            raise ValueError(ERROR_MESSAGES["temperature_range"])
        return v

    @field_validator("cache_ttl_minutes")
    @classmethod
    def validate_cache_ttl(cls, v: int) -> int:
        """Validate cache TTL is within allowed range."""
        if not 1 <= v <= 10080:
            raise ValueError(
                f"Cache TTL must be between 1 and 10080 minutes (7 days), got {v}",
            )

        if v > 7200:
            logger.warning(
                "Very long cache TTL (%d minutes) may not be practical for learning projects.",
                v,
            )

        return v

    @field_validator("budget_limit_usd")
    @classmethod
    def validate_budget(cls, v: float | None) -> float | None:
        """Validate budget limit is positive if set."""
        if v is None:
            return v
        if v <= 0:
            raise ValueError(ERROR_MESSAGES["budget_positive"])
        return round(float(v), 2)

    @field_validator("cache_min_tokens")
    @classmethod
    def validate_cache_min_tokens(cls, v: int) -> int:
        """Gemini Context Caching API는 2048 토큰 미만을 지원하지 않습니다."""
        api_min = CacheConfig.MIN_TOKENS_FOR_CACHING

        if v < api_min:
            logger.warning(
                "CACHE_MIN_TOKENS=%d는 Gemini API 제약(%d)보다 작습니다. "
                "캐싱이 작동하지 않을 수 있습니다. %d로 자동 조정합니다.",
                v,
                api_min,
                api_min,
            )
            return api_min

        if v > api_min:
            logger.info(
                "CACHE_MIN_TOKENS=%d로 설정됨. "
                "API 최소값(%d)보다 높으므로 일부 요청에서 캐싱이 건너뛰어질 수 있습니다.",
                v,
                api_min,
            )

        return v


class DatabaseSettingsMixin(BaseSettings):
    """Database configuration settings (Mixin).

    Handles Neo4j (graph database) and Redis (message queue) configuration.
    """

    neo4j_uri: str | None = Field(None, alias="NEO4J_URI")
    neo4j_user: str | None = Field(None, alias="NEO4J_USER")
    neo4j_password: str | None = Field(None, alias="NEO4J_PASSWORD")
    redis_url: str = Field(
        "redis://localhost:6379",
        alias="REDIS_URL",
        description="Redis URL for FastStream",
    )


class WebSettingsMixin(BaseSettings):
    """Web API configuration settings (Mixin).

    Handles CORS, timeouts, and response formatting.
    """

    cors_allow_origins: list[str] = Field(
        default=["http://127.0.0.1:8000", "http://localhost:8000"],
        alias="CORS_ALLOW_ORIGINS",
        description="Comma-separated list of allowed CORS origins",
    )
    enable_standard_response: bool = Field(False, alias="ENABLE_STANDARD_RESPONSE")
    qa_single_timeout: int = Field(
        QA_SINGLE_GENERATION_TIMEOUT,
        alias="QA_SINGLE_TIMEOUT",
    )
    qa_batch_timeout: int = Field(QA_BATCH_GENERATION_TIMEOUT, alias="QA_BATCH_TIMEOUT")
    workspace_timeout: int = Field(
        WORKSPACE_GENERATION_TIMEOUT,
        alias="WORKSPACE_TIMEOUT",
    )
    workspace_unified_timeout: int = Field(
        WORKSPACE_UNIFIED_TIMEOUT,
        alias="WORKSPACE_UNIFIED_TIMEOUT",
    )


class FeatureSettingsMixin(BaseSettings):
    """Feature flags and optional functionality (Mixin).

    Handles RAG, LATS, Data2Neo, and provider selection.
    """

    enable_rag: bool = Field(False, alias="ENABLE_RAG")
    enable_lats: bool = Field(False, alias="ENABLE_LATS")
    enable_data2neo: bool = Field(False, alias="ENABLE_DATA2NEO")
    llm_provider_type: str = Field(
        "gemini",
        description="LLM provider type (gemini, etc.)",
    )
    graph_provider_type: str = Field(
        "neo4j",
        description="Graph provider type (neo4j, etc.)",
    )
    data2neo_batch_size: int = Field(100, alias="DATA2NEO_BATCH_SIZE")
    data2neo_confidence: float = Field(0.7, alias="DATA2NEO_CONFIDENCE_THRESHOLD")


class AppConfig(
    LLMSettingsMixin,
    DatabaseSettingsMixin,
    WebSettingsMixin,
    FeatureSettingsMixin,
    BaseSettings,
):
    """애플리케이션 설정 관리 (Composed from Mixins).

    환경 변수(.env)를 통해 모든 설정을 주입받으며,
    Pydantic을 사용한 엄격한 타입 검증을 수행합니다.

    설정은 다음 Mixin들로 구성됩니다:
    - LLMSettingsMixin: API 키, 모델, 토큰, 타임아웃, 온도, 캐싱, 예산
    - DatabaseSettingsMixin: Neo4j, Redis 설정
    - WebSettingsMixin: CORS, API 타임아웃
    - FeatureSettingsMixin: RAG, LATS, Data2Neo 플래그

    추가 설정:
    - log_level: 로깅 레벨
    - cache_stats_file: 캐시 통계 파일 경로
    - cache_stats_max_entries: 캐시 통계 최대 항목 수
    - local_cache_dir: 로컬 캐시 디렉토리

    Raises:
        ValueError: 설정값이 유효하지 않은 경우
    """

    # General settings (not in mixins)
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    cache_stats_file: str = Field("cache_stats.jsonl", alias="CACHE_STATS_FILE")
    cache_stats_max_entries: int = Field(100, alias="CACHE_STATS_MAX_ENTRIES")
    local_cache_dir: str = Field(".cache", alias="LOCAL_CACHE_DIR")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def __init__(self, **data: Any) -> None:
        """Initialize AppConfig from environment variables or provided data."""
        super().__init__(**data)

    def resolve_max_output_tokens(self, query_type: str | None = None) -> int:
        """qtype에 맞는 max_output_tokens를 반환한다."""
        base = self._get_base_max_output_tokens()

        if not query_type:
            return base

        normalized = self._normalize_query_type(query_type)
        return self._get_tokens_for_type(normalized, base)

    def _get_base_max_output_tokens(self) -> int:
        """기본 max_output_tokens 반환 (검증 포함)."""
        if self.max_output_tokens <= 0:
            logger.warning(
                "Invalid GEMINI_MAX_OUTPUT_TOKENS=%s; falling back to 4096",
                self.max_output_tokens,
            )
            return 4096
        return self.max_output_tokens

    def _normalize_query_type(self, query_type: str) -> str:
        """query_type을 정규화된 형태로 변환."""
        if query_type in {"global_explanation", "globalexplanation"}:
            return "explanation"
        # target_short, target_long은 분리하여 처리
        return query_type

    def _get_tokens_for_type(self, normalized: str, base: int) -> int:
        """타입별 토큰 설정 반환."""
        config_map = {
            "explanation": (self.max_output_tokens_explanation, base),
            "reasoning": (self.max_output_tokens_reasoning, min(base, 2048)),
            "target_short": (self.max_output_tokens_target_short, min(base, 512)),
            "target_long": (self.max_output_tokens_target_long, min(base, 2048)),
        }

        if normalized not in config_map:
            return base

        override, default = config_map[normalized]
        if override is not None and override > 0:
            return override
        if override is not None and override <= 0:
            logger.warning(
                "Invalid GEMINI_MAX_OUTPUT_TOKENS_%s=%s; ignoring",
                normalized.upper(),
                override,
            )
        return default

    @model_validator(mode="after")
    def check_rag_dependencies(self) -> "AppConfig":
        """RAG 기능 활성화 시 Neo4j 설정 확인.

        Validation rules:
        1. enable_rag=True requires all Neo4j fields (uri, user, password)
        2. Any Neo4j field set without enable_rag triggers a warning but is allowed
           (the field might be set for other purposes)
        3. neo4j_uri set implies all other Neo4j fields are required
        """
        # Case 1: ENABLE_RAG is explicitly True - require all Neo4j fields
        if self.enable_rag:
            required_fields = ["neo4j_uri", "neo4j_user", "neo4j_password"]
            missing = [f for f in required_fields if not getattr(self, f, None)]
            if missing:
                raise ValueError(
                    "NEO4J_URI 설정 시 필수: {fields}\n"
                    "ENABLE_RAG=True 설정 시 필수: {fields}\n"
                    "또는 ENABLE_RAG=false로 설정하세요".format(
                        fields=", ".join(missing),
                    ),
                )

        # Case 2: neo4j_uri is set (without enable_rag=True) - still require other Neo4j fields
        # This handles cases where user sets NEO4J_URI without ENABLE_RAG
        elif self.neo4j_uri:
            required_fields = ["neo4j_user", "neo4j_password"]
            missing = [f for f in required_fields if not getattr(self, f, None)]
            if missing:
                raise ValueError(
                    f"NEO4J_URI 설정 시 필수: {', '.join(missing)}\n"
                    f"또는 .env에서 NEO4J_URI를 제거하세요",
                )

        return self

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is a recognized level."""
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(
                ERROR_MESSAGES["log_level_invalid"].format(allowed=allowed),
            )
        return upper

    @field_validator("cache_stats_max_entries")
    @classmethod
    def validate_cache_stats_max_entries(cls, v: int) -> int:
        """Validate cache stats max entries is at least 1."""
        if v < 1:
            raise ValueError(ERROR_MESSAGES["cache_stats_min_entries"])
        return v

    def model_post_init(self, __context: Any) -> None:
        """Ensure required directories exist after settings load."""
        self._ensure_directories()

    @staticmethod
    def _detect_project_root() -> Path:
        """Detect the project root by checking several hints.

        1. PROJECT_ROOT env var (highest priority)
        2. The nearest directory containing `.git`, `templates`, or `data`
        3. Fallback to the parent of this file (legacy behavior)
        """
        project_root_env = os.getenv("PROJECT_ROOT")
        if project_root_env:
            return Path(project_root_env)

        current = Path(__file__).resolve().parent
        markers = {".git", "templates", "data"}

        for parent in [current, *current.parents]:
            if any((parent / marker).exists() for marker in markers):
                return parent

        return Path(__file__).parent.parent

    @property
    def base_dir(self) -> Path:
        """프로젝트 루트 디렉토리 반환."""
        return self._detect_project_root()

    @property
    def template_dir(self) -> Path:
        """Jinja2 템플릿 디렉토리 반환."""
        return self.base_dir / "templates"

    @property
    def input_dir(self) -> Path:
        """입력 데이터 디렉토리 반환."""
        return self.base_dir / "data" / "inputs"

    @property
    def output_dir(self) -> Path:
        """출력 데이터 디렉토리 반환."""
        return self.base_dir / "data" / "outputs"

    def _ensure_directories(self) -> None:
        """Create required directories if missing."""
        required_dirs = [
            self.input_dir,
            self.output_dir,
            self.template_dir,
        ]
        for dir_path in required_dirs:
            dir_path.mkdir(parents=True, exist_ok=True)

    @property
    def cache_stats_path(self) -> Path:
        """Cache stats file path resolved relative to project root if needed."""
        path = Path(self.cache_stats_file)
        if not path.is_absolute():
            path = self.base_dir / path
        return path
