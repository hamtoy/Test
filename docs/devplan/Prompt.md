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
| 1 | PROMPT-001 | Web Router Module Optimization - workspace.py | P2 | ⬜ Pending |
| 2 | PROMPT-002 | Web Router Module Optimization - qa.py | P2 | ⬜ Pending |
| 3 | PROMPT-003 | QA RAG System Refactoring | P2 | ⬜ Pending |
| 4 | PROMPT-004 | Agent Core Functional Separation | P2 | ⬜ Pending |
| 5 | PROMPT-005 | Performance Monitoring Dashboard | P3 | ⬜ Pending |

**Total: 5 prompts** | **Completed: 0** | **Remaining: 5**

---

## 🟡 Priority 2 (High) - Execute First

### [PROMPT-001] Web Router Module Optimization - workspace.py

> **⏱️ Execute this prompt now, then proceed to PROMPT-002**

**Task**: Split `src/web/routers/workspace.py` (806 lines) into three focused modules
**Files to Modify**: 
- `src/web/routers/workspace.py` (reduce to ~200 lines)
- Create: `src/web/routers/workspace_generation.py`
- Create: `src/web/routers/workspace_evaluation.py`
- Create: `src/web/routers/workspace_review.py`

#### Instructions:

1. Analyze `src/web/routers/workspace.py` and identify endpoints by category
2. Create three new router files for generation, evaluation, and review
3. Move endpoints to appropriate files while maintaining all functionality
4. Update `src/web/api.py` to include all three routers
5. Ensure all imports and dependencies are correctly handled

#### Implementation Steps:

**Step 1**: Create `src/web/routers/workspace_generation.py`

```python
"""워크스페이스 질의 생성 관련 엔드포인트."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from src.agent import GeminiAgent
from src.config import AppConfig
from src.config.constants import WORKSPACE_GENERATION_TIMEOUT
from src.web.models import WorkspaceRequest
from src.web.response import APIMetadata, build_response
from src.web.service_registry import get_registry
from src.web.utils import load_ocr_text

logger = logging.getLogger(__name__)

router: APIRouter = APIRouter(prefix="/api/workspace", tags=["workspace-generation"])


@router.post("/generate-queries")
async def generate_queries(request: WorkspaceRequest) -> Dict[str, Any]:
    """OCR 텍스트 기반 질의 생성.
    
    Args:
        request: 워크스페이스 요청 (OCR 파일명, 사용자 의도)
        
    Returns:
        생성된 질의 목록 및 메타데이터
        
    Raises:
        HTTPException: OCR 파일 로드 실패 또는 질의 생성 실패 시
    """
    try:
        # Load OCR text
        ocr_text = await load_ocr_text(request.ocr_filename)
        
        # Get agent from registry
        registry = get_registry()
        agent: GeminiAgent = registry.get("gemini_agent")
        
        # Generate queries
        queries = await agent.generate_queries(
            ocr_text=ocr_text,
            user_intent=request.user_intent or "",
            timeout=WORKSPACE_GENERATION_TIMEOUT
        )
        
        metadata = APIMetadata(
            endpoint="/api/workspace/generate-queries",
            status="success"
        )
        
        return build_response(
            data={"queries": queries},
            metadata=metadata
        )
        
    except FileNotFoundError as e:
        logger.error(f"OCR file not found: {request.ocr_filename}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Query generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query generation failed: {e}")


# Add more generation-related endpoints here
```

**Step 2**: Create `src/web/routers/workspace_evaluation.py`

```python
"""워크스페이스 평가 관련 엔드포인트."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from src.agent import GeminiAgent
from src.config.constants import WORKSPACE_EVALUATION_TIMEOUT
from src.web.models import WorkspaceRequest
from src.web.response import APIMetadata, build_response
from src.web.service_registry import get_registry

logger = logging.getLogger(__name__)

router: APIRouter = APIRouter(prefix="/api/workspace", tags=["workspace-evaluation"])


@router.post("/evaluate-candidates")
async def evaluate_candidates(request: WorkspaceRequest) -> Dict[str, Any]:
    """후보 답변들에 대한 평가 수행.
    
    Args:
        request: 워크스페이스 요청 (질의, 후보 답변 목록)
        
    Returns:
        평가 결과 및 점수
        
    Raises:
        HTTPException: 평가 실패 시
    """
    try:
        registry = get_registry()
        agent: GeminiAgent = registry.get("gemini_agent")
        
        # Evaluate all candidates
        evaluation_tasks = [
            agent.evaluate_response(
                query=request.query,
                response=candidate,
                timeout=WORKSPACE_EVALUATION_TIMEOUT
            )
            for candidate in request.candidates
        ]
        
        results = await asyncio.gather(*evaluation_tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = [r for r in results if not isinstance(r, Exception)]
        
        metadata = APIMetadata(
            endpoint="/api/workspace/evaluate-candidates",
            status="success",
            total_evaluated=len(valid_results)
        )
        
        return build_response(
            data={"evaluations": valid_results},
            metadata=metadata
        )
        
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {e}")


# Add more evaluation-related endpoints here
```

