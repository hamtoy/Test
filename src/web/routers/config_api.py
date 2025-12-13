# mypy: allow-untyped-decorators
"""Configuration API endpoints for reading and updating settings."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from src.utils.file_lock import FileLock

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["config"])


class ConfigResponse(BaseModel):
    """Response model for configuration data."""

    llm_model: str = Field(default="", description="LLM model name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)
    log_level: str = Field(default="INFO")
    output_dir: str = Field(default="output")
    enable_cache: bool = Field(default=True)
    cache_ttl: int = Field(default=3600, ge=0)


class ConfigUpdateRequest(BaseModel):
    """Request model for updating configuration."""

    llm_model: str | None = Field(default=None, description="LLM model name")
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    log_level: str | None = Field(default=None)
    output_dir: str | None = Field(default=None)
    enable_cache: bool | None = Field(default=None)
    cache_ttl: int | None = Field(default=None, ge=0)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str | None) -> str | None:
        if v is not None:
            valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
            if v.upper() not in valid_levels:
                raise ValueError(f"log_level must be one of {valid_levels}")
            return v.upper()
        return v


def _get_env_file_path() -> Path:
    """Get the path to the .env file."""
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / ".env"


def _read_env_file() -> dict[str, str]:
    """Read and parse the .env file."""
    env_path = _get_env_file_path()
    result: dict[str, str] = {}

    if not env_path.exists():
        return result

    content = env_path.read_text(encoding="utf-8")
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            # Remove quotes if present
            value = value.strip().strip("'\"")
            result[key.strip()] = value

    return result


def _process_existing_line(
    line: str,
    updates: dict[str, str],
    updated_keys: set[str],
) -> str:
    """Process a single line from existing env file."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return line

    key = stripped.split("=", 1)[0].strip()
    if key in updates:
        updated_keys.add(key)
        return f"{key}={updates[key]}"
    return line


def _write_env_file(updates: dict[str, str]) -> None:
    """Update values in the .env file with file locking for concurrency safety."""
    env_path = _get_env_file_path()

    # Use file lock to prevent race conditions
    with FileLock(env_path, timeout=5.0):
        lines: list[str] = []
        updated_keys: set[str] = set()

        if env_path.exists():
            content = env_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                processed = _process_existing_line(line, updates, updated_keys)
                lines.append(processed)

        # Add new keys that weren't in the file
        for key, value in updates.items():
            if key not in updated_keys:
                lines.append(f"{key}={value}")

        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# Mapping from config fields to environment variable names
CONFIG_ENV_MAP = {
    "llm_model": "LLM_MODEL",
    "temperature": "LLM_TEMPERATURE",
    "max_tokens": "LLM_MAX_TOKENS",
    "log_level": "LOG_LEVEL",
    "output_dir": "OUTPUT_DIR",
    "enable_cache": "ENABLE_CACHE",
    "cache_ttl": "CACHE_TTL",
}


@router.get("", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    """Get current configuration from environment/.env file."""
    loop = asyncio.get_running_loop()
    env_data = await loop.run_in_executor(None, _read_env_file)

    # Merge with current environment
    merged = {**os.environ, **env_data}

    return ConfigResponse(
        llm_model=merged.get("LLM_MODEL", merged.get("GEMINI_MODEL", "")),
        temperature=float(merged.get("LLM_TEMPERATURE", "0.7")),
        max_tokens=int(merged.get("LLM_MAX_TOKENS", "4096")),
        log_level=merged.get("LOG_LEVEL", "INFO"),
        output_dir=merged.get("OUTPUT_DIR", "output"),
        enable_cache=merged.get("ENABLE_CACHE", "true").lower() == "true",
        cache_ttl=int(merged.get("CACHE_TTL", "3600")),
    )


@router.post("", response_model=ConfigResponse)
async def update_config(request: ConfigUpdateRequest) -> ConfigResponse:
    """Update configuration in .env file."""
    updates: dict[str, str] = {}

    request_data = request.model_dump(exclude_none=True)
    for field_name, value in request_data.items():
        env_key = CONFIG_ENV_MAP.get(field_name)
        if env_key:
            if isinstance(value, bool):
                updates[env_key] = "true" if value else "false"
            else:
                updates[env_key] = str(value)

    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _write_env_file, updates)
        logger.info("Configuration updated: %s", list(updates.keys()))
    except Exception as e:
        logger.error("Failed to update configuration: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to update config: {e}")

    return await get_config()


__all__ = ["router"]
