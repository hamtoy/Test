"""LLM Configuration Settings.

Handles API keys, model selection, tokens, timeouts, concurrency,
temperature, caching, and budget management for Gemini API.
"""

import logging
import re
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings

from src.config.constants import (
    ERROR_MESSAGES,
    GEMINI_API_KEY_LENGTH,
    MIN_CACHE_TOKENS,
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
        3584,
        alias="GEMINI_MAX_OUTPUT_TOKENS_EXPLANATION",
    )
    max_output_tokens_reasoning: int | None = Field(
        2048,
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
        """Validate max_output_tokens is positive."""
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