**Step 3**: Create `src/web/routers/workspace_review.py`

```python
"""워크스페이스 검수 관련 엔드포인트."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from src.workflow.inspection import inspect_answer
from src.web.models import WorkspaceRequest
from src.web.response import APIMetadata, build_response
from src.web.utils import log_review_session

logger = logging.getLogger(__name__)

router: APIRouter = APIRouter(prefix="/api/workspace", tags=["workspace-review"])


@router.post("/review-answer")
async def review_answer(request: WorkspaceRequest) -> Dict[str, Any]:
    """답변 검수 수행.
    
    Args:
        request: 워크스페이스 요청 (검수 대상 답변)
        
    Returns:
        검수 결과 및 피드백
        
    Raises:
        HTTPException: 검수 실패 시
    """
    try:
        # Perform inspection
        result = await inspect_answer(
            answer=request.answer,
            criteria=request.review_criteria or {}
        )
        
        # Log review session
        await log_review_session(
            answer_id=request.answer_id,
            result=result
        )
        
        metadata = APIMetadata(
            endpoint="/api/workspace/review-answer",
            status="success"
        )
        
        return build_response(
            data={"review_result": result},
            metadata=metadata
        )
        
    except Exception as e:
        logger.error(f"Review failed: {e}")
        raise HTTPException(status_code=500, detail=f"Review failed: {e}")


# Add more review-related endpoints here
```

**Step 4**: Update `src/web/routers/workspace.py` to keep only router aggregation

```python
"""워크스페이스 관련 엔드포인트 (메인 라우터)."""

from __future__ import annotations

from fastapi import APIRouter

from . import workspace_evaluation, workspace_generation, workspace_review

# Main workspace router that includes all sub-routers
router: APIRouter = APIRouter()

# Include sub-routers
router.include_router(workspace_generation.router)
router.include_router(workspace_evaluation.router)
router.include_router(workspace_review.router)

# Backward compatibility: export sub-routers
__all__ = [
    "router",
    "workspace_generation",
    "workspace_evaluation",
    "workspace_review",
]
```

**Step 5**: Update `src/web/api.py` if needed (router should auto-include)

#### Verification:
- Run: `mypy src/web/routers/`
- Run: `pytest tests/web/ -v`
- Expected: All type checks pass, all tests pass

**✅ After completing this prompt, proceed to [PROMPT-002]**

---

### [PROMPT-002] Web Router Module Optimization - qa.py

> **⏱️ Execute this prompt now, then proceed to PROMPT-003**

**Task**: Split `src/web/routers/qa.py` (703 lines) into three focused modules
**Files to Modify**:
- `src/web/routers/qa.py` (reduce to ~200 lines)
- Create: `src/web/routers/qa_generation.py`
- Create: `src/web/routers/qa_evaluation.py`
- Create: `src/web/routers/qa_batch.py`

#### Instructions:

1. Analyze `src/web/routers/qa.py` and categorize endpoints
2. Create three new router files for generation, evaluation, and batch operations
3. Move endpoints while preserving all functionality
4. Update imports and ensure proper dependency injection

#### Implementation Steps:

**Step 1**: Create `src/web/routers/qa_generation.py`

```python
"""QA 생성 관련 엔드포인트."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from src.qa.factory import QASystemFactory
from src.qa.pipeline import IntegratedQAPipeline
from src.web.models import QARequest
from src.web.response import APIMetadata, build_response
from src.web.service_registry import get_registry

logger = logging.getLogger(__name__)

router: APIRouter = APIRouter(prefix="/api/qa", tags=["qa-generation"])


@router.post("/generate")
async def generate_qa(request: QARequest) -> Dict[str, Any]:
    """QA 쌍 생성.
    
    Args:
        request: QA 생성 요청
        
    Returns:
        생성된 QA 쌍 및 메타데이터
        
    Raises:
        HTTPException: 생성 실패 시
    """
    try:
        registry = get_registry()
        pipeline: IntegratedQAPipeline = registry.get("qa_pipeline")
        
        qa_pairs = await pipeline.generate_qa_pairs(
            context=request.context,
            num_pairs=request.num_pairs or 5
        )
        
        metadata = APIMetadata(
            endpoint="/api/qa/generate",
            status="success",
            total_generated=len(qa_pairs)
        )
        
        return build_response(
            data={"qa_pairs": qa_pairs},
            metadata=metadata
        )
        
    except Exception as e:
        logger.error(f"QA generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"QA generation failed: {e}")


# Add more generation-related endpoints here
```

