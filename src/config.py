import os
import re
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppConfig(BaseSettings):
    """[Modern Config] Pydantic Settings를 이용한 설정 관리"""
    api_key: str = Field(..., alias="GEMINI_API_KEY")
    model_name: str = Field("gemini-3-pro-preview", alias="GEMINI_MODEL_NAME")
    max_output_tokens: int = Field(8192, alias="GEMINI_MAX_OUTPUT_TOKENS")
    timeout: int = Field(120, alias="GEMINI_TIMEOUT")
    max_concurrency: int = Field(5, alias="GEMINI_MAX_CONCURRENCY")
    cache_size: int = Field(50, alias="GEMINI_CACHE_SIZE")
    temperature: float = Field(0.2, alias="GEMINI_TEMPERATURE")
    cache_ttl_minutes: int = Field(10, alias="GEMINI_CACHE_TTL_MINUTES")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    # [Typo Prevention] extra="forbid"로 변경하여 오타를 즉시 감지
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="forbid")

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        # Google API 키 형식: AIza + 20+ 안전 문자
        if not re.match(r"^AIza[0-9A-Za-z_\-]{20,}$", v):
            raise ValueError("Invalid GEMINI_API_KEY format (expected Google API key starting with 'AIza')")
        return v

    @field_validator("max_concurrency")
    @classmethod
    def validate_concurrency(cls, v: int) -> int:
        if not 1 <= v <= 20:
            raise ValueError("max_concurrency must be between 1 and 20")
        return v

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        if not 30 <= v <= 600:
            raise ValueError("timeout must be between 30 and 600 seconds")
        return v

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 2.0:
            raise ValueError("temperature must be between 0.0 and 2.0")
        return v

    @field_validator("cache_ttl_minutes")
    @classmethod
    def validate_cache_ttl(cls, v: int) -> int:
        if not 1 <= v <= 1440:
            raise ValueError("cache_ttl_minutes must be between 1 and 1440")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return upper

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
