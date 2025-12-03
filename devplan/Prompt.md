# 🤖 AI Agent Improvement Prompts

> ## 🚨 MANDATORY: FILE MODIFICATION REQUIRED
> 
> **⛔ DO NOT just respond with text or code blocks.**
> **⛔ DO NOT say "you can modify like this" without actually modifying.**
> **⛔ DO NOT explain what needs to be done without doing it.**
> 
> **✅ YOU MUST use file editing tools (`edit`, `create`) to directly modify files.**
> **✅ After each prompt, confirm "I have modified the file(s)" with the actual changes made.**
> 
> ---
> 
> **Process ALL prompts below SEQUENTIALLY. Do NOT stop after completing one prompt.**

---

## 📋 Execution Checklist

| # | Prompt ID | Title | Priority | Status |
|:---:|:---|:---|:---:|:---:|
| 1 | PROMPT-001 | Web API Module Split | P2 | ✅ Completed |
| 2 | PROMPT-002 | Agent Core Module Split | P2 | ✅ Completed |
| 3 | PROMPT-003 | RAG System Additional Modularization | P2 | ⬜ Pending |
| 4 | PROMPT-004 | Web Session Management Implementation | P2 | ⬜ Pending |
| 5 | PROMPT-005 | Error Logging Enhancement | P3 | ⬜ Pending |

**Total: 5 prompts** | **Completed: 1** | **Remaining: 4**

---

## 🟡 Priority 2 (High) - Execute First

### [PROMPT-001] Web API Module Split

> **🚨 REQUIRED: Use `edit` or `create` tools to make changes. Do NOT just show code.**

**⏱️ Execute this prompt now, then proceed to PROMPT-002**

**Task**: Split the large `src/web/api.py` (1695 lines) into focused router modules
**Files to Modify**: 
- `src/web/api.py`
- Create: `src/web/routers/__init__.py`
- Create: `src/web/routers/qa.py`
- Create: `src/web/routers/workspace.py`
- Create: `src/web/routers/health.py`
- Create: `src/web/routers/stream.py`
- Create: `src/web/utils.py`

#### Instructions:

1. Create the routers directory structure
2. Extract QA-related endpoints to `routers/qa.py`
3. Extract workspace endpoints to `routers/workspace.py`
4. Extract health check endpoints to `routers/health.py`
5. Extract streaming endpoints to `routers/stream.py`
6. Move common utilities to `utils.py`
7. Update main `api.py` to import and include routers

#### Implementation Code:

**File: `src/web/routers/__init__.py`**
```python
"""Web API routers package."""

from src.web.routers.health import router as health_router
from src.web.routers.qa import router as qa_router
from src.web.routers.stream import router as stream_router
from src.web.routers.workspace import router as workspace_router

__all__ = ["health_router", "qa_router", "stream_router", "workspace_router"]
```

**File: `src/web/routers/health.py`**
```python
"""Health check and monitoring endpoints."""

from __future__ import annotations

import logging
from typing import Dict

from fastapi import APIRouter, HTTPException
from src.infra.health import HealthChecker, HealthStatus, check_gemini_api

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint.

    Returns:
        Health status dictionary
    """
    try:
        checker = HealthChecker()
        status: HealthStatus = await checker.check_all()
        if status["status"] == "healthy":
            return {"status": "ok"}
        else:
            raise HTTPException(status_code=503, detail="Service unhealthy")
    except Exception as e:
        logger.error("Health check failed: %s", str(e))
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/health/gemini")
async def health_check_gemini() -> Dict[str, str]:
    """Check Gemini API connectivity.

    Returns:
        Gemini API status
    """
    try:
        is_healthy = await check_gemini_api()
        if is_healthy:
            return {"status": "ok", "service": "gemini"}
        else:
            raise HTTPException(status_code=503, detail="Gemini API unavailable")
    except Exception as e:
        logger.error("Gemini health check failed: %s", str(e))
        raise HTTPException(status_code=503, detail=str(e))
```

**File: `src/web/routers/qa.py`**
```python
"""QA generation and evaluation endpoints."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from src.agent import GeminiAgent
from src.config import AppConfig
from src.config.constants import (
    QA_BATCH_GENERATION_TIMEOUT,
    QA_SINGLE_GENERATION_TIMEOUT,
)
from src.qa.pipeline import IntegratedQAPipeline
from src.web.models import GenerateQARequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["qa"])

# Global instances (initialized by lifespan)
_config: Optional[AppConfig] = None
agent: Optional[GeminiAgent] = None
pipeline: Optional[IntegratedQAPipeline] = None


def set_dependencies(
    config: AppConfig,
    gemini_agent: GeminiAgent,
    qa_pipeline: IntegratedQAPipeline,
) -> None:
    """Set global dependencies for QA router.

    Args:
        config: Application configuration
        gemini_agent: Gemini agent instance
        qa_pipeline: QA pipeline instance
    """
    global _config, agent, pipeline
    _config = config
    agent = gemini_agent
    pipeline = qa_pipeline


@router.post("/generate-qa")
async def generate_qa(request: GenerateQARequest) -> Dict[str, Any]:
    """Generate QA pairs based on request.

    Args:
        request: QA generation request

    Returns:
        Generated QA pairs

    Raises:
        HTTPException: If agent not initialized or generation fails
    """
    if agent is None:
        raise HTTPException(status_code=500, detail="Agent not initialized")

    try:
        if request.batch_mode:
            timeout = QA_BATCH_GENERATION_TIMEOUT
        else:
            timeout = QA_SINGLE_GENERATION_TIMEOUT

        result = await asyncio.wait_for(
            pipeline.generate_qa(
                ocr_text=request.ocr_text,
                qtype=request.qtype,
                num_questions=request.num_questions or 1,
            ),
            timeout=timeout,
        )

        return {"success": True, "data": result}

    except asyncio.TimeoutError:
        timeout_msg = f"Generation timed out after {timeout}s"
        logger.error(timeout_msg)
        raise HTTPException(status_code=504, detail=timeout_msg)
    except Exception as e:
        logger.error("QA generation failed: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")
```