**Step 2**: Create `src/web/routers/qa_evaluation.py`

```python
"""QA 평가 관련 엔드포인트."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from src.qa.quality import QualityValidator
from src.web.models import QARequest
from src.web.response import APIMetadata, build_response
from src.web.service_registry import get_registry

logger = logging.getLogger(__name__)

router: APIRouter = APIRouter(prefix="/api/qa", tags=["qa-evaluation"])


@router.post("/evaluate")
async def evaluate_qa(request: QARequest) -> Dict[str, Any]:
    """QA 품질 평가.
    
    Args:
        request: QA 평가 요청
        
    Returns:
        평가 결과 및 점수
        
    Raises:
        HTTPException: 평가 실패 시
    """
    try:
        registry = get_registry()
        validator: QualityValidator = registry.get("quality_validator")
        
        evaluation = await validator.validate_qa_pair(
            question=request.question,
            answer=request.answer
        )
        
        metadata = APIMetadata(
            endpoint="/api/qa/evaluate",
            status="success"
        )
        
        return build_response(
            data={"evaluation": evaluation},
            metadata=metadata
        )
        
    except Exception as e:
        logger.error(f"QA evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=f"QA evaluation failed: {e}")


# Add more evaluation-related endpoints here
```

**Step 3**: Create `src/web/routers/qa_batch.py`

```python
"""QA 배치 처리 관련 엔드포인트."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from src.agent.batch_processor import BatchProcessor
from src.web.models import QABatchRequest
from src.web.response import APIMetadata, build_response
from src.web.service_registry import get_registry

logger = logging.getLogger(__name__)

router: APIRouter = APIRouter(prefix="/api/qa", tags=["qa-batch"])


@router.post("/batch-process")
async def batch_process_qa(request: QABatchRequest) -> Dict[str, Any]:
    """QA 배치 처리.
    
    Args:
        request: 배치 처리 요청
        
    Returns:
        처리 결과 목록
        
    Raises:
        HTTPException: 배치 처리 실패 시
    """
    try:
        registry = get_registry()
        processor: BatchProcessor = registry.get("batch_processor")
        
        results = await processor.process_batch(
            items=request.items,
            concurrency=request.concurrency or 5
        )
        
        metadata = APIMetadata(
            endpoint="/api/qa/batch-process",
            status="success",
            total_processed=len(results),
            successful=sum(1 for r in results if r.get("success"))
        )
        
        return build_response(
            data={"results": results},
            metadata=metadata
        )
        
    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {e}")


# Add more batch-related endpoints here
```

**Step 4**: Update `src/web/routers/qa.py` to aggregate routers

```python
"""QA 관련 엔드포인트 (메인 라우터)."""

from __future__ import annotations

from fastapi import APIRouter

from . import qa_batch, qa_evaluation, qa_generation

# Main QA router that includes all sub-routers
router: APIRouter = APIRouter()

# Include sub-routers
router.include_router(qa_generation.router)
router.include_router(qa_evaluation.router)
router.include_router(qa_batch.router)

# Backward compatibility
__all__ = [
    "router",
    "qa_generation",
    "qa_evaluation",
    "qa_batch",
]
```

#### Verification:
- Run: `mypy src/web/routers/`
- Run: `pytest tests/web/ -v`
- Expected: All type checks pass, all tests pass

**✅ After completing this prompt, proceed to [PROMPT-003]**

---

### [PROMPT-003] QA RAG System Refactoring

> **⏱️ Execute this prompt now, then proceed to PROMPT-004**

**Task**: Refactor `src/qa/rag_system.py` (670 lines) to reduce size to ~400 lines
**Files to Modify**:
- `src/qa/rag_system.py` (reduce to ~400 lines)
- Create: `src/qa/graph/connection.py`
- Create: `src/qa/graph/vector_search.py`
- Update: `src/qa/validators/session_validator.py`

#### Instructions:

1. Extract Neo4j connection management to dedicated module
2. Separate vector search logic
3. Move session validation to validators package
4. Simplify `QAKnowledgeGraph` class using facade pattern

#### Implementation Steps:

**Step 1**: Create `src/qa/graph/connection.py`

