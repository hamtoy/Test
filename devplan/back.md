제공해주신 마크다운 문서는 전반적으로 내용이 좋으나, 코드 블록의 언어 지정이 누락되어 있거나 중첩된 블록 형식으로 인해 가독성이 떨어질 수 있는 부분이 있습니다.

아래는 **언어 하이라이팅(Python, Jinja2 등)**을 적용하고 포맷을 깔끔하게 정리한 수정본입니다. 이 내용을 그대로 `.md` 파일로 저장하여 사용하시면 됩니다.

---

# hamtoy/Test web.api 백엔드 개선 작업

## 1. 전역 상태 제거 및 의존성 주입 (긴급)

### 현재 문제
- `src/web/api.py`와 `src/web/routers/workspace.py`에 모듈 레벨 전역 변수 사용
- 테스트 시 패칭 어려움, 동시성 문제 가능성

### 개선 작업

#### src/web/container.py (신규 생성)
```python
"""의존성 주입 컨테이너."""
from dependency_injector import containers, providers
from src.config import AppConfig
from src.agent import GeminiAgent
from src.qa.rag_system import QAKnowledgeGraph
from src.qa.pipeline import IntegratedQAPipeline

class AppContainer(containers.DeclarativeContainer):
    """애플리케이션 전역 의존성 컨테이너."""
    
    config = providers.Singleton(AppConfig)
    
    agent = providers.Singleton(
        GeminiAgent,
        config=config,
        jinja_env=providers.Dependency(),
    )
    
    kg = providers.Singleton(
        QAKnowledgeGraph,
    )
    
    pipeline = providers.Singleton(
        IntegratedQAPipeline,
    )
```

#### src/web/api.py 수정
```python
# 전역 변수 제거
# _config, agent, kg, pipeline 삭제

# 컨테이너 추가
from src.web.container import AppContainer

container = AppContainer()

async def init_resources() -> None:
    """리소스 초기화."""
    from jinja2 import Environment, FileSystemLoader
    
    jinja_env = Environment(
        loader=FileSystemLoader(str(REPO_ROOT / "templates")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    
    container.agent.init(jinja_env=jinja_env)
    
    # 라우터 의존성 주입
    qa_router_module.set_dependencies(
        container.config(),
        container.agent(),
        container.pipeline(),
        container.kg()
    )
    workspace_router_module.set_dependencies(
        container.config(),
        container.agent(),
        container.kg(),
        container.pipeline()
    )
```

#### src/web/routers/workspace.py 수정
```python
# 전역 변수 제거
# _config, agent, kg, pipeline, _validator 삭제

# 의존성을 클래스 속성으로 저장
class WorkspaceService:
    def __init__(
        self,
        config: AppConfig,
        agent: GeminiAgent,
        kg: Optional[QAKnowledgeGraph],
        pipeline: Optional[IntegratedQAPipeline],
    ):
        self.config = config
        self.agent = agent
        self.kg = kg
        self.pipeline = pipeline
        self._validator: Optional[CrossValidationSystem] = None

    def get_validator(self) -> Optional[CrossValidationSystem]:
        if self._validator is None and self.kg:
            self._validator = CrossValidationSystem(self.kg)
        return self._validator

# 전역 서비스 인스턴스
_service: Optional[WorkspaceService] = None

def set_dependencies(config, gemini_agent, kg_ref, qa_pipeline):
    global _service
    _service = WorkspaceService(config, gemini_agent, kg_ref, qa_pipeline)
```

## 2. workspace.py 모듈화 (높음)

### 현재 문제
- 1,000줄 이상의 단일 파일
- 워크플로우 로직, LATS 평가, 프롬프트 생성이 혼재

### 개선 작업

