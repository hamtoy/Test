"""System optimization router.

Provides endpoints for triggering self-improvement analysis and retrieving suggestions.
"""

from __future__ import annotations

import json
import logging
from typing import Any, cast

from fastapi import APIRouter, HTTPException

from src.features.self_improvement import SelfImprovingSystem

router = APIRouter(prefix="/api/optimization", tags=["optimization"])
logger = logging.getLogger(__name__)


@router.post("/analyze")
async def trigger_analysis() -> dict[str, Any]:
    """Trigger self-improvement analysis."""
    try:
        system = SelfImprovingSystem()
        report = await system.analyze_and_suggest()
        return {"status": "success", "report": report}
    except Exception as exc:
        logger.error("Analysis failed", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/suggestions")
async def get_suggestions() -> dict[str, Any]:
    """Get latest improvement suggestions."""
    try:
        system = SelfImprovingSystem()
        if not system.suggestions_file.exists():
            return {"suggestions": [], "timestamp": None}

        content = system.suggestions_file.read_text(encoding="utf-8")
        return cast(dict[str, Any], json.loads(content))
    except Exception as exc:
        logger.error("Failed to load suggestions", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to load suggestions"
        ) from exc