```python
"""Neo4j connection management."""

from __future__ import annotations

import atexit
import logging
import weakref
from contextlib import contextmanager
from typing import Generator, Optional

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from src.config import AppConfig
from src.config.utils import require_env
from src.infra.neo4j import SafeDriver, create_sync_driver

logger = logging.getLogger(__name__)


class Neo4jConnectionManager:
    """Neo4j 연결 관리자.
    
    Singleton pattern으로 Neo4j 드라이버를 관리하고
    애플리케이션 종료 시 자동으로 정리합니다.
    """
    
    _instance: Optional[Neo4jConnectionManager] = None
    _driver: Optional[SafeDriver] = None
    
    def __new__(cls) -> Neo4jConnectionManager:
        """Singleton 인스턴스 생성."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def initialize(self, config: AppConfig) -> None:
        """Neo4j 드라이버 초기화.
        
        Args:
            config: 애플리케이션 설정
        """
        if self._driver is not None:
            logger.warning("Driver already initialized")
            return
        
        uri = require_env("NEO4J_URI")
        user = require_env("NEO4J_USER")
        password = require_env("NEO4J_PASSWORD")
        
        try:
            self._driver = create_sync_driver(uri, user, password)
            logger.info("Neo4j connection initialized")
            
            # Register cleanup
            atexit.register(self.close)
            weakref.finalize(self, self.close)
            
        except Exception as e:
            logger.error(f"Failed to initialize Neo4j connection: {e}")
            raise
    
    @contextmanager
    def get_session(self) -> Generator:
        """Neo4j 세션 컨텍스트 매니저.
        
        Yields:
            Neo4j session
            
        Raises:
            RuntimeError: 드라이버가 초기화되지 않은 경우
        """
        if self._driver is None:
            raise RuntimeError("Driver not initialized. Call initialize() first.")
        
        session = self._driver.session()
        try:
            yield session
        finally:
            session.close()
    
    def close(self) -> None:
        """드라이버 종료."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None
            logger.info("Neo4j connection closed")
    
    def verify_connectivity(self) -> bool:
        """Neo4j 연결 확인.
        
        Returns:
            연결 성공 여부
        """
        try:
            with self.get_session() as session:
                result = session.run("RETURN 1")
                return result.single()[0] == 1
        except Exception as e:
            logger.error(f"Connectivity check failed: {e}")
            return False


# Global instance
_connection_manager = Neo4jConnectionManager()


def get_connection_manager() -> Neo4jConnectionManager:
    """Neo4j 연결 관리자 반환."""
    return _connection_manager
```

**Step 2**: Create `src/qa/graph/vector_search.py`

```python
"""Vector search functionality."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.caching.analytics import CacheMetrics
from src.qa.graph.utils import (
    CustomGeminiEmbeddings,
    init_vector_store,
    len_if_sized,
    record_vector_metrics,
)

logger = logging.getLogger(__name__)


class VectorSearchEngine:
    """벡터 검색 엔진.
    
    Gemini Embeddings를 사용하여 Neo4j에서 유사 문서를 검색합니다.
    """
    
    def __init__(self, api_key: str, cache_metrics: Optional[CacheMetrics] = None):
        """초기화.
        
        Args:
            api_key: Gemini API 키
            cache_metrics: 캐시 메트릭 (선택)
        """
        self.embeddings = CustomGeminiEmbeddings(api_key=api_key)
        self.vector_store: Optional[Any] = None
        self.cache_metrics = cache_metrics
    
    async def initialize(
        self,
        uri: str,
        user: str,
        password: str,
        index_name: str = "rule_vector"
    ) -> None:
        """벡터 스토어 초기화.
        
        Args:
            uri: Neo4j URI
            user: Neo4j 사용자명
            password: Neo4j 비밀번호
            index_name: 벡터 인덱스 이름
        """
        self.vector_store = await init_vector_store(
            uri=uri,
            user=user,
            password=password,
            embeddings=self.embeddings,
            index_name=index_name
        )
        logger.info(f"Vector store initialized with index '{index_name}'")
    
    async def search_similar(
        self,
        query: str,
        k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """유사 문서 검색.
        
        Args:
            query: 검색 쿼리
            k: 반환할 문서 수
            filter_dict: 필터 조건 (선택)
            
        Returns:
            검색된 문서 목록
            
        Raises:
            RuntimeError: 벡터 스토어가 초기화되지 않은 경우
        """
        if self.vector_store is None:
            raise RuntimeError("Vector store not initialized")
        
        try:
            # Search similar documents
            results = await self.vector_store.similarity_search(
                query=query,
                k=k,
                filter=filter_dict
            )
            
            # Record metrics
            if self.cache_metrics:
                record_vector_metrics(
                    cache_metrics=self.cache_metrics,
                    query=query,
                    results_count=len_if_sized(results)
                )
            
            logger.debug(f"Found {len(results)} similar documents for query: {query[:50]}...")
            return results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise
    
    async def search_with_score(
        self,
        query: str,
        k: int = 5
    ) -> List[tuple[Any, float]]:
        """점수와 함께 유사 문서 검색.
        
        Args:
            query: 검색 쿼리
            k: 반환할 문서 수
            
        Returns:
            (문서, 점수) 튜플 목록
        """
        if self.vector_store is None:
            raise RuntimeError("Vector store not initialized")
        
        try:
            results = await self.vector_store.similarity_search_with_score(
                query=query,
                k=k
            )
            return results
        except Exception as e:
            logger.error(f"Vector search with score failed: {e}")
            raise
```

