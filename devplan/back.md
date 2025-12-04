제공해주신 내용은 마크다운 코드 블록(` ``` `)이 중첩되거나 닫히지 않아 형식이 깨진 것으로 보입니다.

아래에 **올바른 마크다운 형식으로 수정한 전문**을 정리해 드립니다. 이를 그대로 복사하여 노션(Notion), 깃허브(GitHub), 또는 문서 도구에 붙여넣으시면 됩니다.

---

# hamtoy/Test web.api 백엔드 개선 작업 (최종 검증판)

## ⚠️ 적용 전 필수 사전 조사

### 1. 현재 코드베이스 스냅샷
```bash
# 1.1 기존 workflow 모듈 구조
ls -la src/workflow/
# 예상 출력: edit.py, inspection.py 등
# 확인: executor.py, unified_executor.py 등 충돌 가능 파일

# 1.2 현재 의존성 확인
cat pyproject.toml | grep -A 50 "dependencies"
# tenacity, jinja2, fastapi 버전 확인

# 1.3 기존 검증 로직 파악
find src/qa -name "*valid*.py" -o -name "*check*.py"
# UnifiedValidator, IntegratedQAPipeline.validate_output 위치 확인

# 1.4 현재 Agent/Pipeline 시그니처 확인
grep -A 5 "class GeminiAgent" src/agent/*.py
grep -A 5 "class IntegratedQAPipeline" src/qa/pipeline.py
grep -A 3 "def __init__" src/agent/*.py | head -20
```

### 2. 테스트 커버리지 확인
```bash
# 현재 테스트 실행
pytest tests/ -v --tb=short

# 특정 모듈 테스트 확인
pytest tests/web/ -v
pytest tests/workflow/ -v 2>/dev/null || echo "workflow 테스트 없음"
```

### 3. API 계약 확인
```bash
# 클라이언트가 사용하는 엔드포인트 확인
grep -r "/workspace" static/*.js templates/*.html
grep -r "api_unified_workspace" tests/

# 현재 응답 스키마 확인
grep -A 10 "class.*Request" src/web/models.py
grep -A 10 "class.*Response" src/web/models.py
```

---

## Phase 0: 기존 시그니처 검증 (필수)

### 실제 코드와 맞추기

#### src/agent/__init__.py 또는 src/agent/agent.py 확인
```python
# 실제 GeminiAgent 초기화 확인
class GeminiAgent:
    def __init__(
        self,
        config: AppConfig,
        jinja_env: Environment,  # ← 이 파라미터 이름 확인
        # 다른 파라미터가 있는지 확인
    ):
        ...
```

#### src/qa/pipeline.py 확인
```python
# 실제 IntegratedQAPipeline 초기화 확인
class IntegratedQAPipeline:
    def __init__(
        self,
        # 파라미터 확인 (kg 필요한지, config 필요한지)
    ):
        ...
```

#### src/qa/rag_system.py 확인
```python
# QAKnowledgeGraph 초기화 확인
class QAKnowledgeGraph:
    def __init__(
        self,
        # URI, user, password를 받는지
        # 아니면 환경변수에서 자동으로 읽는지
    ):
        ...
```

---

## Phase 1: 서비스 레지스트리 도입 (1-2일)

### 1.1 ServiceRegistry 구현

#### src/web/service_registry.py (신규)
```python
"""서비스 레지스트리 - 싱글톤 패턴."""
from __future__ import annotations
from typing import Optional, TYPE_CHECKING
import threading
import logging

if TYPE_CHECKING:
    from src.config import AppConfig
    from src.agent import GeminiAgent
    from src.qa.rag_system import QAKnowledgeGraph
    from src.qa.pipeline import IntegratedQAPipeline

logger = logging.getLogger(__name__)


class ServiceRegistry:
    """스레드 안전 서비스 레지스트리."""
    
    def __init__(self):
        self._config: Optional[AppConfig] = None
        self._agent: Optional[GeminiAgent] = None
        self._kg: Optional[QAKnowledgeGraph] = None
        self._pipeline: Optional[IntegratedQAPipeline] = None
        self._lock = threading.Lock()
    
    def register_config(self, config: AppConfig) -> None:
        with self._lock:
            self._config = config
            logger.debug("Config registered")
    
    def register_agent(self, agent: GeminiAgent) -> None:
        with self._lock:
            self._agent = agent
            logger.debug("Agent registered")
    
    def register_kg(self, kg: Optional[QAKnowledgeGraph]) -> None:
        with self._lock:
            self._kg = kg
            logger.debug("KG registered: %s", kg is not None)
    
    def register_pipeline(self, pipeline: Optional[IntegratedQAPipeline]) -> None:
        with self._lock:
            self._pipeline = pipeline
            logger.debug("Pipeline registered: %s", pipeline is not None)
    
    @property
    def config(self) -> AppConfig:
        if self._config is None:
            raise RuntimeError("Config not registered. Call init_resources first.")
        return self._config
    
    @property
    def agent(self) -> GeminiAgent:
        if self._agent is None:
            raise RuntimeError("Agent not registered. Call init_resources first.")
        return self._agent
    
    @property
    def kg(self) -> Optional[QAKnowledgeGraph]:
        return self._kg
    
    @property
    def pipeline(self) -> Optional[IntegratedQAPipeline]:
        return self._pipeline
    
    def is_initialized(self) -> bool:
        """초기화 여부 확인."""
        return (
            self._config is not None
            and self._agent is not None
        )
    
    def clear(self) -> None:
        """테스트용 초기화 - 프로덕션에서는 사용 금지."""
        with self._lock:
            self._config = None
            self._agent = None
            self._kg = None
            self._pipeline = None
            logger.warning("ServiceRegistry cleared (test mode only)")


# 전역 싱글톤 인스턴스
_registry = ServiceRegistry()


def get_registry() -> ServiceRegistry:
    """레지스트리 접근자."""
    return _registry


def reset_registry_for_test() -> None:
    """테스트 전용 - 레지스트리 초기화."""
    _registry.clear()
```

### 1.2 api.py 수정

#### src/web/api.py (수정)
```python
# ===== 기존 전역 변수 제거 =====
# 삭제: _config, agent, kg, pipeline
# 삭제: get_config() 함수

from src.web.service_registry import get_registry

# ===== init_resources 수정 =====
async def init_resources() -> None:
    """리소스 초기화 - ServiceRegistry 사용."""
    registry = get_registry()
    
    # 이미 초기화되었으면 스킵
    if registry.is_initialized():
        logger.info("Resources already initialized")
        return
    
    # 1. Config 등록
    app_config = AppConfig()
    registry.register_config(app_config)
    logger.info("Config registered")
    
    # 2. Agent 등록
    from jinja2 import Environment, FileSystemLoader
    
    jinja_env = Environment(
        loader=FileSystemLoader(str(REPO_ROOT / "templates")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    
    # ⚠️ 실제 GeminiAgent 시그니처에 맞춰 수정 필요
    gemini_agent = GeminiAgent(
        config=app_config,
        jinja_env=jinja_env,
        # 추가 파라미터가 있다면 여기 추가
    )
    registry.register_agent(gemini_agent)
    logger.info("GeminiAgent initialized")
    
    # 3. KG 등록
    try:
        # ⚠️ 실제 QAKnowledgeGraph 시그니처 확인
        knowledge_graph = QAKnowledgeGraph()
        registry.register_kg(knowledge_graph)
        logger.info("QAKnowledgeGraph initialized")
    except Exception as e:
        logger.warning("Neo4j connection failed (RAG disabled): %s", e)
        registry.register_kg(None)
    
    # 4. Pipeline 등록
    try:
        # ⚠️ 실제 IntegratedQAPipeline 시그니처 확인
        qa_pipeline = IntegratedQAPipeline()
        registry.register_pipeline(qa_pipeline)
        logger.info("IntegratedQAPipeline initialized")
    except Exception as e:
        logger.warning("Pipeline init failed: %s", e)
        registry.register_pipeline(None)
    
    # 5. 라우터 의존성 주입
    # ⚠️ 각 모듈의 set_dependencies 시그니처 확인 필요
    qa_router_module.set_dependencies(
        registry.config,
        registry.agent,
        registry.pipeline,
        registry.kg,
    )
    workspace_router_module.set_dependencies(
        registry.config,
        registry.agent,
        registry.kg,
        registry.pipeline,
    )
    stream_router_module.set_dependencies(
        registry.config,
        registry.agent,
    )
    health_router_module.set_dependencies(
        health_checker,
        agent=registry.agent,
        kg=registry.kg,
        pipeline=registry.pipeline,
    )

# ===== OCR 헬퍼 함수 수정 =====
def load_ocr_text() -> str:
    """Load OCR text from persisted storage."""
    registry = get_registry()
    return _load_ocr_text(registry.config)


def save_ocr_text(text: str) -> None:
    """Persist OCR text to storage."""
    registry = get_registry()
    _save_ocr_text(registry.config, text)
```

### 1.3 라우터 수정

#### src/web/routers/workspace.py (수정)
```python
# ===== 전역 변수 완전 제거 =====
# 삭제: _config, agent, kg, pipeline, _validator, _service
# 삭제: set_dependencies 함수
# 삭제: _get_agent, _get_kg, _get_pipeline, _get_config 함수

from src.web.service_registry import get_registry

# ===== 엔드포인트 수정 예시 =====
@router.post("/workspace/unified")
async def api_unified_workspace(body: UnifiedWorkspaceRequest) -> Dict[str, Any]:
    """통합 워크스페이스 - ServiceRegistry 사용."""
    registry = get_registry()
    
    # 필요한 서비스 가져오기
    config = registry.config
    agent = registry.agent
    kg = registry.kg
    pipeline = registry.pipeline
    
    # OCR 텍스트 로드
    ocr_text = body.ocr_text or load_ocr_text()
    
    # 기존 로직 유지
    # ... (detect_workflow, 프롬프트 생성 등)
    
    # 예시: 간단한 워크플로우 실행
    try:
        # ⚠️ 기존 로직을 여기 유지하거나
        # Phase 2에서 WorkspaceExecutor로 이동
        pass
    except Exception as e:
        logger.error("Workflow failed: %s", e)
        raise HTTPException(500, detail=str(e))
```

### 1.4 테스트 작성

#### tests/web/test_service_registry.py (신규)
```python
"""ServiceRegistry 테스트."""
import pytest
from src.web.service_registry import (
    ServiceRegistry,
    get_registry,
    reset_registry_for_test,
)
from src.config import AppConfig


def test_service_registry_singleton():
    """싱글톤 패턴 확인."""
    r1 = get_registry()
    r2 = get_registry()
    assert r1 is r2


def test_service_registry_register_config():
    """Config 등록 테스트."""
    reset_registry_for_test()
    registry = get_registry()
    
    config = AppConfig()
    registry.register_config(config)
    
    assert registry.config == config


def test_service_registry_uninitialized_error():
    """초기화 전 접근 시 에러."""
    reset_registry_for_test()
    registry = get_registry()
    
    with pytest.raises(RuntimeError, match="Config not registered"):
        _ = registry.config


def test_service_registry_is_initialized():
    """초기화 상태 확인."""
    reset_registry_for_test()
    registry = get_registry()
    
    assert not registry.is_initialized()
    
    # Config만 등록
    registry.register_config(AppConfig())
    assert not registry.is_initialized()  # Agent도 필요
    
    # Agent 등록 (mock)
    from unittest.mock import Mock
    registry.register_agent(Mock())
    assert registry.is_initialized()


def test_service_registry_clear():
    """Clear 테스트."""
    reset_registry_for_test()
    registry = get_registry()
    
    registry.register_config(AppConfig())
    assert registry._config is not None
    
    registry.clear()
    assert registry._config is None
```

### 1.5 기존 테스트 업데이트

#### tests/conftest.py (수정)
```python
"""테스트 픽스처."""
import pytest
from src.web.service_registry import reset_registry_for_test


@pytest.fixture(autouse=True)
def reset_registry():
    """각 테스트 전 레지스트리 초기화."""
    reset_registry_for_test()
    yield
    reset_registry_for_test()


@pytest.fixture
def mock_registry():
    """Mock ServiceRegistry."""
    from unittest.mock import Mock
    from src.web.service_registry import get_registry
    
    registry = get_registry()
    registry.register_config(Mock())
    registry.register_agent(Mock())
    registry.register_kg(None)
    registry.register_pipeline(None)
    
    return registry
```

---

## Phase 2: 워크스페이스 로직 분리 (3-5일)

### 2.1 파일명 충돌 확인 및 결정
```bash
# 기존 파일 확인
ls -la src/workflow/

# 출력 예시:
# edit.py
# inspection.py
# (executor.py가 없다면 그대로 사용 가능)

# executor.py가 이미 있다면:
# - workspace_executor.py 사용
# - 또는 qa_executor.py 사용
```

### 2.2 WorkspaceExecutor 구현

#### src/workflow/workspace_executor.py (신규)
```python
"""워크스페이스 워크플로우 실행기."""
from __future__ import annotations
from enum import Enum
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from dataclasses import dataclass
import logging
import re

if TYPE_CHECKING:
    from src.agent import GeminiAgent
    from src.qa.rag_system import QAKnowledgeGraph
    from src.qa.pipeline import IntegratedQAPipeline
    from src.config import AppConfig

logger = logging.getLogger(__name__)


class WorkflowType(Enum):
    """워크플로우 타입."""
    FULL_GENERATION = "full_generation"
    QUERY_GENERATION = "query_generation"
    ANSWER_GENERATION = "answer_generation"
    REWRITE = "rewrite"
    EDIT_QUERY = "edit_query"
    EDIT_ANSWER = "edit_answer"
    EDIT_BOTH = "edit_both"


@dataclass
class WorkflowContext:
    """워크플로우 실행 컨텍스트."""
    query: str
    answer: str
    ocr_text: str
    query_type: str
    edit_request: str
    global_explanation_ref: str
    use_lats: bool


@dataclass
class WorkflowResult:
    """워크플로우 실행 결과."""
    workflow: str
    query: str
    answer: str
    changes: List[str]
    query_type: str


class WorkspaceExecutor:
    """워크스페이스 워크플로우 실행 엔진."""
    
    def __init__(
        self,
        agent: GeminiAgent,
        kg: Optional[QAKnowledgeGraph],
        pipeline: Optional[IntegratedQAPipeline],
        config: AppConfig,
    ):
        self.agent = agent
        self.kg = kg
        self.pipeline = pipeline
        self.config = config
    
    async def execute(
        self,
        workflow: WorkflowType,
        context: WorkflowContext,
    ) -> WorkflowResult:
        """워크플로우 실행."""
        logger.info(
            "Executing workflow: %s (qtype=%s)",
            workflow.value,
            context.query_type
        )
        
        handlers = {
            WorkflowType.FULL_GENERATION: self._handle_full_generation,
            WorkflowType.QUERY_GENERATION: self._handle_query_generation,
            WorkflowType.ANSWER_GENERATION: self._handle_answer_generation,
            WorkflowType.REWRITE: self._handle_rewrite,
            WorkflowType.EDIT_QUERY: self._handle_edit_query,
            WorkflowType.EDIT_ANSWER: self._handle_edit_answer,
            WorkflowType.EDIT_BOTH: self._handle_edit_both,
        }
        
        handler = handlers.get(workflow)
        if handler is None:
            raise ValueError(f"Unknown workflow: {workflow}")
        
        return await handler(context)
    
    async def _handle_full_generation(
        self, ctx: WorkflowContext
    ) -> WorkflowResult:
        """전체 생성 워크플로우."""
        changes: List[str] = ["OCR에서 전체 생성"]
        
        # 1. 질의 생성
        query_intent = self._get_query_intent(
            ctx.query_type,
            ctx.global_explanation_ref
        )
        
        queries = await self.agent.generate_query(
            ctx.ocr_text,
            user_intent=query_intent,
            query_type=ctx.query_type,
            kg=self.kg,
        )
        
        query = queries if queries else "질문 생성 실패"
        
        # 타겟 단답은 짧게
        if ctx.query_type == "target_short":
            query = self._shorten_query(query)
        
        changes.append("질의 생성 완료")
        
        # 2. 답변 생성
        # ⚠️ 기존 workspace.py의 프롬프트 생성 로직을 여기로 이동
        # 또는 Phase 3에서 템플릿으로 분리
        answer = await self._generate_answer(ctx, query)
        changes.append("답변 생성 완료")
        
        return WorkflowResult(
            workflow="full_generation",
            query=query,
            answer=answer,
            changes=changes,
            query_type=ctx.query_type,
        )
    
    async def _handle_query_generation(
        self, ctx: WorkflowContext
    ) -> WorkflowResult:
        """질의 생성 워크플로우."""
        changes: List[str] = ["질문 생성 요청"]
        
        query_intent = self._get_query_intent(
            ctx.query_type,
            ctx.global_explanation_ref
        )
        
        queries = await self.agent.generate_query(
            ctx.ocr_text,
            user_intent=query_intent,
            query_type=ctx.query_type,
            kg=self.kg,
        )
        
        query = queries if queries else "질문 생성 실패"
        
        if ctx.query_type == "target_short":
            query = self._shorten_query(query)
        
        changes.append("질문 생성 완료")
        
        return WorkflowResult(
            workflow="query_generation",
            query=query,
            answer=ctx.answer,  # 기존 답변 유지
            changes=changes,
            query_type=ctx.query_type,
        )
    
    async def _handle_answer_generation(
        self, ctx: WorkflowContext
    ) -> WorkflowResult:
        """답변 생성 워크플로우."""
        changes: List[str] = ["답변 생성 요청"]
        
        answer = await self._generate_answer(ctx, ctx.query)
        changes.append("답변 생성 완료")
        
        return WorkflowResult(
            workflow="answer_generation",
            query=ctx.query,
            answer=answer,
            changes=changes,
            query_type=ctx.query_type,
        )
    
    async def _handle_rewrite(
        self, ctx: WorkflowContext
    ) -> WorkflowResult:
        """재작성 워크플로우."""
        changes: List[str] = ["답변 재작성 요청"]
        
        # edit_content 사용
        from src.workflow.edit import edit_content
        
        answer = await edit_content(
            agent=self.agent,
            answer=ctx.answer,
            ocr_text=ctx.ocr_text,
            query=ctx.query,
            edit_request="형식/길이 위반을 자동 교정",
            kg=self.kg,
            cache=None,
        )
        
        changes.append("재작성 완료")
        
        return WorkflowResult(
            workflow="rewrite",
            query=ctx.query,
            answer=answer,
            changes=changes,
            query_type=ctx.query_type,
        )
    
    async def _handle_edit_query(
        self, ctx: WorkflowContext
    ) -> WorkflowResult:
        """질의 수정 워크플로우."""
        changes: List[str] = ["질의 수정 요청"]
        
        from src.workflow.edit import edit_content
        
        edited_query = await edit_content(
            agent=self.agent,
            answer=ctx.query,
            ocr_text=ctx.ocr_text,
            query="",
            edit_request=ctx.edit_request,
            kg=self.kg,
            cache=None,
        )
        
        changes.append("질의 수정 완료")
        
        return WorkflowResult(
            workflow="edit_query",
            query=edited_query,
            answer=ctx.answer,
            changes=changes,
            query_type=ctx.query_type,
        )
    
    async def _handle_edit_answer(
        self, ctx: WorkflowContext
    ) -> WorkflowResult:
        """답변 수정 워크플로우."""
        changes: List[str] = [f"답변 수정 요청: {ctx.edit_request}"]
        
        from src.workflow.edit import edit_content
        
        edited_answer = await edit_content(
            agent=self.agent,
            answer=ctx.answer,
            ocr_text=ctx.ocr_text,
            query=ctx.query,
            edit_request=ctx.edit_request,
            kg=self.kg,
            cache=None,
        )
        
        changes.append("답변 수정 완료")
        
        return WorkflowResult(
            workflow="edit_answer",
            query=ctx.query,
            answer=edited_answer,
            changes=changes,
            query_type=ctx.query_type,
        )
    
    async def _handle_edit_both(
        self, ctx: WorkflowContext
    ) -> WorkflowResult:
        """질의+답변 수정 워크플로우."""
        changes: List[str] = [f"질의+답변 수정 요청: {ctx.edit_request}"]
        
        from src.workflow.edit import edit_content
        
        # 답변 수정
        edited_answer = await edit_content(
            agent=self.agent,
            answer=ctx.answer,
            ocr_text=ctx.ocr_text,
            query=ctx.query,
            edit_request=ctx.edit_request,
            kg=self.kg,
            cache=None,
        )
        changes.append("답변 수정 완료")
        
        # 질의 조정
        edited_query = await edit_content(
            agent=self.agent,
            answer=ctx.query,
            ocr_text=ctx.ocr_text,
            query="",
            edit_request=f"다음 답변에 맞게 질의 조정: {edited_answer[:200]}...",
            kg=self.kg,
            cache=None,
        )
        changes.append("질의 조정 완료")
        
        return WorkflowResult(
            workflow="edit_both",
            query=edited_query,
            answer=edited_answer,
            changes=changes,
            query_type=ctx.query_type,
        )
    
    # === 헬퍼 메서드 ===
    
    def _get_query_intent(
        self, query_type: str, global_ref: str
    ) -> Optional[str]:
        """쿼리 타입별 인텐트 생성."""
        intents = {
            "target_short": "간단한 사실 확인 질문",
            "target_long": "핵심 요점을 묻는 질문",
            "reasoning": "추론/예측 질문",
            "global_explanation": "전체 내용 설명 질문",
        }
        
        base_intent = intents.get(query_type)
        
        # 중복 방지 추가
        if global_ref and query_type in {"target_short", "target_long"}:
            base_intent += f"""

[중복 방지 필수]
다음 전체 설명문에서 이미 다룬 내용과 중복되지 않는 새로운 세부 사실/수치를 질문하세요:
***
{global_ref[:500]}
---"""
        
        return base_intent
    
    def _shorten_query(self, text: str) -> str:
        """타겟 단답용 질의 압축."""
        clean = re.sub(r"\s+", " ", text or "").strip()
        parts = re.split(r"[?.!]\s*", clean)
        candidate = parts if parts and parts else clean
        words = candidate.split()
        if len(words) > 20:
            candidate = " ".join(words[:20])
        return candidate.strip()
    
    async def _generate_answer(
        self, ctx: WorkflowContext, query: str
    ) -> str:
        """답변 생성 (공통 로직)."""
        # ⚠️ 기존 workspace.py의 답변 생성 로직을 여기로 이동
        # 또는 Phase 3에서 템플릿으로 분리
        
        # 임시 구현 (실제로는 프롬프트 생성 + agent 호출)
        prompt = f"""[질의]
{query}

[OCR 텍스트]
{ctx.ocr_text[:2000]}

위 OCR 텍스트를 기반으로 답변을 작성하세요."""
        
        answer = await self.agent.rewrite_best_answer(
            ocr_text=ctx.ocr_text,
            best_answer=prompt,
            cached_content=None,
            query_type=ctx.query_type,
        )
        
        # 후처리
        from src.web.utils import strip_output_tags, postprocess_answer
        answer = strip_output_tags(answer)
        answer = postprocess_answer(answer, ctx.query_type)
        
        return answer
```

### 2.3 라우터에서 Executor 사용

#### src/web/routers/workspace.py (수정)
```python
from src.workflow.workspace_executor import (
    WorkspaceExecutor,
    WorkflowType,
    WorkflowContext,
)
from src.web.service_registry import get_registry
from src.web.utils import detect_workflow
import asyncio

@router.post("/workspace/unified")
async def api_unified_workspace(body: UnifiedWorkspaceRequest) -> Dict[str, Any]:
    """통합 워크스페이스."""
    registry = get_registry()
    meta_start = datetime.now()
    
    # OCR 텍스트
    ocr_text = body.ocr_text or load_ocr_text(registry.config)
    
    # 워크플로우 감지
    workflow_str = detect_workflow(
        body.query or "",
        body.answer or "",
        body.edit_request or ""
    )
    workflow_type = WorkflowType(workflow_str)
    
    # 컨텍스트 구성
    context = WorkflowContext(
        query=body.query or "",
        answer=body.answer or "",
        ocr_text=ocr_text,
        query_type=body.query_type or "global_explanation",
        edit_request=body.edit_request or "",
        global_explanation_ref=body.global_explanation_ref or "",
        use_lats=body.use_lats or False,
    )
    
    # Executor 생성 및 실행
    executor = WorkspaceExecutor(
        registry.agent,
        registry.kg,
        registry.pipeline,
        registry.config,
    )
    
    try:
        result = await asyncio.wait_for(
            executor.execute(workflow_type, context),
            timeout=registry.config.workspace_unified_timeout
        )
        
        # 결과를 Dict로 변환
        result_dict = {
            "workflow": result.workflow,
            "query": result.query,
            "answer": result.answer,
            "changes": result.changes,
            "query_type": result.query_type,
        }
        
        # 응답 구성
        duration = (datetime.now() - meta_start).total_seconds()
        meta = APIMetadata(duration=duration)
        
        return build_response(
            result_dict,
            metadata=meta,
            config=registry.config
        )
    
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"워크플로우 시간 초과 ({registry.config.workspace_unified_timeout}초)"
        )
    except ValueError as e:
        # 잘못된 워크플로우 타입 등
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Workflow execution failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="워크플로우 실행 중 오류가 발생했습니다."
        )
```

---

## Phase 3-7: 나머지 개선 사항

### 간략 체크리스트
- [ ] **Phase 3**: 프롬프트 템플릿 외부화 (templates/prompts/workspace/)
- [ ] **Phase 4**: 검증 레이어 통합 (src/qa/validator.py 확장)
- [ ] **Phase 5**: 에러 처리 개선 (src/web/exceptions.py)
- [ ] **Phase 6**: 재시도 로직 (src/infra/retry.py)
- [ ] **Phase 7**: 캐싱 개선 (RuleLoader 메모이제이션)

*(상세 구현은 기존 devplan/back.md Phase 3-7 참조)*

---

## 최종 검증 체크리스트

### 적용 전
- [ ] `src/workflow/executor.py` 충돌 확인 완료
- [ ] `GeminiAgent.__init__` 시그니처 확인 완료
- [ ] `IntegratedQAPipeline.__init__` 시그니처 확인 완료
- [ ] `QAKnowledgeGraph.__init__` 시그니처 확인 완료
- [ ] 기존 테스트 전체 통과 확인

### Phase 1 적용 후
- [ ] `pytest tests/web/test_service_registry.py -v` 통과
- [ ] `pytest tests/ -v` 전체 통과
- [ ] 로컬 서버 기동 (`uvicorn src.web.api:app --reload`)
- [ ] `/health` 엔드포인트 정상 응답
- [ ] `/workspace` 페이지 로드 확인

### Phase 2 적용 후
- [ ] `WorkspaceExecutor` 단위 테스트 작성 및 통과
- [ ] `/api/workspace/unified` POST 요청 테스트
- [ ] 기존 클라이언트 동작 확인 (static/app.js)
- [ ] 기존 테스트 전체 통과

### 성능 비교
```bash
# 개선 전
time curl -X POST http://localhost:8000/api/workspace/unified \
  -H "Content-Type: application/json" \
  -d '{"query":"test","answer":"test","ocr_text":"test"}'

# 개선 후 (동일 요청 반복)
```

---

## 롤백 계획

### Phase 1 롤백
```bash
git checkout HEAD -- src/web/service_registry.py
git checkout HEAD -- src/web/api.py
git checkout HEAD -- src/web/routers/workspace.py
pytest tests/ -v  # 롤백 후 테스트 확인
```

### Phase 2 롤백
```bash
git checkout HEAD -- src/workflow/workspace_executor.py
git checkout HEAD -- src/web/routers/workspace.py
pytest tests/ -v
```

---

## 추가 주의사항

### 멀티프로세스 환경
- ServiceRegistry는 프로세스당 하나의 인스턴스만 유지
- Gunicorn 등 멀티워커 환경에서는 각 워커가 독립적으로 초기화
- 프로세스 간 상태 공유 불가 (Redis/DB 사용 고려)

### 테스트 격리
- `conftest.py`의 `reset_registry` 픽스처 필수
- 각 테스트 전후로 `reset_registry_for_test()` 호출
- Mock 객체 사용 시 레지스트리에 명시적 등록

### 실제 Agent API 맞추기
```python
# 예시: Agent 메서드 시그니처 확인
import inspect
print(inspect.signature(GeminiAgent.__init__))
print(inspect.signature(GeminiAgent.generate_query))
print(inspect.signature(GeminiAgent.rewrite_best_answer))
```