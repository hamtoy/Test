"""Helpers for optional standardized API responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.config import AppConfig


@dataclass
class APIMetadata:
    """Metadata for API responses (timing/cache/token usage)."""

    duration: float = 0.0
    cache_hit: bool = False
    token_usage: Optional[Dict[str, int]] = None


def build_response(
    data: Any,
    *,
    success: bool = True,
    errors: Optional[List[str]] = None,
    metadata: Optional[APIMetadata] = None,
    config: Optional[AppConfig] = None,
) -> Any:
    """Wrap response if standard response is enabled; otherwise pass through."""
    if config and getattr(config, "enable_standard_response", False):
        base = {
            "success": success,
            "data": data,
            "metadata": metadata.__dict__ if metadata else None,
            "errors": errors,
        }
        # 역호환: dict 데이터를 상위 키로 노출
        if isinstance(data, dict):
            base.update(data)
        return base
    return data
