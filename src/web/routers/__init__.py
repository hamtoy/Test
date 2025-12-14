"""Web API routers package."""

from src.web.routers.cache_stats import router as cache_stats_router
from src.web.routers.config_api import router as config_api_router
from src.web.routers.health import router as health_router
from src.web.routers.logs_api import router as logs_api_router
from src.web.routers.metrics import router as metrics_router
from src.web.routers.ocr import router as ocr_router
from src.web.routers.optimization import router as optimization_router
from src.web.routers.pages import router as pages_router
from src.web.routers.qa import router as qa_router
from src.web.routers.session import router as session_router
from src.web.routers.stream import router as stream_router
from src.web.routers.workspace import router as workspace_router

__all__ = [
    "cache_stats_router",
    "config_api_router",
    "health_router",
    "logs_api_router",
    "metrics_router",
    "ocr_router",
    "optimization_router",
    "pages_router",
    "qa_router",
    "session_router",
    "stream_router",
    "workspace_router",
]