#### src/workflow/executor.py (신규 생성)
```python
"""워크플로우 실행 엔진."""
from enum import Enum
from typing import Dict, Any
from dataclasses import dataclass

class WorkflowType(Enum):
    FULL_GENERATION = "full_generation"
    QUERY_GENERATION = "query_generation"
    ANSWER_GENERATION = "answer_generation"
    REWRITE = "rewrite"
    EDIT_QUERY = "edit_query"
    EDIT_ANSWER = "edit_answer"
    EDIT_BOTH = "edit_both"

@dataclass
class WorkflowContext:
    query: str
    answer: str
    ocr_text: str
    query_type: str
    edit_request: str
    global_explanation_ref: str
    use_lats: bool

class WorkflowExecutor:
    def __init__(self, agent, kg, pipeline, config):
        self.agent = agent
        self.kg = kg
        self.pipeline = pipeline
        self.config = config
        self.handlers = {
            WorkflowType.FULL_GENERATION: self._handle_full_generation,
            WorkflowType.QUERY_GENERATION: self._handle_query_generation,
            WorkflowType.ANSWER_GENERATION: self._handle_answer_generation,
            WorkflowType.REWRITE: self._handle_rewrite,
            WorkflowType.EDIT_QUERY: self._handle_edit_query,
            WorkflowType.EDIT_ANSWER: self._handle_edit_answer,
            WorkflowType.EDIT_BOTH: self._handle_edit_both,
        }
    
    async def execute(
        self,
        workflow: WorkflowType,
        context: WorkflowContext
    ) -> Dict[str, Any]:
        handler = self.handlers[workflow]
        return await handler(context)
    
    async def _handle_full_generation(self, ctx: WorkflowContext):
        # 로직 이동
        pass
    
    async def _handle_query_generation(self, ctx: WorkflowContext):
        # 로직 이동
        pass
```

#### src/workflow/lats_evaluator.py (신규 생성)
```python
"""LATS 답변 후보 생성 및 평가."""
from typing import List, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

class LATSEvaluator:
    def __init__(self, agent):
        self.agent = agent
        self.strategies = [
            {
                "name": "숫자_중심",
                "instruction": "OCR 텍스트에 있는 모든 주요 숫자와 수치를 중심으로 답변하세요.",
            },
            {
                "name": "트렌드_중심",
                "instruction": "시간에 따른 변화, 증가/감소 추세를 중심으로 답변하세요.",
            },
            {
                "name": "비교_중심",
                "instruction": "서로 다른 항목들의 차이점과 비교를 중심으로 답변하세요.",
            },
        ]
    
    async def generate_and_evaluate(
        self,
        query: str,
        ocr_text: str,
        query_type: str,
    ) -> Tuple[str, Dict[str, Any]]:
        """여러 전략으로 답변 생성 후 최적 선택."""
        candidates: List[Dict[str, Any]] = []
        
        for strategy in self.strategies:
            try:
                answer = await self._generate_with_strategy(
                    query, ocr_text, strategy
                )
                score = await self._evaluate_quality(
                    answer, ocr_text, query_type
                )
                candidates.append({
                    "strategy": strategy["name"],
                    "answer": answer,
                    "score": score,
                })
                logger.info(
                    "LATS 후보 생성: %s (점수: %.2f)",
                    strategy["name"],
                    score
                )
            except Exception as e:
                logger.debug(
                    "LATS 답변 생성 실패 (%s): %s",
                    strategy["name"],
                    e
                )
                continue
        
        if not candidates:
            return "", {}
        
        best = max(candidates, key=lambda x: float(x["score"]))
        meta = {
            "candidates": len(candidates),
            "best_strategy": best["strategy"],
            "best_score": best["score"],
            "all_scores": [c["score"] for c in candidates],
        }
        return str(best["answer"]), meta
    
    async def _generate_with_strategy(
        self, query: str, ocr_text: str, strategy: Dict[str, str]
    ) -> str:
        # 기존 _generate_lats_answer 로직
        pass
    
    async def _evaluate_quality(
        self, answer: str, ocr_text: str, query_type: str
    ) -> float:
        # 기존 _evaluate_answer_quality 로직
        pass
```

