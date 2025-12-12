# mypy: allow-untyped-decorators
"""Cache statistics endpoint router."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from src.config import AppConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cache", tags=["cache"])

# Module-level config (set by set_dependencies)
_config: AppConfig | None = None


def set_dependencies(config: AppConfig) -> None:
    """Inject configuration dependency."""
    global _config
    _config = config


def _get_config() -> AppConfig:
    """Get config, falling back to default if not set."""
    if _config is not None:
        return _config
    return AppConfig()


def _parse_cache_stats(file_path: Path) -> dict[str, Any]:
    """Parse JSONL cache stats file and compute summary statistics.

    Args:
        file_path: Path to the cache_stats.jsonl file.

    Returns:
        Dictionary with aggregated statistics.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Cache stats file not found: {file_path}")

    total_entries = 0
    cache_hits = 0
    cache_misses = 0
    total_tokens_input = 0
    total_tokens_output = 0
    total_cost_usd = 0.0

    with open(file_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                total_entries += 1

                # Count cache status
                cache_status = entry.get("cache_status", "")
                if cache_status == "hit":
                    cache_hits += 1
                elif cache_status == "miss":
                    cache_misses += 1

                # Aggregate token usage
                usage = entry.get("token_usage", {})
                total_tokens_input += usage.get("input_tokens", 0)
                total_tokens_output += usage.get("output_tokens", 0)

                # Aggregate cost
                total_cost_usd += entry.get("cost_usd", 0.0)

            except json.JSONDecodeError:
                # Skip malformed lines
                logger.debug("Skipping malformed JSONL line")
                continue

    total_requests = cache_hits + cache_misses
    hit_rate = (cache_hits / total_requests * 100) if total_requests > 0 else 0.0

    return {
        "total_entries": total_entries,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "hit_rate_percent": round(hit_rate, 2),
        "total_tokens": {
            "input": total_tokens_input,
            "output": total_tokens_output,
            "total": total_tokens_input + total_tokens_output,
        },
        "total_cost_usd": round(total_cost_usd, 4),
    }


@router.get("/summary")
async def get_cache_stats_summary() -> dict[str, Any]:
    """Get cache statistics summary from JSONL file.

    Returns:
        JSON summary of cache hit/miss, token usage, and cost.

    Raises:
        HTTPException: 404 if stats file not found.
    """
    config = _get_config()
    stats_path = config.cache_stats_path

    try:
        summary = _parse_cache_stats(stats_path)
        return {"status": "ok", "data": summary}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to parse cache stats: %s", e)
        raise HTTPException(
            status_code=500, detail="Failed to parse cache statistics"
        ) from e


__all__ = ["router", "set_dependencies"]
