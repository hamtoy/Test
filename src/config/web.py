"""Web API Configuration Settings.

Handles CORS, timeouts, and response formatting for FastAPI.
"""

from pydantic import Field
from pydantic_settings import BaseSettings

from src.config.constants import (
    QA_BATCH_GENERATION_TIMEOUT,
    QA_SINGLE_GENERATION_TIMEOUT,
    WORKSPACE_GENERATION_TIMEOUT,
    WORKSPACE_UNIFIED_TIMEOUT,
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