#### src/web/routers/workspace.py 리팩토링
```python
# 대폭 축소
from src.workflow.executor import WorkflowExecutor, WorkflowType, WorkflowContext
from src.workflow.lats_evaluator import LATSEvaluator

@router.post("/workspace/unified")
async def api_unified_workspace(body: UnifiedWorkspaceRequest):
    if _service is None:
        raise HTTPException(500, "Service not initialized")
    
    workflow_type = WorkflowType(
        detect_workflow(body.query or "", body.answer or "", body.edit_request)
    )
    
    context = WorkflowContext(
        query=body.query or "",
        answer=body.answer or "",
        ocr_text=body.ocr_text or load_ocr_text(_service.config),
        query_type=body.query_type or "global_explanation",
        edit_request=body.edit_request or "",
        global_explanation_ref=body.global_explanation_ref or "",
        use_lats=body.use_lats,
    )
    
    executor = WorkflowExecutor(
        _service.agent,
        _service.kg,
        _service.pipeline,
        _service.config,
    )
    
    try:
        result = await asyncio.wait_for(
            executor.execute(workflow_type, context),
            timeout=_service.config.workspace_unified_timeout
        )
        # 응답 처리
    except asyncio.TimeoutError:
        raise HTTPException(504, "워크플로우 시간 초과")
```

## 3. 프롬프트 외부화 (높음)

### 현재 문제
- f-string으로 하드코딩된 프롬프트
- 버전 관리 불가, 다국어 지원 어려움

### 개선 작업

#### templates/prompts/answer_generation.jinja2 (신규 생성)
```jinja2
[지시사항]
반드시 {{ language }}로 답변하세요.
OCR에 없는 정보는 추가하지 마세요.
{% if length_constraint %}
{{ length_constraint }}
{% endif %}
{% if dedup_section %}
{{ dedup_section }}
{% endif %}
{{ difficulty_hint }}
{{ evidence_clause }}

[준수 규칙]
{% for rule in rules_list %}
- {{ rule }}
{% endfor %}
{% for rule in extra_rules %}
- {{ rule }}
{% endfor %}

[OCR 텍스트]
{{ ocr_text[:3000] }}

[질의]
{{ query }}

위 OCR 텍스트를 기반으로 답변을 작성하세요.
```

#### templates/prompts/query_generation.jinja2 (신규 생성)
```jinja2
다음 답변에 가장 적합한 질문을 생성하세요.

[OCR 텍스트]
{{ ocr_text[:1000] }}

[답변]
{{ answer }}

위 답변에 대한 자연스러운 질문 1개를 생성하세요. 질문만 출력하세요.
```

#### src/workflow/prompt_builder.py (신규 생성)
```python
"""프롬프트 템플릿 빌더."""
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from typing import Dict, Any

class PromptBuilder:
    def __init__(self, template_dir: Path):
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    
    def build_answer_generation(
        self,
        query: str,
        ocr_text: str,
        rules_list: list[str],
        extra_rules: list[str] = None,
        length_constraint: str = "",
        dedup_section: str = "",
        difficulty_hint: str = "",
        language: str = "한국어",
    ) -> str:
        template = self.env.get_template("prompts/answer_generation.jinja2")
        return template.render(
            language=language,
            length_constraint=length_constraint,
            dedup_section=dedup_section,
            difficulty_hint=difficulty_hint,
            evidence_clause="숫자·고유명사는 OCR에 나온 값 그대로 사용하세요.",
            rules_list=rules_list,
            extra_rules=extra_rules or [],
            ocr_text=ocr_text,
            query=query,
        )
    
    def build_query_generation(
        self, answer: str, ocr_text: str
    ) -> str:
        template = self.env.get_template("prompts/query_generation.jinja2")
        return template.render(
            answer=answer,
            ocr_text=ocr_text,
        )
```

#### src/workflow/executor.py에 통합
```python
from src.workflow.prompt_builder import PromptBuilder

class WorkflowExecutor:
    def __init__(self, agent, kg, pipeline, config):
        # ...
        self.prompt_builder = PromptBuilder(
            Path(__file__).parents / "templates"
        )
    
    async def _handle_answer_generation(self, ctx: WorkflowContext):
        rules_list = self._load_rules(ctx.query_type)
        
        prompt = self.prompt_builder.build_answer_generation(
            query=ctx.query,
            ocr_text=ctx.ocr_text,
            rules_list=rules_list,
            length_constraint=self._get_length_constraint(ctx.query_type),
            dedup_section=self._build_dedup_section(ctx.global_explanation_ref),
        )
        
        answer = await self.agent.rewrite_best_answer(
            ocr_text=ctx.ocr_text,
            best_answer=prompt,
            cached_content=None,
            query_type=ctx.query_type,
        )
        return answer
```

