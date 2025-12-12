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


class AppConfig(BaseSettings):
    """애플리케이션 설정 관리.

    환경 변수(.env)를 통해 모든 설정을 주입받으며,
    Pydantic을 사용한 엄격한 타입 검증을 수행합니다.

    주요 설정:
    - API 키 검증 (길이 제한, AIza 시작)
    - 동시성 제한 (1-20)
    - 타임아웃 (30-600초)
    - 캐시 TTL (1-1440분)

    Raises:
        ValueError: 설정값이 유효하지 않은 경우
    """

    api_key: str = Field(..., alias="GEMINI_API_KEY")
    model_name: Literal["gemini-flash-latest"] = Field(
        "gemini-flash-latest",
        alias="GEMINI_MODEL_NAME",
    )
    max_output_tokens: int = Field(4096, alias="GEMINI_MAX_OUTPUT_TOKENS")
    # Per-query-type token overrides (optional). If unset, fall back to
    # GEMINI_MAX_OUTPUT_TOKENS with conservative defaults for faster responses.
    max_output_tokens_explanation: int | None = Field(
        None,
        alias="GEMINI_MAX_OUTPUT_TOKENS_EXPLANATION",
    )
    max_output_tokens_reasoning: int | None = Field(
        None,
        alias="GEMINI_MAX_OUTPUT_TOKENS_REASONING",
    )
    max_output_tokens_target: int | None = Field(
        None,
        alias="GEMINI_MAX_OUTPUT_TOKENS_TARGET",
    )
    timeout: int = Field(120, alias="GEMINI_TIMEOUT")
    timeout_max: int = Field(3600, alias="GEMINI_TIMEOUT_MAX")
    max_concurrency: int = Field(10, alias="GEMINI_MAX_CONCURRENCY")
    cache_size: int = Field(50, alias="GEMINI_CACHE_SIZE")
    temperature: float = Field(0.2, alias="GEMINI_TEMPERATURE")
    cache_ttl_minutes: int = Field(360, alias="GEMINI_CACHE_TTL_MINUTES")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    cache_stats_file: str = Field("cache_stats.jsonl", alias="CACHE_STATS_FILE")
    cache_stats_max_entries: int = Field(100, alias="CACHE_STATS_MAX_ENTRIES")
    local_cache_dir: str = Field(".cache", alias="LOCAL_CACHE_DIR")
    budget_limit_usd: float | None = Field(None, alias="BUDGET_LIMIT_USD")
    cache_min_tokens: int = Field(MIN_CACHE_TOKENS, alias="GEMINI_CACHE_MIN_TOKENS")
    # Standardized API response toggle
    enable_standard_response: bool = Field(False, alias="ENABLE_STANDARD_RESPONSE")
    # Timeout overrides (environment can override; defaults keep backward compatibility)
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

    # RAG Configuration
    enable_rag: bool = Field(False, alias="ENABLE_RAG")

    # Provider Configuration
    llm_provider_type: str = Field(
        "gemini",
        description="LLM provider type (gemini, etc.)",
    )
    graph_provider_type: str = Field(
        "neo4j",
        description="Graph provider type (neo4j, etc.)",
    )
    neo4j_uri: str | None = Field(None, alias="NEO4J_URI")
    neo4j_user: str | None = Field(None, alias="NEO4J_USER")
    neo4j_password: str | None = Field(None, alias="NEO4J_PASSWORD")
    enable_lats: bool = Field(False, alias="ENABLE_LATS")

    # Data2Neo Configuration
    enable_data2neo: bool = Field(False, alias="ENABLE_DATA2NEO")
    data2neo_batch_size: int = Field(100, alias="DATA2NEO_BATCH_SIZE")
    data2neo_confidence: float = Field(0.7, alias="DATA2NEO_CONFIDENCE_THRESHOLD")

    # Async Queue Configuration
    redis_url: str = Field(
        "redis://localhost:6379",
        alias="REDIS_URL",
        description="Redis URL for FastStream",
    )

    # CORS Configuration
    cors_allow_origins: list[str] = Field(
        default=["http://127.0.0.1:8000", "http://localhost:8000"],
        alias="CORS_ALLOW_ORIGINS",
        description="Comma-separated list of allowed CORS origins",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def __init__(self, **data: Any) -> None:
        """Initialize AppConfig from environment variables or provided data."""
        super().__init__(**data)

    def resolve_max_output_tokens(self, query_type: str | None = None) -> int:
        """qtype에 맞는 max_output_tokens를 반환한다.

        - 환경 변수 override가 있으면 최우선 적용
        - 없으면 GEMINI_MAX_OUTPUT_TOKENS를 기준으로 보수적인 기본값을 적용해
          짧은 타입(target/reasoning) 응답 속도를 개선한다.
        """
        if not query_type:
            return self.max_output_tokens

        normalized = query_type
        if normalized in {"global_explanation", "globalexplanation"}:
            normalized = "explanation"
        if normalized in {"target_short", "target_long"}:
            normalized = "target"

        if normalized == "explanation":
            return (
                self.max_output_tokens_explanation
                if self.max_output_tokens_explanation is not None
                else self.max_output_tokens
            )

        if normalized == "reasoning":
            if self.max_output_tokens_reasoning is not None:
                return self.max_output_tokens_reasoning
            return min(self.max_output_tokens, 2048)

        if normalized == "target":
            if self.max_output_tokens_target is not None:
                return self.max_output_tokens_target
            return min(self.max_output_tokens, 512)

        return self.max_output_tokens

    @model_validator(mode="after")
    def check_timeout_consistency(self) -> "AppConfig":
        """Timeout <= timeout_max 확인."""
        if self.timeout > self.timeout_max:
            raise ValueError(
                f"timeout ({self.timeout}s) must be <= timeout_max ({self.timeout_max}s)",
            )
        return self

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

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate Gemini API key format with detailed error messages.

        Args:
            v (str): API 키 문자열.

        Returns:
            str: 검증된 API 키.

        Raises:
            ValueError: 키가 비어있거나, 'AIza'로 시작하지 않거나,
                길이가 39자가 아니거나, 형식이 잘못된 경우.

        Examples:
            >>> AppConfig.validate_api_key("AIzaSyABC123...")
            'AIzaSyABC123...'
        """
        # 1️⃣ 필수 확인
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

        # 2️⃣ 길이 확인
        if len(v) != GEMINI_API_KEY_LENGTH:
            raise ValueError(
                f"❌ API key length is {len(v)}, expected {GEMINI_API_KEY_LENGTH}.\n"
                f"   Your key: {v[:10]}...{v[-4:]}\n"
                f"   Check if copied correctly from https://aistudio.google.com/app/apikey",
            )

        # 3️⃣ 형식 확인
        if not v.startswith("AIza"):
            raise ValueError(
                f"❌ API key must start with 'AIza', got '{v[:10]}...'\n"
                f"   Make sure you copied the full key",
            )

        # 4️⃣ 정규식 확인
        # Google API 키 형식: AIza + 35개의 안전 문자 (총 GEMINI_API_KEY_LENGTH자)
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
        "max_output_tokens_target",
    )
    @classmethod
    def validate_max_output_tokens(cls, v: int | None) -> int | None:
        if v is None:
            return v
        if v < 1:
            raise ValueError("max_output_tokens must be >= 1")
        return v

    @field_validator("max_concurrency")
    @classmethod
    def validate_concurrency(cls, v: int) -> int:
        """Validate concurrency is within allowed range.

        Args:
            v (int): 동시성 제한 값.

        Returns:
            int: 검증된 동시성 값 (1-100 범위).

        Raises:
            ValueError: 값이 1-100 범위를 벗어난 경우.
        """
        if not 1 <= v <= 100:
            raise ValueError(f"Concurrency must be between 1 and 100, got {v}")

        # 경고: 높은 동시성은 Rate Limit 위험
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
        """Validate timeout is within allowed range.

        Args:
            v (int): 타임아웃 값 (초).

        Returns:
            int: 검증된 타임아웃 값 (30-3600초 범위).

        Raises:
            ValueError: 값이 30-3600초 범위를 벗어난 경우.
        """
        if not 30 <= v <= 3600:
            raise ValueError(f"Timeout must be between 30 and 3600 seconds, got {v}")
        return v

    @field_validator("timeout_max")
    @classmethod
    def validate_timeout_max(cls, v: int) -> int:
        """Validate timeout_max is at least 30 seconds.

        Args:
            v (int): 최대 타임아웃 값 (초).

        Returns:
            int: 검증된 최대 타임아웃 값.

        Raises:
            ValueError: 값이 30초 미만인 경우.
        """
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
        """Validate cache TTL is within allowed range.

        Args:
            v (int): 캐시 TTL (분).

        Returns:
            int: 검증된 캐시 TTL (1-10080분 범위).

        Raises:
            ValueError: 값이 1-10080분 범위를 벗어난 경우.
        """
        if not 1 <= v <= 10080:  # 1분 ~ 7일 (10080 = 7 * 24 * 60)
            raise ValueError(
                f"Cache TTL must be between 1 and 10080 minutes (7 days), got {v}",
            )

        # 경고: 7일 이상은 실용적이지 않음
        if v > 7200:  # 5일 이상
            logger.warning(
                "Very long cache TTL (%d minutes) may not be practical for learning projects.",
                v,
            )

        return v

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

    @field_validator("budget_limit_usd")
    @classmethod
    def validate_budget(cls, v: float | None) -> float | None:
        """Validate budget limit is positive if set."""
        if v is None:
            return v
        if v <= 0:
            raise ValueError(ERROR_MESSAGES["budget_positive"])
        # Normalize to cents precision to avoid unstable comparisons downstream.
        return round(float(v), 2)

    @field_validator("cache_stats_max_entries")
    @classmethod
    def validate_cache_stats_max_entries(cls, v: int) -> int:
        """Validate cache stats max entries is at least 1."""
        if v < 1:
            raise ValueError(ERROR_MESSAGES["cache_stats_min_entries"])
        return v

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