**Step 3**: Update `src/qa/rag_system.py` to use new modules

```python
"""QA RAG System - Simplified using facade pattern."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.caching.analytics import CacheMetrics
from src.config import AppConfig
from src.qa.graph.connection import get_connection_manager
from src.qa.graph.utils import ensure_formatting_rule_schema, format_rules
from src.qa.graph.vector_search import VectorSearchEngine
from src.qa.rule_loader import clear_global_rule_cache

logger = logging.getLogger(__name__)


class QAKnowledgeGraph:
    """RAG + 그래프 기반 QA 헬퍼 (Facade)."""
    
    def __init__(self, config: AppConfig, cache_metrics: Optional[CacheMetrics] = None):
        """초기화."""
        self.config = config
        self.cache_metrics = cache_metrics
        
        # Initialize connection manager
        self.connection_mgr = get_connection_manager()
        self.connection_mgr.initialize(config)
        
        # Initialize vector search
        self.vector_search = VectorSearchEngine(
            api_key=config.gemini_api_key,
            cache_metrics=cache_metrics
        )
    
    async def initialize(self) -> None:
        """비동기 초기화."""
        from src.config.utils import require_env
        
        uri = require_env("NEO4J_URI")
        user = require_env("NEO4J_USER")
        password = require_env("NEO4J_PASSWORD")
        
        await self.vector_search.initialize(uri, user, password)
        await ensure_formatting_rule_schema()
        logger.info("QA Knowledge Graph initialized")
    
    async def search_rules(
        self,
        query: str,
        k: int = 5
    ) -> List[Dict[str, Any]]:
        """규칙 검색."""
        results = await self.vector_search.search_similar(query, k)
        return format_rules(results)
    
    def clear_cache(self) -> None:
        """캐시 클리어."""
        clear_global_rule_cache()
    
    def verify_connection(self) -> bool:
        """연결 확인."""
        return self.connection_mgr.verify_connectivity()
```

#### Verification:
- Run: `mypy src/qa/`
- Run: `pytest tests/unit/qa/ -v`
- Expected: All type checks pass, RAG system tests pass

**✅ After completing this prompt, proceed to [PROMPT-004]**

---

### [PROMPT-004] Agent Core Functional Separation

> **⏱️ Execute this prompt now, then proceed to PROMPT-005**

**Task**: Refactor `src/agent/core.py` (624 lines) to reduce to ~400 lines
**Files to Modify**:
- `src/agent/core.py` (reduce to ~400 lines)
- Update: `src/agent/services.py` (consolidate all services)

#### Instructions:

1. Ensure all generation, evaluation, and rewriting logic is in `services.py`
2. Simplify `GeminiAgent` to be a coordinator
3. Remove duplicate code and consolidate service calls

#### Implementation Steps:

**Step 1**: Update `src/agent/services.py` to include all service logic

