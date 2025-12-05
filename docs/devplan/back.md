---

# hamtoy/Test 백엔드 개선 작업 - 최종 통합본

## 📌 문서 개요

이 문서는 hamtoy/Test 프로젝트의 web.api 백엔드를 개선하기 위한 실전 가이드입니다.
- **목표**: 전역 상태 제거, 모듈화, 테스트 가능성 향상
- **원칙**: 기존 코드 시그니처 검증 → 점진적 적용 → 롤백 가능
- **위험 완화**: 각 Phase별 체크리스트 및 롤백 계획 포함

---

## 🔴 Critical: 적용 전 필수 사전 조사

### 1. 현재 코드베이스 스냅샷

```bash
# 1.1 기존 workflow 모듈 구조 확인
ls -la src/workflow/
# 예상: edit.py, inspection.py
# 주의: executor.py, unified_executor.py 충돌 가능

# 1.2 의존성 확인
cat pyproject.toml | grep -A 50 "dependencies"
# tenacity 유무 확인 (없으면 uv add tenacity)

# 1.3 기존 검증 로직 파악
find src/qa -name "*valid*.py" -o -name "*check*.py"
# UnifiedValidator 위치 확인

# 1.4 Agent/Pipeline 시그니처 확인 (가장 중요!)
python -c "
from src.agent import GeminiAgent
from src.qa.pipeline import IntegratedQAPipeline
from src.qa.rag_system import QAKnowledgeGraph
import inspect
print('GeminiAgent.__init__:', inspect.signature(GeminiAgent.__init__))
print('Pipeline.__init__:', inspect.signature(IntegratedQAPipeline.__init__))
print('KG.__init__:', inspect.signature(QAKnowledgeGraph.__init__))
"
```

### 2. 테스트 현황 확인

```bash
# 전체 테스트 실행
pytest tests/ -v --tb=short

# 커버리지 확인
pytest tests/ --cov=src/web --cov-report=term-missing
```

### 3. API 계약 확인

```bash
# 클라이언트 엔드포인트 사용 확인
grep -r "/workspace" static/*.js templates/*.html
grep -r "api_unified_workspace" tests/

# 현재 Request/Response 모델 확인
grep -A 10 "class.*Request" src/web/models.py
```

---

## Phase 0: 실제 시그니처 검증 (필수)

### ⚠️ 주의: 예시 코드는 가정입니다. 실제 시그니처를 먼저 확인하세요!

```python
# src/agent/agent.py 예시
class GeminiAgent:
    def __init__(
        self,
        config: AppConfig,
        jinja_env: Environment,
        # ← 이 파라미터들이 실제와 일치하는지 확인!
    ):
        ...

# src/qa/pipeline.py 예시
class IntegratedQAPipeline:
    def __init__(self):  # ← 파라미터가 있는지 확인!
        ...

# src/qa/rag_system.py 예시
class QAKnowledgeGraph:
    def __init__(self):  # ← URI/user/password 받는지 확인!
        ...
```

**검증 스크립트 실행 후 devplan/back.md의 예시 코드와 비교하세요!**

---

## Phase 1: 서비스 레지스트리 도입 (1-2일)

### 목표
- 전역 변수 `_config`, `agent`, `kg`, `pipeline` 제거
- 싱글톤 패턴 ServiceRegistry로 의존성 관리
- 테스트 격리 가능하도록 `reset_registry_for_test()` 제공

### 1.1 ServiceRegistry 생성

#### src/web/service_registry.py (신규)

