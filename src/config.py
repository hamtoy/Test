import os
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.constants import ERROR_MESSAGES, GEMINI_API_KEY_LENGTH, MIN_CACHE_TOKENS


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
    model_name: Literal["gemini-3-pro-preview"] = Field(
        "gemini-3-pro-preview", alias="GEMINI_MODEL_NAME"
    )
    max_output_tokens: int = Field(8192, alias="GEMINI_MAX_OUTPUT_TOKENS")
    timeout: int = Field(120, alias="GEMINI_TIMEOUT")
    max_concurrency: int = Field(5, alias="GEMINI_MAX_CONCURRENCY")
    cache_size: int = Field(50, alias="GEMINI_CACHE_SIZE")
    temperature: float = Field(0.2, alias="GEMINI_TEMPERATURE")
    cache_ttl_minutes: int = Field(10, alias="GEMINI_CACHE_TTL_MINUTES")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    cache_stats_file: str = Field("cache_stats.jsonl", alias="CACHE_STATS_FILE")
    cache_stats_max_entries: int = Field(100, alias="CACHE_STATS_MAX_ENTRIES")
    local_cache_dir: str = Field(".cache", alias="LOCAL_CACHE_DIR")
    budget_limit_usd: float | None = Field(None, alias="BUDGET_LIMIT_USD")
    cache_min_tokens: int = Field(MIN_CACHE_TOKENS, alias="GEMINI_CACHE_MIN_TOKENS")

    # Provider Configuration
    llm_provider_type: str = Field(
        "gemini", description="LLM provider type (gemini, etc.)"
    )
    graph_provider_type: str = Field(
        "neo4j", description="Graph provider type (neo4j, etc.)"
    )

    # Async Queue Configuration
    redis_url: str = Field(
        "redis://localhost:6379", description="Redis URL for FastStream"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
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
        if v != "gemini-3-pro-preview":
            raise ValueError(
                "Unsupported model. This system only allows 'gemini-3-pro-preview'."
            )
        return v

    @field_validator("max_concurrency")
    @classmethod
    def validate_concurrency(cls, v: int) -> int:
        if not 1 <= v <= 20:
            raise ValueError(ERROR_MESSAGES["concurrency_range"])
        return v

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        if not 30 <= v <= 600:
            raise ValueError(ERROR_MESSAGES["timeout_range"])
        return v

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 2.0:
            raise ValueError(ERROR_MESSAGES["temperature_range"])
        return v

    @field_validator("cache_ttl_minutes")
    @classmethod
    def validate_cache_ttl(cls, v: int) -> int:
        if not 1 <= v <= 1440:
            raise ValueError(ERROR_MESSAGES["cache_ttl_range"])
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
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
        if v is None:
            return v
        if v <= 0:
            raise ValueError(ERROR_MESSAGES["budget_positive"])
        return v

    @field_validator("cache_stats_max_entries")
    @classmethod
    def validate_cache_stats_max_entries(cls, v: int) -> int:
        if v < 1:
            raise ValueError(ERROR_MESSAGES["cache_stats_min_entries"])
        return v

    @field_validator("cache_min_tokens")
    @classmethod
    def validate_cache_min_tokens(cls, v: int) -> int:
        if v < 1:
            raise ValueError("cache_min_tokens must be positive")
        return v

    def model_post_init(self, __context: Any) -> None:
        """Ensure required directories exist after settings load."""
        self._ensure_directories()

    @staticmethod
    def _detect_project_root() -> Path:
        """
        Detect the project root by checking several hints:
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
        """프로젝트 루트 디렉토리 반환"""
        return self._detect_project_root()

    @property
    def template_dir(self) -> Path:
        """Jinja2 템플릿 디렉토리 반환"""
        return self.base_dir / "templates"

    @property
    def input_dir(self) -> Path:
        """입력 데이터 디렉토리 반환"""
        return self.base_dir / "data" / "inputs"

    @property
    def output_dir(self) -> Path:
        """출력 데이터 디렉토리 반환"""
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