```python
"""Gemini Agent Services - All business logic."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from src.config import AppConfig
from src.core.models import EvaluationResultSchema

logger = logging.getLogger(__name__)


class QueryGeneratorService:
    """질의 생성 서비스."""
    
    def __init__(self, client: Any, config: AppConfig):
        """초기화."""
        self.client = client
        self.config = config
    
    async def generate_queries(
        self,
        ocr_text: str,
        user_intent: str = "",
        num_queries: int = 5
    ) -> List[str]:
        """OCR 텍스트 기반 질의 생성.
        
        Args:
            ocr_text: OCR 추출 텍스트
            user_intent: 사용자 의도 (선택)
            num_queries: 생성할 질의 수
            
        Returns:
            생성된 질의 목록
        """
        prompt = self._build_query_generation_prompt(ocr_text, user_intent, num_queries)
        response = await self.client.generate_content(prompt)
        return self._parse_queries(response.text)
    
    def _build_query_generation_prompt(
        self,
        ocr_text: str,
        user_intent: str,
        num_queries: int
    ) -> str:
        """질의 생성 프롬프트 빌드."""
        prompt = f"""다음 OCR 텍스트를 분석하여 {num_queries}개의 전략적 질의를 생성하세요.

OCR 텍스트:
{ocr_text}
"""
        if user_intent:
            prompt += f"\n사용자 의도: {user_intent}\n"
        
        prompt += """
요구사항:
1. 텍스트의 핵심 내용을 파악할 수 있는 질의
2. 다양한 관점에서 접근
3. 명확하고 구체적인 질문

형식: 각 질의를 번호와 함께 한 줄로 작성
"""
        return prompt
    
    def _parse_queries(self, text: str) -> List[str]:
        """생성된 텍스트에서 질의 파싱."""
        lines = text.strip().split("\n")
        queries = []
        for line in lines:
            # Remove numbering (1., 2., etc.)
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-")):
                query = line.split(".", 1)[-1].strip()
                if query:
                    queries.append(query)
        return queries


class ResponseEvaluatorService:
    """응답 평가 서비스."""
    
    def __init__(self, client: Any, config: AppConfig):
        """초기화."""
        self.client = client
        self.config = config
    
    async def evaluate_response(
        self,
        query: str,
        response: str,
        criteria: Optional[Dict[str, Any]] = None
    ) -> EvaluationResultSchema:
        """응답 평가.
        
        Args:
            query: 질의
            response: 평가 대상 응답
            criteria: 평가 기준 (선택)
            
        Returns:
            평가 결과
        """
        prompt = self._build_evaluation_prompt(query, response, criteria)
        result = await self.client.generate_content(prompt)
        return self._parse_evaluation(result.text)
    
    def _build_evaluation_prompt(
        self,
        query: str,
        response: str,
        criteria: Optional[Dict[str, Any]]
    ) -> str:
        """평가 프롬프트 빌드."""
        prompt = f"""다음 질의에 대한 응답을 평가하세요.

질의: {query}

응답:
{response}

평가 기준:
1. 정확성 (0-10점)
2. 완전성 (0-10점)
3. 명확성 (0-10점)
4. 관련성 (0-10점)
"""
        if criteria:
            prompt += f"\n추가 기준: {criteria}\n"
        
        prompt += """
형식 (JSON):
{
  "accuracy": <점수>,
  "completeness": <점수>,
  "clarity": <점수>,
  "relevance": <점수>,
  "overall": <평균 점수>,
  "feedback": "<피드백>"
}
"""
        return prompt
    
    def _parse_evaluation(self, text: str) -> EvaluationResultSchema:
        """평가 결과 파싱."""
        import json
        # Extract JSON from markdown code blocks if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        data = json.loads(text.strip())
        return EvaluationResultSchema(**data)


class RewriterService:
    """응답 재작성 서비스."""
    
    def __init__(self, client: Any, config: AppConfig):
        """초기화."""
        self.client = client
        self.config = config
    
    async def rewrite_response(
        self,
        original_response: str,
        feedback: str,
        style: str = "formal"
    ) -> str:
        """응답 재작성.
        
        Args:
            original_response: 원본 응답
            feedback: 개선 피드백
            style: 작성 스타일
            
        Returns:
            재작성된 응답
        """
        prompt = self._build_rewrite_prompt(original_response, feedback, style)
        result = await self.client.generate_content(prompt)
        return result.text.strip()
    
    def _build_rewrite_prompt(
        self,
        original_response: str,
        feedback: str,
        style: str
    ) -> str:
        """재작성 프롬프트 빌드."""
        return f"""다음 응답을 피드백에 따라 개선하여 재작성하세요.

원본 응답:
{original_response}

피드백:
{feedback}

스타일: {style}

요구사항:
1. 피드백의 모든 사항을 반영
2. {style} 스타일로 작성
3. 명확하고 간결하게
4. 원본의 핵심 내용 유지

재작성된 응답만 출력하세요 (설명 없이).
"""
```

**Step 2**: Simplify `src/agent/core.py` to be a coordinator

```python
"""Gemini Agent 핵심 모듈 - Simplified Coordinator."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.config import AppConfig
from src.core.models import EvaluationResultSchema

from .cache_manager import CacheManager
from .client import GeminiClient
from .context_manager import AgentContextManager
from .cost_tracker import CostTracker
from .rate_limiter import RateLimiter
from .services import (
    QueryGeneratorService,
    ResponseEvaluatorService,
    RewriterService,
)

logger = logging.getLogger(__name__)


class GeminiAgent:
    """Gemini Agent Coordinator.
    
    모든 비즈니스 로직은 services.py에 위임하고,
    이 클래스는 조정자 역할만 수행합니다.
    """
    
    def __init__(self, config: AppConfig):
        """초기화."""
        self.config = config
        
        # Initialize components
        self.client = GeminiClient(config)
        self.cache_manager = CacheManager(config)
        self.cost_tracker = CostTracker(config)
        self.rate_limiter = RateLimiter(config)
        self.context_manager = AgentContextManager(config)
        
        # Initialize services
        self.query_generator = QueryGeneratorService(self.client, config)
        self.evaluator = ResponseEvaluatorService(self.client, config)
        self.rewriter = RewriterService(self.client, config)
        
        logger.info("GeminiAgent initialized")
    
    async def generate_queries(
        self,
        ocr_text: str,
        user_intent: str = "",
        num_queries: int = 5
    ) -> List[str]:
        """질의 생성 (서비스로 위임)."""
        async with self.rate_limiter:
            return await self.query_generator.generate_queries(
                ocr_text, user_intent, num_queries
            )
    
    async def evaluate_response(
        self,
        query: str,
        response: str,
        criteria: Optional[Dict[str, Any]] = None,
        timeout: int = 30
    ) -> EvaluationResultSchema:
        """응답 평가 (서비스로 위임)."""
        async with self.rate_limiter:
            result = await self.evaluator.evaluate_response(
                query, response, criteria
            )
            # Track cost
            self.cost_tracker.track(result.tokens_used if hasattr(result, 'tokens_used') else 0)
            return result
    
    async def rewrite_response(
        self,
        original_response: str,
        feedback: str,
        style: str = "formal"
    ) -> str:
        """응답 재작성 (서비스로 위임)."""
        async with self.rate_limiter:
            return await self.rewriter.rewrite_response(
                original_response, feedback, style
            )
    
    async def close(self) -> None:
        """리소스 정리."""
        await self.client.close()
        logger.info("GeminiAgent closed")
```

