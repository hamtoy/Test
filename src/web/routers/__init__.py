"""Web API routers package."""

from src.web.routers.health import router as health_router
from src.web.routers.qa import router as qa_router
from src.web.routers.stream import router as stream_router
from src.web.routers.workspace import router as workspace_router

__all__ = ["health_router", "qa_router", "stream_router", "workspace_router"]
