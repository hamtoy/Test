# mypy: allow-untyped-decorators
"""OCR 텍스트 관리 엔드포인트.

엔드포인트:
- GET /api/ocr - OCR 텍스트 조회
- POST /api/ocr - OCR 텍스트 저장
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from starlette.requests import Request

from src.config import AppConfig
from src.web.models import OCRTextInput
from src.web.utils import load_ocr_text as _load_ocr_text
from src.web.utils import save_ocr_text as _save_ocr_text

router = APIRouter(prefix="/api", tags=["ocr"])
logger = logging.getLogger(__name__)

# Module-level config (set by set_dependencies)
_config: AppConfig | None = None


def set_dependencies(config: AppConfig) -> None:
    """Set dependencies for OCR router."""
    global _config
    _config = config


def _get_config() -> AppConfig:
    """Get config, raising error if not set."""
    if _config is None:
        raise RuntimeError("OCR router not initialized. Call set_dependencies first.")
    return _config


def _get_request_id(request: Request) -> str:
    """Get request ID from request state."""
    return getattr(request.state, "request_id", "")


@router.get("/ocr")
async def api_get_ocr(request: Request) -> dict[str, str]:
    """OCR 텍스트 조회."""
    try:
        config = _get_config()
        ocr_text = _load_ocr_text(config)
        return {"ocr": ocr_text}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to load OCR text",
            extra={
                "request_id": _get_request_id(request),
                "error_type": exc.__class__.__name__,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="OCR 텍스트 조회 중 오류가 발생했습니다.",
        ) from exc


@router.post("/ocr")
async def api_save_ocr(request: Request, payload: OCRTextInput) -> dict[str, str]:
    """OCR 텍스트 저장 (비동기 파일 I/O)."""
    try:
        config = _get_config()
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _save_ocr_text, config, payload.text)

        logger.info(
            "OCR text saved successfully",
            extra={
                "request_id": _get_request_id(request),
                "text_length": len(payload.text),
            },
        )
        return {"status": "success", "message": "OCR 텍스트가 저장되었습니다."}
    except Exception as exc:
        logger.error(
            "Failed to save OCR text",
            extra={
                "request_id": _get_request_id(request),
                "error_type": exc.__class__.__name__,
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="OCR 텍스트 저장 실패") from exc


__all__ = ["router", "set_dependencies"]