#### Verification:
- Run: `mypy src/agent/`
- Run: `pytest tests/unit/agent/ -v`
- Expected: All type checks pass, agent tests pass

**✅ After completing this prompt, proceed to [PROMPT-005]**

---

## 🟢 Priority 3 (Medium) - Execute Last

### [PROMPT-005] Performance Monitoring Dashboard

> **⏱️ Execute this prompt now**

**Task**: Implement real-time performance monitoring dashboard
**Files to Create**:
- `src/analytics/realtime_dashboard.py`
- `src/monitoring/metrics_exporter.py`
- `config/grafana_dashboard.json` (template)

#### Instructions:

1. Create dashboard module with Prometheus metrics export
2. Add Grafana dashboard configuration template
3. Implement alert system for budget and error rate

#### Implementation Steps:

**Step 1**: Create `src/analytics/realtime_dashboard.py`

```python
"""실시간 성능 모니터링 대시보드."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)


@dataclass
class DashboardMetrics:
    """대시보드 메트릭."""
    
    # API Latency
    latency_p50: float
    latency_p90: float
    latency_p99: float
    
    # Token Usage
    total_tokens: int
    cache_hit_rate: float
    
    # Cost
    total_cost: float
    cost_per_query: float
    
    # Error Rate
    error_count: int
    error_rate: float


class RealtimeDashboard:
    """실시간 대시보드.
    
    Prometheus 메트릭을 수집하고 Grafana로 시각화합니다.
    """
    
    def __init__(self):
        """초기화."""
        # Define metrics
        self.api_latency = Histogram(
            "gemini_api_latency_seconds",
            "API 호출 레이턴시",
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
        )
        
        self.token_usage = Counter(
            "gemini_tokens_used_total",
            "총 토큰 사용량",
            ["type"]  # input, output, cache
        )
        
        self.cache_hits = Counter(
            "gemini_cache_hits_total",
            "캐시 히트 수"
        )
        
        self.cache_misses = Counter(
            "gemini_cache_misses_total",
            "캐시 미스 수"
        )
        
        self.total_cost = Gauge(
            "gemini_total_cost_usd",
            "총 비용 (USD)"
        )
        
        self.error_count = Counter(
            "gemini_errors_total",
            "에러 발생 수",
            ["error_type"]
        )
        
        self.budget_remaining = Gauge(
            "gemini_budget_remaining_usd",
            "남은 예산 (USD)"
        )
        
        logger.info("Realtime dashboard initialized")
    
    def record_api_call(self, latency: float) -> None:
        """API 호출 기록."""
        self.api_latency.observe(latency)
    
    def record_token_usage(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_tokens: int = 0
    ) -> None:
        """토큰 사용량 기록."""
        if input_tokens > 0:
            self.token_usage.labels(type="input").inc(input_tokens)
        if output_tokens > 0:
            self.token_usage.labels(type="output").inc(output_tokens)
        if cache_tokens > 0:
            self.token_usage.labels(type="cache").inc(cache_tokens)
    
    def record_cache_result(self, hit: bool) -> None:
        """캐시 결과 기록."""
        if hit:
            self.cache_hits.inc()
        else:
            self.cache_misses.inc()
    
    def update_cost(self, cost: float) -> None:
        """비용 업데이트."""
        self.total_cost.set(cost)
    
    def update_budget(self, remaining: float) -> None:
        """남은 예산 업데이트."""
        self.budget_remaining.set(remaining)
    
    def record_error(self, error_type: str) -> None:
        """에러 기록."""
        self.error_count.labels(error_type=error_type).inc()
    
    def get_metrics_summary(self) -> DashboardMetrics:
        """메트릭 요약 반환."""
        # This is a simplified version
        # In production, you'd query Prometheus for percentiles
        return DashboardMetrics(
            latency_p50=0.0,  # Calculate from histogram
            latency_p90=0.0,
            latency_p99=0.0,
            total_tokens=0,  # Sum from counter
            cache_hit_rate=0.0,  # Calculate from hits/misses
            total_cost=0.0,
            cost_per_query=0.0,
            error_count=0,
            error_rate=0.0
        )


# Global dashboard instance
_dashboard = RealtimeDashboard()


def get_dashboard() -> RealtimeDashboard:
    """대시보드 인스턴스 반환."""
    return _dashboard
```

