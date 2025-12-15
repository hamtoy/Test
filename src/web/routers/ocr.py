# mypy: allow-untyped-decorators
"""OCR 텍스트 관리 엔드포인트.

엔드포인트:
- GET /api/ocr - OCR 텍스트 조회
- POST /api/ocr - OCR 텍스트 저장
- POST /api/ocr/image - 이미지 업로드 → Gemini OCR → 텍스트 추출
"""

from __future__ import annotations

import contextlib
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any

import aiofiles
from fastapi import APIRouter, File, HTTPException, UploadFile
from starlette.requests import Request

from src.config import AppConfig
from src.core.interfaces import LLMProvider
from src.features.multimodal import MultimodalUnderstanding
from src.web.models import OCRTextInput
from src.web.utils import load_ocr_text as _load_ocr_text
from src.web.utils import save_ocr_text as _save_ocr_text

router = APIRouter(prefix="/api", tags=["ocr"])
logger = logging.getLogger(__name__)

# Module-level dependencies (set by set_dependencies)
_config: AppConfig | None = None
_llm_provider: LLMProvider | None = None


def set_dependencies(
    config: AppConfig,
    llm_provider: LLMProvider | None = None,
) -> None:
    """Set dependencies for OCR router."""
    global _config, _llm_provider
    _config = config
    _llm_provider = llm_provider


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
    """OCR 텍스트 조회 (비동기 파일 I/O)."""
    try:
        config = _get_config()
        ocr_text = await _load_ocr_text(config)
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
        await _save_ocr_text(config, payload.text)

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


@router.post("/ocr/image")
async def api_ocr_image(
    request: Request,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """이미지 업로드 → Gemini Vision OCR → 텍스트 추출 및 저장.

    Args:
        request: FastAPI 요청 객체
        file: 업로드할 이미지 파일 (PNG, JPG, GIF, WebP)

    Returns:
        추출된 텍스트 및 메타데이터
    """
    config = _get_config()

    if _llm_provider is None:
        raise HTTPException(
            status_code=503,
            detail="LLM Provider가 초기화되지 않았습니다.",
        )

    # 파일 타입 검증
    allowed_types = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp"}
    content_type = file.content_type or "application/octet-stream"
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 이미지 형식입니다: {content_type}",
        )

    try:
        # 임시 파일 경로 생성 (비동기 처리 호환)
        suffix = Path(file.filename or "image.png").suffix
        tmp_filename = f"{uuid.uuid4()}{suffix}"
        tmp_path = Path(tempfile.gettempdir()) / tmp_filename

        # 비동기 파일 쓰기
        async with aiofiles.open(tmp_path, "wb") as out_file:
            content = await file.read()
            await out_file.write(content)

        # Multimodal OCR 실행
        multimodal = MultimodalUnderstanding(llm_provider=_llm_provider)
        result = await multimodal.analyze_image_deep(str(tmp_path))

        # OCR 텍스트 저장
        extracted_text = result.get("extracted_text", "")
        if extracted_text:
            await _save_ocr_text(config, extracted_text)

        logger.info(
            "Image OCR completed",
            extra={
                "request_id": _get_request_id(request),
                "filename": file.filename,
                "text_length": len(extracted_text),
            },
        )

        return {
            "status": "success",
            "ocr": extracted_text,
            "metadata": {
                "text_density": result.get("text_density", 0),
                "topics": result.get("topics", []),
                "has_table_chart": result.get("has_table_chart", False),
            },
        }

    except HTTPException:
        raise
    except Exception as exc:
        # DEBUG: Print actual exception for CI debugging
        import traceback

        print(f"DEBUG OCR ERROR: {exc.__class__.__name__}: {exc}")
        traceback.print_exc()

        logger.error(
            "Image OCR failed",
            extra={
                "request_id": _get_request_id(request),
                "filename": file.filename,
                "error_type": exc.__class__.__name__,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"이미지 OCR 처리 실패: {exc}",
        ) from exc
    finally:
        # 임시 파일 삭제
        with contextlib.suppress(Exception):
            Path(tmp_path).unlink(missing_ok=True)


__all__ = ["router", "set_dependencies"]
