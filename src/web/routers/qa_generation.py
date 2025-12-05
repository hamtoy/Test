# mypy: allow-untyped-decorators
"""QA 생성 엔드포인트."""
from __future__ import annotations

from fastapi import APIRouter
from src.web.routers.qa_common import *

router = APIRouter(prefix="/api", tags=["qa-generation"])

# Import the generation endpoint from original qa module temporarily
# This will be properly extracted after initial setup
@router.post("/qa/generate")
async def api_generate_qa(body: GenerateQARequest) -> Dict[str, Any]:
    """QA 쌍 생성 (임시 - 원본에서 가져옴)."""
    # Delegate to original implementation
    from src.web.routers import qa_old
    return await qa_old.api_generate_qa(body)