```python
"""서비스 레지스트리 - 싱글톤 패턴."""
from __future__ import annotations
from typing import Optional, TYPE_CHECKING
import threading
import logging
import os

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
        self._worker_id = os.getpid()
    
    def _check_worker(self):
        """프로세스가 바뀌면 경고 (멀티프로세스 디버깅용)."""
        current_pid = os.getpid()
        if current_pid != self._worker_id:
            logger.warning(
                "ServiceRegistry accessed from different process: "
                "original=%d, current=%d",
                self._worker_id,
                current_pid
            )
    
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
        self._check_worker()
        if self._config is None:
            raise RuntimeError("Config not registered. Call init_resources first.")
        return self._config
    
    @property
    def agent(self) -> GeminiAgent:
        self._check_worker()
        if self._agent is None:
            raise RuntimeError("Agent not registered. Call init_resources first.")
        return self._agent
    
    @property
    def kg(self) -> Optional[QAKnowledgeGraph]:
        self._check_worker()
        return self._kg
    
    @property
    def pipeline(self) -> Optional[IntegratedQAPipeline]:
        self._check_worker()
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
# ===== 기존 전역 변수 삭제 =====
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
    
    # ⚠️ Phase 0에서 확인한 실제 시그니처에 맞춰 수정!
    gemini_agent = GeminiAgent(
        config=app_config,
        jinja_env=jinja_env,
    )
    registry.register_agent(gemini_agent)
    logger.info("GeminiAgent initialized")
    
    # 3. KG 등록
    try:
        knowledge_graph = QAKnowledgeGraph()
        registry.register_kg(knowledge_graph)
        logger.info("QAKnowledgeGraph initialized")
    except Exception as e:
        logger.warning("Neo4j connection failed (RAG disabled): %s", e)
        registry.register_kg(None)
    
    # 4. Pipeline 등록
    try:
        qa_pipeline = IntegratedQAPipeline()
        registry.register_pipeline(qa_pipeline)
        logger.info("IntegratedQAPipeline initialized")
    except Exception as e:
        logger.warning("Pipeline init failed: %s", e)
        registry.register_pipeline(None)
    
    # 5. 라우터 의존성 주입
    # ⚠️ 각 라우터의 set_dependencies 시그니처 확인 필요!
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
# 삭제: set_dependencies, _get_agent, _get_kg, _get_pipeline, _get_config

from src.web.service_registry import get_registry

# ===== 엔드포인트 수정 예시 =====
@router.post("/workspace/unified")
async def api_unified_workspace(body: UnifiedWorkspaceRequest) -> Dict[str, Any]:
    """통합 워크스페이스 - ServiceRegistry 사용."""
    registry = get_registry()
    
    # 서비스 가져오기
    config = registry.config
    agent = registry.agent
    kg = registry.kg
    pipeline = registry.pipeline
    
    # OCR 텍스트 로드
    ocr_text = body.ocr_text or load_ocr_text()
    
    # 기존 로직 유지 (또는 Phase 2에서 WorkspaceExecutor로 이동)
    try:
        # ... 기존 워크플로우 로직 ...
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

#### tests/conftest.py (수정)

```python
"""테스트 픽스처."""
import pytest
from src.web.service_registry import reset_registry_for_test, _registry


@pytest.fixture(scope="function", autouse=True)
def isolate_registry():
    """각 테스트마다 레지스트리 격리."""
    # 현재 상태 백업
    original_state = {
        'config': _registry._config,
        'agent': _registry._agent,
        'kg': _registry._kg,
        'pipeline': _registry._pipeline,
    }
    
    # 테스트 전 초기화
    reset_registry_for_test()
    
    yield
    
    # 테스트 후 복원
    _registry._config = original_state['config']
    _registry._agent = original_state['agent']
    _registry._kg = original_state['kg']
    _registry._pipeline = original_state['pipeline']


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

### Phase 1 체크리스트

- [ ] ServiceRegistry 생성 완료
- [ ] api.py 수정 완료 (시그니처 검증 후)
- [ ] workspace.py 전역 변수 제거 완료
- [ ] 테스트 작성 완료
- [ ] `pytest tests/web/test_service_registry.py -v` 통과
- [ ] `pytest tests/ -v` 전체 통과
- [ ] 로컬 서버 기동 확인
- [ ] `/health` 엔드포인트 정상 응답 확인

---

## Phase 2: 워크스페이스 로직 분리 (3-5일)

### 목표
- 1,000줄+ workspace.py를 WorkspaceExecutor로 분리
- 7가지 워크플로우 타입별 핸들러 구조화
- 기존 기능 유지하며 테스트 가능하게

### 2.1 파일명 충돌 확인

```bash
# 기존 파일 확인
ls -la src/workflow/

# executor.py가 이미 있다면:
# → workspace_executor.py 사용
# → 또는 qa_executor.py 사용
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
    
    # ===== 워크플로우 핸들러 (기존 workspace.py 로직 이동) =====
    
    async def _handle_full_generation(self, ctx: WorkflowContext) -> WorkflowResult:
        """전체 생성 워크플로우."""
        changes: List[str] = ["OCR에서 전체 생성"]
        
        # 1. 질의 생성
        query_intent = self._get_query_intent(ctx.query_type, ctx.global_explanation_ref)
        queries = await self.agent.generate_query(
            ctx.ocr_text,
            user_intent=query_intent,
            query_type=ctx.query_type,
            kg=self.kg,
        )
        
        query = queries if queries else "질문 생성 실패"
        
        if ctx.query_type == "target_short":
            query = self._shorten_query(query)
        
        changes.append("질의 생성 완료")
        
        # 2. 답변 생성
        answer = await self._generate_answer(ctx, query)
        changes.append("답변 생성 완료")
        
        return WorkflowResult(
            workflow="full_generation",
            query=query,
            answer=answer,
            changes=changes,
            query_type=ctx.query_type,
        )
    
    # ... (나머지 핸들러는 기존 workspace.py 로직 참조)
    
    # ===== 헬퍼 메서드 =====
    
    def _get_query_intent(self, query_type: str, global_ref: str) -> Optional[str]:
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
    
    async def _generate_answer(self, ctx: WorkflowContext, query: str) -> str:
        """답변 생성 (공통 로직)."""
        # ⚠️ 기존 workspace.py의 프롬프트 생성 로직을 여기로 이동
        # Phase 3에서 템플릿으로 분리 가능
        
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
    ocr_text = body.ocr_text or load_ocr_text()
    
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
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Workflow execution failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="워크플로우 실행 중 오류가 발생했습니다."
        )
```

### Phase 2 체크리스트