## 4. 검증 레이어 통합 (중간)

### 현재 문제
- 4개의 검증 시스템이 중복 역할 수행
- 일관성 없는 검증 결과

### 개선 작업

#### src/qa/validation/pipeline.py (신규 생성)
```python
"""통합 검증 파이프라인."""
from typing import List, Optional
from dataclasses import dataclass, field

@dataclass
class ValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    
    def has_errors(self) -> bool:
        return len(self.errors) > 0
    
    def get_error_summary(self) -> str:
        return "; ".join(self.errors[:3])
    
    def merge(self, other: "ValidationResult") -> "ValidationResult":
        return ValidationResult(
            valid=self.valid and other.valid,
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
            suggestions=self.suggestions + other.suggestions,
        )

class BaseValidator:
    def validate(self, answer: str, qtype: str) -> ValidationResult:
        raise NotImplementedError

class FormatValidator(BaseValidator):
    """형식 검증: 마크다운, 불릿 등."""
    def validate(self, answer: str, qtype: str) -> ValidationResult:
        import re
        errors = []
        
        # 불릿 검증
        if re.search(r"^\s*[-*- ]\s", answer, re.MULTILINE):
            errors.append("불릿 포인트 사용 금지")
        
        # 마크다운 볼드 검증
        if re.search(r"\*\*.*?\*\*", answer):
            errors.append("마크다운 볼드 사용 금지")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
        )

class LengthValidator(BaseValidator):
    """길이 검증."""
    LIMITS = {
        "target_short": (10, 200),
        "target_long": (50, 500),
        "reasoning": (100, 1000),
        "global_explanation": (200, 3000),
    }
    
    def validate(self, answer: str, qtype: str) -> ValidationResult:
        min_len, max_len = self.LIMITS.get(qtype, (10, 5000))
        length = len(answer)
        
        if length < min_len:
            return ValidationResult(
                valid=False,
                errors=[f"답변이 너무 짧습니다 (최소 {min_len}자)"],
            )
        
        if length > max_len:
            return ValidationResult(
                valid=False,
                errors=[f"답변이 너무 깁니다 (최대 {max_len}자)"],
            )
        
        return ValidationResult(valid=True)

class ConstraintValidator(BaseValidator):
    """Neo4j 제약사항 검증."""
    def __init__(self, kg):
        self.kg = kg
    
    def validate(self, answer: str, qtype: str) -> ValidationResult:
        if not self.kg:
            return ValidationResult(valid=True)
        
        errors = []
        warnings = []
        
        try:
            constraints = self.kg.get_constraints_for_query_type(qtype)
            for constraint in constraints:
                # 제약사항 검증 로직
                pass
        except Exception as e:
            warnings.append(f"제약사항 검증 실패: {str(e)}")
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

class ValidationPipeline:
    """통합 검증 파이프라인."""
    def __init__(self, kg=None):
        self.validators: List[BaseValidator] = [
            FormatValidator(),
            LengthValidator(),
        ]
        if kg:
            self.validators.append(ConstraintValidator(kg))
    
    def validate(self, answer: str, qtype: str) -> ValidationResult:
        result = ValidationResult(valid=True)
        
        for validator in self.validators:
            current = validator.validate(answer, qtype)
            result = result.merge(current)
            
            # 에러 발생 시 조기 종료
            if current.has_errors():
                break
        
        return result
```

#### src/workflow/executor.py에 통합
```python
from src.qa.validation.pipeline import ValidationPipeline

class WorkflowExecutor:
    def __init__(self, agent, kg, pipeline, config):
        # ...
        self.validator = ValidationPipeline(kg)
    
    async def _handle_answer_generation(self, ctx: WorkflowContext):
        # 답변 생성
        answer = await self._generate_answer(ctx)
        
        # 검증
        validation = self.validator.validate(answer, ctx.query_type)
        
        # 위반 시 재작성
        if validation.has_errors():
            edit_request = validation.get_error_summary()
            answer = await self._rewrite_answer(answer, ctx, edit_request)
        
        return answer
```

## 5. 에러 타입별 처리 (중간)

### 현재 문제
- 모든 예외를 500으로 처리
- 재시도 가능 여부 구분 없음

