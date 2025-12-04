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
        "gemini-flash-latest", alias="GEMINI_MODEL_NAME"
    )
    max_output_tokens: int = Field(8192, alias="GEMINI_MAX_OUTPUT_TOKENS")
    timeout: int = Field(120, alias="GEMINI_TIMEOUT")
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
    # Timeout overrides (environment can override; defaults keep backward compatibility)
    qa_single_timeout: int = Field(
        QA_SINGLE_GENERATION_TIMEOUT, alias="QA_SINGLE_TIMEOUT"
    )
    qa_batch_timeout: int = Field(
        QA_BATCH_GENERATION_TIMEOUT, alias="QA_BATCH_TIMEOUT"
    )
    workspace_timeout: int = Field(
        WORKSPACE_GENERATION_TIMEOUT, alias="WORKSPACE_TIMEOUT"
    )
    workspace_unified_timeout: int = Field(
        WORKSPACE_UNIFIED_TIMEOUT, alias="WORKSPACE_UNIFIED_TIMEOUT"
    )

    # RAG Configuration
    enable_rag: bool = Field(False, alias="ENABLE_RAG")

    # Provider Configuration
    llm_provider_type: str = Field(
        "gemini", description="LLM provider type (gemini, etc.)"
    )
    graph_provider_type: str = Field(
        "neo4j", description="Graph provider type (neo4j, etc.)"
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def __init__(self, **data: Any) -> None:
        """Initialize AppConfig from environment variables or provided data."""
        super().__init__(**data)

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
                    f"ENABLE_RAG=True 설정 시 필수: {', '.join(missing)}\n"
                    f"또는 ENABLE_RAG=false로 설정하세요"
                )

        # Case 2: neo4j_uri is set (without enable_rag=True) - still require other Neo4j fields
        # This handles cases where user sets NEO4J_URI without ENABLE_RAG
        elif self.neo4j_uri:
            required_fields = ["neo4j_user", "neo4j_password"]
            missing = [f for f in required_fields if not getattr(self, f, None)]
            if missing:
                raise ValueError(
                    f"NEO4J_URI 설정 시 필수: {', '.join(missing)}\n"
                    f"또는 .env에서 NEO4J_URI를 제거하세요"
                )

        return self

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate Gemini API key format and structure.

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
        if not v or v == "your_api_key_here":
            raise ValueError(ERROR_MESSAGES["api_key_missing"])

        if not v.startswith("AIza"):
            raise ValueError(ERROR_MESSAGES["api_key_prefix"])

        if len(v) != GEMINI_API_KEY_LENGTH:
            raise ValueError(
                ERROR_MESSAGES["api_key_length"].format(
                    got=len(v), length=GEMINI_API_KEY_LENGTH
                )
            )

        # Google API 키 형식: AIza + 35개의 안전 문자 (총 GEMINI_API_KEY_LENGTH자)
        if not re.match(r"^AIza[0-9A-Za-z_\-]{35}$", v):
            raise ValueError(ERROR_MESSAGES["api_key_format"])
        return v

    @field_validator("model_name")
    @classmethod
    def enforce_single_model(cls, v: str) -> str:
        """Enforce use of the supported Gemini model only."""
        if v != "gemini-flash-latest":
            raise ValueError(
                "Unsupported model. This system only allows 'gemini-flash-latest'."
            )
        return v

    @field_validator("max_concurrency")
    @classmethod
    def validate_concurrency(cls, v: int) -> int:
        """Validate concurrency is within allowed range.

        Args:
            v (int): 동시성 제한 값.

        Returns:
            int: 검증된 동시성 값 (1-20 범위).

        Raises:
            ValueError: 값이 1-20 범위를 벗어난 경우.
        """
        if not 1 <= v <= 20:
            raise ValueError(ERROR_MESSAGES["concurrency_range"])
        return v

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate timeout is within allowed range.

        Args:
            v (int): 타임아웃 값 (초).

        Returns:
            int: 검증된 타임아웃 값 (30-600초 범위).

        Raises:
            ValueError: 값이 30-600초 범위를 벗어난 경우.
        """
        if not 30 <= v <= 600:
            raise ValueError(ERROR_MESSAGES["timeout_range"])
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
        if not 1 <= v <= 1440:
            raise ValueError(ERROR_MESSAGES["cache_ttl_range"])
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is a recognized level."""
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(
                ERROR_MESSAGES["log_level_invalid"].format(allowed=allowed)
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
        return v

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