- [ ] WorkspaceExecutor 생성 완료
- [ ] 기존 workspace.py 로직 이동 완료
- [ ] 라우터에서 Executor 사용 완료
- [ ] WorkspaceExecutor 단위 테스트 작성
- [ ] `/api/workspace/unified` POST 요청 테스트
- [ ] 기존 클라이언트 동작 확인
- [ ] 전체 테스트 통과

---

## Phase 3-7: 추가 개선 (선택)

### Phase 3: 프롬프트 템플릿 외부화
- `templates/prompts/workspace/answer_generation.jinja2` 생성
- Jinja2로 프롬프트 렌더링
- 버전 관리 가능, 다국어 지원 용이

### Phase 4: 검증 레이어 통합
- 기존 `UnifiedValidator` 확장
- `validate_format()`, `validate_length()` 메서드 추가
- 중복 검증 로직 제거

### Phase 5: 에러 처리 개선
- `src/web/exceptions.py` 생성
- `AppError`, `RetryableError`, `TimeoutError` 정의
- 에러 타입별 HTTP 상태 코드 매핑

### Phase 6: 재시도 로직
- `src/infra/retry.py` 생성
- `async_retry` 데코레이터 구현
- Agent 호출에 적용

### Phase 7: 캐싱 개선
- `RuleLoader.get_rules_for_type()` 메모이제이션
- `@lru_cache` 데코레이터 사용

---

## 🎯 우선순위 및 적용 순서

### Day 1: 시그니처 검증 (필수)
```bash
# Phase 0 실행
python -c "
from src.agent import GeminiAgent
import inspect
print(inspect.signature(GeminiAgent.__init__))
"
# 출력 결과를 devplan/back.md의 예시와 비교
```

### Day 2-3: Phase 1 적용
1. ServiceRegistry 생성
2. api.py 수정 (주석 참조하며 신중히)
3. workspace.py 전역 변수 제거
4. 테스트 작성 및 실행

### Day 4-5: Phase 2 적용
1. WorkspaceExecutor 생성
2. 한 워크플로우씩 이동 (FULL_GENERATION부터)
3. 각 단계마다 테스트 확인

### Day 6-10: Phase 3-7 (선택)
필요한 개선사항만 선택적으로 적용

---

## 🛡️ 위험 관리

### 롤백 계획

```bash
# Phase 1 롤백
git checkout HEAD -- src/web/service_registry.py
git checkout HEAD -- src/web/api.py
git checkout HEAD -- src/web/routers/workspace.py
pytest tests/ -v

# Phase 2 롤백
git checkout HEAD -- src/workflow/workspace_executor.py
git checkout HEAD -- src/web/routers/workspace.py
pytest tests/ -v
```

### 위험 신호 (즉시 롤백 고려)

1. **테스트 실패율 30% 이상** → 시그니처 재확인
2. **로컬 서버 기동 실패** → api.py 초기화 로직 검토
3. **메모리 누수 발견** → ServiceRegistry 생명주기 재설계
4. **성능 저하 20% 이상** → 병목 지점 프로파일링

### Quick Win (당장 적용 가능)

```python
# src/web/routers/workspace.py에만 적용
# 전역 변수 하나씩 제거

# Before:
_config: Optional[AppConfig] = None

# After:
def _get_config() -> AppConfig:
    from src.web.service_registry import get_registry
    return get_registry().config

# 모든 _config 사용처를 _get_config()로 변경
# 테스트 통과하면 나머지도 순차 제거
```

---

## 📋 최종 체크리스트

### 적용 전
- [ ] 시그니처 검증 완료
- [ ] 기존 테스트 전체 통과
- [ ] 백업 브랜치 생성

### Phase 1 완료 후
- [ ] ServiceRegistry 테스트 통과
- [ ] 전체 테스트 통과
- [ ] 로컬 서버 정상 기동
- [ ] `/health` 정상 응답

### Phase 2 완료 후
- [ ] WorkspaceExecutor 테스트 통과
- [ ] API 엔드포인트 정상 동작
- [ ] 클라이언트 정상 동작
- [ ] 성능 회귀 없음

### 최종 완료
- [ ] 문서 업데이트
- [ ] PR 생성
- [ ] 코드 리뷰 요청

---

## 💡 추가 주의사항

### 멀티프로세스 환경
- ServiceRegistry는 프로세스당 독립 인스턴스
- Gunicorn 멀티워커 환경에서 각 워커가 독립 초기화
- 프로세스 간 상태 공유 불가 (Redis/DB 사용 고려)

### 테스트 격리
- `conftest.py`의 `reset_registry` 픽스처 필수
- Mock 객체는 레지스트리에 명시적 등록
- 각 테스트 전후 `reset_registry_for_test()` 호출

### 실전 팁
- 한 번에 하나의 Phase만 적용
- 각 Phase 완료 후 커밋
- 문제 발생 시 즉시 이전 커밋으로 롤백

---

**작성일**: 2025-12-05  
**버전**: 1.0 (최종 통합본)  
**다음 업데이트**: Phase 3-7 상세 구현 가이드