### 개선 작업

#### src/web/exceptions.py (신규 생성)
```python
"""커스텀 예외 클래스."""
from fastapi import HTTPException

class RetryableError(HTTPException):
    """재시도 가능한 오류."""
    def __init__(self, detail: str, retry_after: int = 5):
        super().__init__(
            status_code=503,
            detail=detail,
            headers={"Retry-After": str(retry_after)}
        )

class TimeoutError(HTTPException):
    """타임아웃 오류."""
    def __init__(self, detail: str, timeout: int):
        super().__init__(
            status_code=504,
            detail=f"{detail} ({timeout}초 초과)"
        )

class ValidationError(HTTPException):
    """검증 오류."""
    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)

class ResourceNotFoundError(HTTPException):
    """리소스 없음."""
    def __init__(self, resource: str):
        super().__init__(
            status_code=404,
            detail=f"{resource}을(를) 찾을 수 없습니다."
        )
```

#### src/web/routers/workspace.py 수정
```python
from src.web.exceptions import (
    RetryableError,
    TimeoutError,
    ValidationError,
)

@router.post("/workspace/unified")
async def api_unified_workspace(body: UnifiedWorkspaceRequest):
    try:
        result = await asyncio.wait_for(
            executor.execute(workflow_type, context),
            timeout=_service.config.workspace_unified_timeout
        )
        return result
    
    except asyncio.TimeoutError:
        raise TimeoutError(
            "워크플로우 시간 초과",
            timeout=_service.config.workspace_unified_timeout
        )
    
    except ValueError as e:
        # 입력 검증 오류
        raise ValidationError(str(e))
    
    except ConnectionError as e:
        # Neo4j/Redis 연결 오류
        raise RetryableError(f"외부 서비스 연결 실패: {str(e)}")
    
    except Exception as e:
        logger.error("예상치 못한 오류: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="서버 오류가 발생했습니다. 관리자에게 문의하세요."
        )
```

## 6. 재시도 로직 추가 (중간)

### 개선 작업

#### requirements.txt에 추가
```text
tenacity==8.2.3
```

#### src/llm/retry.py (신규 생성)
```python
"""LLM 호출 재시도 로직."""
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import logging

logger = logging.getLogger(__name__)

# 재시도 가능한 예외
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
)

def llm_retry_decorator():
    """LLM 호출용 재시도 데코레이터."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
        before_sleep=lambda retry_state: logger.warning(
            "LLM 호출 재시도 (%d/%d): %s",
            retry_state.attempt_number,
            3,
            retry_state.outcome.exception()
        ),
    )

@llm_retry_decorator()
async def call_llm_with_retry(agent, prompt: str, **kwargs):
    """재시도 로직이 포함된 LLM 호출."""
    return await agent.generate(prompt, **kwargs)
```

#### src/workflow/executor.py에 적용
```python
from src.llm.retry import call_llm_with_retry

class WorkflowExecutor:
    async def _generate_answer(self, ctx: WorkflowContext) -> str:
        prompt = self.prompt_builder.build_answer_generation(...)
        
        return await call_llm_with_retry(
            self.agent,
            prompt,
            query_type=ctx.query_type,
        )
```

## 7. 캐싱 추가 (낮음)

### 개선 작업

#### src/qa/rule_loader.py 수정
```python
from functools import lru_cache

class RuleLoader:
    @lru_cache(maxsize=128)
    def get_rules_for_type(
        self, query_type: str, defaults: list
    ) -> list[str]:
        """메모이제이션된 규칙 로드."""
        if not self.kg:
            return defaults
        
        try:
            kg_rules = self.kg.get_rules_for_query_type(query_type)
            return [r.get("text") for r in kg_rules if r.get("text")]
        except Exception:
            return defaults
```

## 우선순위

1. **긴급**: 전역 상태 제거 및 의존성 주입 (테스트 가능성)
2. **높음**: workspace.py 모듈화 (유지보수성)
3. **높음**: 프롬프트 외부화 (버전 관리)
4. **중간**: 검증 레이어 통합
5. **중간**: 에러 타입별 처리
6. **중간**: 재시도 로직 추가
7. **낮음**: 캐싱 추가