**File: `src/web/routers/workspace.py`**
```python
"""Workspace management endpoints."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from src.agent import GeminiAgent
from src.config import AppConfig
from src.web.models import UnifiedWorkspaceRequest, WorkspaceRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["workspace"])

# Global instances
_config: Optional[AppConfig] = None
agent: Optional[GeminiAgent] = None


def set_dependencies(config: AppConfig, gemini_agent: GeminiAgent) -> None:
    """Set global dependencies for workspace router.

    Args:
        config: Application configuration
        gemini_agent: Gemini agent instance
    """
    global _config, agent
    _config = config
    agent = gemini_agent


@router.post("/workspace/unified")
async def unified_workspace(request: UnifiedWorkspaceRequest) -> Dict[str, Any]:
    """Unified workspace endpoint for batch operations.

    Args:
        request: Workspace request

    Returns:
        Workspace operation results

    Raises:
        HTTPException: If agent not initialized or operation fails
    """
    if agent is None:
        raise HTTPException(status_code=500, detail="Agent not initialized")

    try:
        # Process workspace request
        results = await _process_workspace(request)
        return {"success": True, "results": results}

    except Exception as e:
        logger.error("Workspace operation failed: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Operation failed: {str(e)}")


async def _process_workspace(request: UnifiedWorkspaceRequest) -> Dict[str, Any]:
    """Process workspace request.

    Args:
        request: Workspace request

    Returns:
        Processing results
    """
    # Implementation here
    return {"status": "processed"}
```

**File: `src/web/routers/stream.py`**
```python
"""Streaming response endpoints."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from src.agent import GeminiAgent
from src.config import AppConfig
from src.web.models import StreamGenerateRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["stream"])

# Global instances
_config: Optional[AppConfig] = None
agent: Optional[GeminiAgent] = None


def set_dependencies(config: AppConfig, gemini_agent: GeminiAgent) -> None:
    """Set global dependencies for stream router.

    Args:
        config: Application configuration
        gemini_agent: Gemini agent instance
    """
    global _config, agent
    _config = config
    agent = gemini_agent


@router.post("/stream/generate")
async def stream_generate(request: StreamGenerateRequest) -> StreamingResponse:
    """Stream generation endpoint.

    Args:
        request: Stream generation request

    Returns:
        Streaming response

    Raises:
        HTTPException: If agent not initialized or stream fails
    """
    if agent is None:
        raise HTTPException(status_code=500, detail="Agent not initialized")

    async def generate_stream() -> AsyncIterator[str]:
        """Generate streaming content.

        Yields:
            Content chunks
        """
        try:
            # Stream implementation
            yield "data: Starting generation\n\n"
            await asyncio.sleep(0.1)
            yield "data: Generation complete\n\n"

        except Exception as e:
            logger.error("Stream generation failed: %s", str(e), exc_info=True)
            yield f"data: Error: {str(e)}\n\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")
```

**File: `src/web/utils.py`**
```python
"""Common utilities for web API."""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def format_error_response(error: Exception) -> Dict[str, Any]:
    """Format error as API response.

    Args:
        error: Exception to format

    Returns:
        Formatted error response
    """
    return {
        "success": False,
        "error": str(error),
        "type": type(error).__name__,
    }


def validate_request_size(data: str, max_size: int = 1_000_000) -> bool:
    """Validate request data size.

    Args:
        data: Request data
        max_size: Maximum allowed size in bytes

    Returns:
        True if valid, False otherwise
    """
    return len(data.encode("utf-8")) <= max_size
```

**Update main `src/web/api.py`** - Replace the router definitions with includes:
```python
from src.web.routers import health_router, qa_router, stream_router, workspace_router

# In the app creation section:
app.include_router(health_router)
app.include_router(qa_router)
app.include_router(workspace_router)
app.include_router(stream_router)

# In lifespan, initialize routers:
from src.web.routers import qa, workspace, stream

qa.set_dependencies(_config, agent, pipeline)
workspace.set_dependencies(_config, agent)
stream.set_dependencies(_config, agent)
```

#### Verification:
- Run: `uv run ruff format . && uv run ruff check --fix .`
- Run: `uv run mypy src/web/`
- Run: `uv run pytest tests/unit/web/ -v`
- Expected: All checks pass, no errors

**✅ After completing this prompt, proceed to [PROMPT-002]**
