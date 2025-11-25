"""워크플로우 컨텍스트."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from google.generativeai import caching
    from rich.progress import Progress

    from src.agent import GeminiAgent
    from src.config import AppConfig


@dataclass
class WorkflowContext:
    """워크플로우 실행 컨텍스트."""

    agent: GeminiAgent
    config: AppConfig
    logger: logging.Logger
    ocr_text: str
    candidates: Dict[str, str]
    cache: Optional[caching.CachedContent]
    total_turns: int
    checkpoint_path: Optional[Path]
    progress: Optional[Progress] = None
