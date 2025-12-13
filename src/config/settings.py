"""Application Configuration Settings.

Pydantic-based configuration management with environment variable loading
and comprehensive validation for the Gemini QA system.

This module composes settings from modular mixin files:
- llm.py: LLM/API settings
- database.py: Neo4j/Redis settings
- web.py: CORS/timeout settings
- features.py: Feature flags
"""

# mypy: disable-error-code=misc
import logging
import os
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.config.constants import ERROR_MESSAGES
from src.config.database import DatabaseSettingsMixin
from src.config.features import FeatureSettingsMixin
from src.config.llm import LLMSettingsMixin
from src.config.web import WebSettingsMixin

logger = logging.getLogger(__name__)


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
