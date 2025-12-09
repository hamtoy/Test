# mypy: allow-untyped-decorators
"""페이지 렌더링 엔드포인트.

페이지 라우트:
- GET / (redirect to /qa)
- GET /qa
- GET /eval
- GET /workspace
- GET /multimodal
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

router = APIRouter(tags=["pages"])

# 템플릿 경로
REPO_ROOT = Path(__file__).resolve().parents[3]
templates = Jinja2Templates(directory=str(REPO_ROOT / "templates" / "web"))

ENABLE_MULTIMODAL = os.getenv("ENABLE_MULTIMODAL", "true").lower() == "true"


@router.get("/", response_class=RedirectResponse)
async def root() -> str:
    """루트 경로 → /qa로 리다이렉트."""
    return "/qa"


@router.get("/qa", response_class=HTMLResponse)
async def page_qa(request: Request) -> HTMLResponse:
    """QA 생성 페이지."""
    return templates.TemplateResponse(request, "qa.html")


@router.get("/eval", response_class=HTMLResponse)
async def page_eval(request: Request) -> HTMLResponse:
    """외부 답변 평가 페이지."""
    return templates.TemplateResponse(request, "eval.html")


@router.get("/workspace", response_class=HTMLResponse)
async def page_workspace(request: Request) -> HTMLResponse:
    """워크스페이스 페이지."""
    return templates.TemplateResponse(request, "workspace.html")


if ENABLE_MULTIMODAL:

    @router.get("/multimodal", response_class=HTMLResponse)
    async def page_multimodal() -> HTMLResponse:
        """멀티모달 페이지."""
        html = "<html><body><h1>Multimodal feature is disabled.</h1></body></html>"
        return HTMLResponse(content=html)


__all__ = ["router"]