**Step 2**: Create `src/monitoring/metrics_exporter.py`

```python
"""Prometheus 메트릭 익스포터."""

from __future__ import annotations

import logging
from typing import Optional

from prometheus_client import start_http_server

logger = logging.getLogger(__name__)


class MetricsExporter:
    """메트릭 익스포터.
    
    Prometheus가 스크랩할 수 있도록 HTTP 엔드포인트를 제공합니다.
    """
    
    def __init__(self, port: int = 9090):
        """초기화.
        
        Args:
            port: 메트릭 서버 포트
        """
        self.port = port
        self.server: Optional[any] = None
    
    def start(self) -> None:
        """메트릭 서버 시작."""
        try:
            start_http_server(self.port)
            logger.info(f"Metrics server started on port {self.port}")
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")
            raise
    
    def stop(self) -> None:
        """메트릭 서버 중지."""
        # prometheus_client doesn't provide a stop method
        # Server will stop when process exits
        logger.info("Metrics server will stop with process")


# Global exporter instance
_exporter: Optional[MetricsExporter] = None


def start_metrics_exporter(port: int = 9090) -> MetricsExporter:
    """메트릭 익스포터 시작."""
    global _exporter
    if _exporter is None:
        _exporter = MetricsExporter(port)
        _exporter.start()
    return _exporter
```

**Step 3**: Create `config/grafana_dashboard.json`

```json
{
  "dashboard": {
    "title": "Gemini API Performance",
    "panels": [
      {
        "title": "API Latency (p50/p90/p99)",
        "targets": [
          {
            "expr": "histogram_quantile(0.50, rate(gemini_api_latency_seconds_bucket[5m]))",
            "legendFormat": "p50"
          },
          {
            "expr": "histogram_quantile(0.90, rate(gemini_api_latency_seconds_bucket[5m]))",
            "legendFormat": "p90"
          },
          {
            "expr": "histogram_quantile(0.99, rate(gemini_api_latency_seconds_bucket[5m]))",
            "legendFormat": "p99"
          }
        ]
      },
      {
        "title": "Token Usage",
        "targets": [
          {
            "expr": "rate(gemini_tokens_used_total{type=\"input\"}[5m])",
            "legendFormat": "Input Tokens/sec"
          },
          {
            "expr": "rate(gemini_tokens_used_total{type=\"output\"}[5m])",
            "legendFormat": "Output Tokens/sec"
          }
        ]
      },
      {
        "title": "Cache Hit Rate",
        "targets": [
          {
            "expr": "rate(gemini_cache_hits_total[5m]) / (rate(gemini_cache_hits_total[5m]) + rate(gemini_cache_misses_total[5m]))",
            "legendFormat": "Hit Rate"
          }
        ]
      },
      {
        "title": "Total Cost (USD)",
        "targets": [
          {
            "expr": "gemini_total_cost_usd",
            "legendFormat": "Total Cost"
          }
        ]
      },
      {
        "title": "Budget Remaining (USD)",
        "targets": [
          {
            "expr": "gemini_budget_remaining_usd",
            "legendFormat": "Remaining Budget"
          }
        ]
      },
      {
        "title": "Error Rate",
        "targets": [
          {
            "expr": "rate(gemini_errors_total[5m])",
            "legendFormat": "Errors/sec"
          }
        ]
      }
    ]
  }
}
```

#### Verification:
- Run: `mypy src/analytics/ src/monitoring/`
- Run: `pytest tests/unit/analytics/ tests/unit/monitoring/ -v` (if tests exist)
- Check: Metrics endpoint accessible at `http://localhost:9090/metrics`
- Expected: All type checks pass, metrics exported correctly

**🎉 ALL PROMPTS COMPLETED! Run final verification.**

---

## 📊 Final Verification Steps

After completing all prompts:

1. **Run full type check**: `mypy src/`
2. **Run all tests**: `pytest tests/ -v`
3. **Check code quality**: `ruff check src/`
4. **Verify coverage**: `pytest --cov=src --cov-report=html`
5. **Check file sizes**: Verify all target files are under 500 lines
6. **Manual review**: Review split modules for logical cohesion

---

**Last Updated**: 2025-12-05 16:30  
**Status**: 🟡 4 pending improvements (3 P2, 1 P3)  
**Next Review**: After applying improvements
