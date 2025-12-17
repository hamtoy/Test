"""워크플로우 컨텍스트."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

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
    candidates: dict[str, str]
    cache: Any | None
    total_turns: int
    checkpoint_path: Path | None
    progress: Progress | None = None
