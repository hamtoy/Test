# mypy: disable-error-code=misc
"""Gemini Agent 핵심 모듈.

GeminiAgent 클래스의 메인 로직을 포함합니다.

## Architecture
This module follows the Service Pattern where business logic is delegated to:
- QueryGeneratorService (in services.py) - Query generation logic
- ResponseEvaluatorService (in services.py) - Response evaluation logic
- RewriterService (in services.py) - Response rewriting logic

The GeminiAgent class acts as a coordinator, managing:
- API client lifecycle
- Rate limiting and concurrency control
- Cost tracking and budget management
- Cache management
- Context and retry handling

## Structure
**Imports and Utilities** (lines 1-66): Module imports and helper functions
**Agent Initialization** (lines 67-140): GeminiAgent initialization and component setup
**Core API Methods** (lines 141-300): Main methods delegating to services
**Cache & Context** (lines 301-450): Cache and context management
**Utilities** (lines 451-600): Helper methods and tracking
**Lifecycle** (lines 601-end): Cleanup and resource management

Note: This is a large file, but most business logic has been extracted to services.py.
Further refactoring could split by concern (initialization, API calls, management).
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import AsyncGenerator, Callable
from typing import (
    TYPE_CHECKING,
    Any,
    cast,
)

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import AppConfig
from src.config.exceptions import (
    CacheCreationError,
    ValidationFailedError,
)
from src.core.models import EvaluationResultSchema
from src.infra.logging import log_metrics as _log_metrics
from src.infra.telemetry import get_meter, traced_async

from .cache_manager import CacheManager
from .client import GeminiClient
from .context_manager import AgentContextManager
from .cost_tracker import CostTracker
from .rate_limiter import RateLimiter
from .retry_handler import RetryHandler
from .services import (
    QueryGeneratorService,
    ResponseEvaluatorService,
    RewriterService,
)

if TYPE_CHECKING:
    from google.generativeai import caching

    from src.core.interfaces import LLMProvider
    from src.qa.rag_system import QAKnowledgeGraph


def _get_log_metrics() -> Callable[..., None]:
    """log_metrics를 동적으로 가져옴 (테스트 패칭 지원)."""
    agent_mod = sys.modules.get("src.agent")
    if agent_mod and hasattr(agent_mod, "log_metrics"):
        return cast("Callable[..., None]", agent_mod.log_metrics)
    return _log_metrics


class GeminiAgent:
    """Gemini API와의 통신을 담당하는 에이전트.

    주요 기능:
    - 의존성 주입을 통한 테스트 용이성 확보
    - Rate limiting 및 동시성 제어
    - 비용 추적 및 캐시 모니터링

    Args:
        config: 애플리케이션 설정
        jinja_env: Jinja2 환경 (테스트 시 mock 주입 가능)
    """

    def __init__(
        self,
        config: AppConfig,
        jinja_env: Environment | None = None,
        llm_provider: LLMProvider | None = None,
    ):
        """Gemini API 에이전트 초기화.

        Args:
            config: 애플리케이션 설정 (API 키, 타임아웃, 동시성 등)
            jinja_env: Jinja2 환경 (테스트 시 mock 주입 가능, 없으면 생성)
            llm_provider: LLM 제공자 (테스트 시 mock 주입 가능)

        Raises:
            FileNotFoundError: 필수 템플릿 파일이 누락된 경우
        """
        self.logger = logging.getLogger("GeminiWorkflow")
        self.config = config

        # LLM Provider 설정
        self.llm_provider: LLMProvider | None = None  # 명시적 초기화
        if llm_provider is not None:
            self.llm_provider = llm_provider
        elif getattr(config, "llm_provider_enabled", False):
            try:
                from src.core.factory import get_llm_provider

                self.llm_provider = get_llm_provider(config)
                self.logger.info(
                    "LLM provider initialized: %s",
                    self.llm_provider.__class__.__name__,
                )
            except (AttributeError, ImportError, ValueError) as e:
                self.logger.warning(
                    "Failed to initialize LLM provider: %s. Falling back to None.",
                    e,
                )
                self.llm_provider = None
            except Exception as e:
                self.logger.error(
                    "Unexpected error initializing LLM provider: %s",
                    e,
                    exc_info=True,
                )
                self.llm_provider = None
        else:
            self.llm_provider = None

        # 서브모듈 초기화
        self._rate_limiter_module = RateLimiter(config.max_concurrency)
        self._cost_tracker = CostTracker(config)
        self._cache_manager = CacheManager(config)
        meter = get_meter()  # type: ignore[no-untyped-call]
        self._api_call_counter = meter.create_counter(
            "gemini.api.calls", description="Number of Gemini API calls",
        )
        self._token_counter = meter.create_counter(
            "gemini.tokens.total", description="Total tokens used",
        )
        self._log_metrics = _get_log_metrics()
        self.client = GeminiClient(self, self._log_metrics)
        self.context_manager = AgentContextManager(self)
        self.retry_handler = RetryHandler(self)
        self.query_service = QueryGeneratorService(self)
        self.evaluator_service = ResponseEvaluatorService(self)
        self.rewriter_service = RewriterService(self)

        # 하위 호환성을 위한 속성
        self._semaphore = self._rate_limiter_module.semaphore
        self._rate_limiter = self._rate_limiter_module.limiter

        self.safety_settings = self._get_safety_settings()
        self.api_retries = 0
        self.api_failures = 0

        # Jinja2 환경 설정
        if jinja_env is not None:
            self.jinja_env = jinja_env
        else:
            required_templates = [
                "system/eval.j2",
                "system/query_gen.j2",
                "system/rewrite.j2",
                "user/query_gen.j2",
                "user/rewrite.j2",
            ]

            for template_name in required_templates:
                template_path = config.template_dir / template_name
                if not template_path.exists():
                    raise FileNotFoundError(
                        f"Required template not found: {template_path}\n"
                        f"Please ensure all .j2 files are in the templates/ directory.",
                    )

            self.jinja_env = Environment(
                loader=FileSystemLoader(config.template_dir),
                autoescape=True,
            )

    # ==================== 하위 호환성 속성 ====================

    @property
    def total_input_tokens(self) -> int:
        """총 입력 토큰 수."""
        return self._cost_tracker.total_input_tokens

    @total_input_tokens.setter
    def total_input_tokens(self, value: int) -> None:
        """Set total input tokens count."""
        self._cost_tracker.total_input_tokens = value

    @property
    def total_output_tokens(self) -> int:
        """총 출력 토큰 수."""
        return self._cost_tracker.total_output_tokens

    @total_output_tokens.setter
    def total_output_tokens(self, value: int) -> None:
        """Set total output tokens count."""
        self._cost_tracker.total_output_tokens = value

    @property
    def cache_hits(self) -> int:
        """캐시 히트 횟수."""
        return self._cache_manager.cache_hits

    @cache_hits.setter
    def cache_hits(self, value: int) -> None:
        """Set cache hits count."""
        self._cache_manager.cache_hits = value

    @property
    def cache_misses(self) -> int:
        """캐시 미스 횟수."""
        return self._cache_manager.cache_misses

    @cache_misses.setter
    def cache_misses(self, value: int) -> None:
        """Set cache misses count."""
        self._cache_manager.cache_misses = value

    @property
    def _budget_warned_thresholds(self) -> set[int]:
        """예산 경고 임계치."""
        return self._cost_tracker._budget_warned_thresholds

    # ==================== Google API 레이지 임포트 ====================

    @property
    def _genai(self) -> Any:
        import google.generativeai as genai

        return genai

    @property
    def _caching(self) -> Any:
        cached = globals().get("caching")
        if cached is not None:
            return cached
        from google.generativeai import caching

        globals()["caching"] = caching
        return caching

    @staticmethod
    def _google_exceptions() -> Any:
        from google.api_core import exceptions as google_exceptions

        return google_exceptions

    def _is_rate_limit_error(self, exc: Exception) -> bool:
        """Rate limit 에러 여부 확인."""
        try:
            google_exceptions = self._google_exceptions()
            if isinstance(exc, google_exceptions.ResourceExhausted):
                return True
        except (ImportError, AttributeError):
            pass
        return exc.__class__.__name__ == "ResourceExhausted"

    @staticmethod
    def _protos() -> Any:
        from google.generativeai import protos

        return protos

    @staticmethod
    def _harm_types() -> tuple[Any, Any]:
        from google.generativeai.types import HarmBlockThreshold, HarmCategory

        return HarmBlockThreshold, HarmCategory

    def _get_safety_settings(self) -> dict[Any, Any]:
        harm_block_threshold, harm_category = self._harm_types()
        return dict.fromkeys([harm_category.HARM_CATEGORY_HARASSMENT, harm_category.HARM_CATEGORY_HATE_SPEECH, harm_category.HARM_CATEGORY_SEXUALLY_EXPLICIT, harm_category.HARM_CATEGORY_DANGEROUS_CONTENT], harm_block_threshold.BLOCK_NONE)

    # ==================== 캐시 관련 메서드 ====================

    def _track_cache_usage(self, cached: bool) -> None:
        """캐시 사용 여부를 추적하여 메트릭 기록.

        Args:
            cached (bool): 캐시를 사용했는지 여부. True면 캐시 히트 카운트 증가.
        """
        self.context_manager.track_cache_usage(cached)

    def _local_cache_manifest_path(self) -> Any:
        """로컬 캐시 매니페스트 경로."""
        return self._cache_manager._local_cache_manifest_path()

    def _cleanup_expired_cache(self, ttl_minutes: int) -> None:
        """만료된 캐시 정리."""
        self.context_manager.cleanup_expired_cache(ttl_minutes)

    def _load_local_cache(self, fingerprint: str, ttl_minutes: int) -> Any:
        """로컬 캐시 로드."""
        return self.context_manager.load_local_cache(
            fingerprint, ttl_minutes, self._caching,
        )

    def _store_local_cache(
        self, fingerprint: str, cache_name: str, ttl_minutes: int,
    ) -> None:
        """로컬 캐시 저장.

        Args:
            fingerprint (str): 컨텐츠의 고유 해시 값(식별자).
            cache_name (str): 저장할 캐시 이름.
            ttl_minutes (int): 캐시 수명 시간(분).
        """
        self.context_manager.store_local_cache(fingerprint, cache_name, ttl_minutes)

    # ==================== 모델 생성 ====================

    def _create_generative_model(
        self,
        system_prompt: str,
        response_schema: type[BaseModel] | None = None,
        cached_content: caching.CachedContent | None = None,
    ) -> Any:
        """GenerativeModel 인스턴스를 생성하는 팩토리 메서드.

        Args:
            system_prompt (str): 시스템 프롬프트 텍스트.
            response_schema (Optional[type[BaseModel]]): JSON 응답 스키마.
                None이면 일반 텍스트 응답.
            cached_content (Optional[caching.CachedContent]): 재사용할 캐시 객체.

        Returns:
            Any: 설정된 GenerativeModel 인스턴스.
        """
        generation_config: dict[str, object] = {
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_output_tokens,
        }

        if response_schema:
            generation_config["response_mime_type"] = "application/json"
            generation_config["response_schema"] = response_schema

        gen_config_param = cast("Any", generation_config)

        if cached_content:
            model = self._genai.GenerativeModel.from_cached_content(
                cached_content=cached_content,
                generation_config=gen_config_param,
                safety_settings=self.safety_settings,
            )
        else:
            model = self._genai.GenerativeModel(
                model_name=self.config.model_name,
                system_instruction=system_prompt,
                generation_config=gen_config_param,
                safety_settings=self.safety_settings,
            )
        try:
            model._agent_system_instruction = system_prompt
            model._agent_response_schema = response_schema
        except (TypeError, AttributeError):
            pass
        return model

    # ==================== Context Cache ====================

    async def create_context_cache(self, ocr_text: str) -> Any:
        """OCR 텍스트를 기반으로 Gemini Context Cache 생성."""
        try:
            return await self.context_manager.create_context_cache(ocr_text)
        except self._google_exceptions().ResourceExhausted as e:
            raise CacheCreationError(
                "Rate limit exceeded during cache creation: %s" % e,
            ) from e
        except (ValueError, RuntimeError, OSError) as e:
            raise CacheCreationError("Failed to create cache: %s" % e) from e

    # ==================== API 호출 ====================

    async def _call_api_with_retry(self, model: Any, prompt_text: str) -> str:
        """재시도 로직이 포함된 API 호출 (RetryHandler 위임)."""
        return await self.retry_handler.call(model, prompt_text)

    async def _execute_api_call(self, model: Any, prompt_text: str) -> str:
        """실제 API 호출 로직 (GeminiClient 위임)."""
        return await self.client.execute(model, prompt_text)

    # ==================== Query 생성 ====================

    @traced_async("gemini.generate_query")
    async def generate_query(
        self,
        ocr_text: str,
        user_intent: str | None = None,
        cached_content: caching.CachedContent | None = None,
        template_name: str | None = None,
        query_type: str = "explanation",
        kg: QAKnowledgeGraph | None = None,
        constraints: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        """OCR 텍스트와 사용자 의도에 기반한 전략적 쿼리 생성.

        이 메서드는 Neo4j에서 query_type별 규칙과 제약사항을 가져와
        Jinja2 템플릿에 주입하여 질의를 생성합니다.

        Args:
            ocr_text (str): 이미지에서 추출한 OCR 텍스트.
            user_intent (Optional[str]): 사용자가 명시한 의도 또는 요구사항.
                None이면 OCR 텍스트만으로 질의 생성.
            cached_content (Optional[caching.CachedContent]): Gemini 캐시 객체.
                같은 OCR 텍스트로 반복 호출 시 캐시 재사용.
            template_name (Optional[str]): A/B 테스트용 템플릿 이름.
                None이면 기본 'system/query_gen.j2' 사용.
            query_type (str): 질의 유형. 'explanation', 'reasoning', 'summary' 등.
                Neo4j에서 해당 타입의 규칙을 조회하는 데 사용.
            kg (Optional[QAKnowledgeGraph]): 재사용할 Neo4j 연결 인스턴스.
            constraints (Optional[List[Dict[str, Any]]]): 미리 조회한 제약사항.

        Returns:
            List[str]: 생성된 전략적 쿼리 목록 (보통 3-4개).

        Examples:
            >>> agent = GeminiAgent(config)
            >>> queries = await agent.generate_query(
            ...     ocr_text="2024년 1분기 매출 100억원",
            ...     query_type="explanation"
            ... )
            >>> len(queries)
            3
            >>> queries[0]
            '2024년 1분기 매출 성과에 대해 설명해 주십시오.'
        """
        return await self.query_service.generate_query(
            ocr_text=ocr_text,
            user_intent=user_intent,
            cached_content=cached_content,
            template_name=template_name,
            query_type=query_type,
            kg=kg,
            constraints=constraints,
        )

    # ==================== 평가 ====================

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(
            (ValidationFailedError, ValidationError, json.JSONDecodeError),
        ),
        reraise=True,
    )
    @traced_async("gemini.evaluate_responses")
    async def evaluate_responses(
        self,
        ocr_text: str,
        query: str,
        candidates: dict[str, str],
        cached_content: caching.CachedContent | None = None,
        query_type: str = "explanation",
        kg: QAKnowledgeGraph | None = None,
    ) -> EvaluationResultSchema | None:
        """후보 답변을 평가하고 점수를 부여.

        여러 후보 답변 중 최적의 답변을 선택하기 위해 각 답변을 평가합니다.

        Args:
            ocr_text (str): 원본 OCR 텍스트 (평가 기준).
            query (str): 질의 문장.
            candidates (Dict[str, str]): 평가할 후보 답변들.
                키는 후보 식별자, 값은 답변 텍스트.
            cached_content (Optional[caching.CachedContent]): Gemini 캐시 객체.
            query_type (str): 질의 유형 (Neo4j 규칙 조회용).
            kg (Optional[QAKnowledgeGraph]): 재사용할 Neo4j 인스턴스.

        Returns:
            Optional[EvaluationResultSchema]: 평가 결과. 각 후보의 점수와
                선택된 최고 답변 정보를 포함. 평가 실패 시 None.

        Examples:
            >>> candidates = {
            ...     "A": "2024년 1분기 매출은 100억원입니다.",
            ...     "B": "매출이 100억원을 달성했습니다."
            ... }
            >>> result = await agent.evaluate_responses(
            ...     ocr_text="2024 Q1 매출: 100억",
            ...     query="매출에 대해 설명해주세요",
            ...     candidates=candidates
            ... )
            >>> result.best_answer
            'A'
        """
        return await self.evaluator_service.evaluate_responses(
            ocr_text=ocr_text,
            query=query,
            candidates=candidates,
            cached_content=cached_content,
            query_type=query_type,
            kg=kg,
        )

    # ==================== Rewrite ====================

    async def rewrite_best_answer(
        self,
        ocr_text: str,
        best_answer: str,
        edit_request: str | None = None,
        cached_content: caching.CachedContent | None = None,
        query_type: str = "explanation",
        kg: QAKnowledgeGraph | None = None,
        constraints: list[dict[str, Any]] | None = None,
        length_constraint: str = "",
    ) -> str:
        """선택된 최고 답변을 가독성 및 안전성 측면에서 개선.

        Neo4j에서 query_type별 규칙과 자주 틀리는 부분(CSV 데이터)을
        동적으로 주입하여 답변을 재작성합니다.

        Args:
            ocr_text (str): 원본 OCR 텍스트.
            best_answer (str): 재작성할 답변 텍스트.
            edit_request (Optional[str]): 사용자 지정 편집 요청사항.
            cached_content (Optional[caching.CachedContent]): Gemini 캐시 객체.
            query_type (str): 질의 유형 (Neo4j 규칙 조회용).
            kg (Optional[QAKnowledgeGraph]): 재사용할 Neo4j 인스턴스.
            constraints (Optional[List[Dict[str, Any]]]): 미리 조회한 제약사항.
            length_constraint (str): 글자 수 제약 (예: "200자 이내").

        Returns:
            str: 재작성된 답변. 오류 발생 시 원본 답변 반환.

        Examples:
            >>> rewritten = await agent.rewrite_best_answer(
            ...     ocr_text="2024 Q1 매출: 100억",
            ...     best_answer="매출은 100억원입니다.",
            ...     query_type="explanation"
            ... )
            >>> len(rewritten) > 0
            True
            >>> "100억" in rewritten
            True
        """
        return await self.rewriter_service.rewrite_best_answer(
            user_query=ocr_text,
            selected_answer=best_answer,
            edit_request=edit_request,
            formatting_rules=None,
            cached_content=cached_content,
            query_type=query_type,
        )

    # ==================== 비용 계산 ====================

    def get_total_cost(self) -> float:
        """세션의 총 API 비용 계산 (USD)."""
        return self._cost_tracker.get_total_cost()

    def get_budget_usage_percent(self) -> float:
        """예산 사용률 반환."""
        return self._cost_tracker.get_budget_usage_percent()

    def check_budget(self) -> None:
        """예산 초과 여부 확인."""
        self._cost_tracker.check_budget()

    # ==================== Streaming ====================

    async def generate_stream(
        self,
        prompt: str,
        *,
        system_instruction: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """스트리밍 방식으로 응답을 생성합니다.

        Args:
            prompt: 사용자 프롬프트.
            system_instruction: 선택적 시스템 프롬프트.
            temperature: 샘플링 온도.
            max_output_tokens: 최대 출력 토큰.
            **kwargs: 추가 생성 파라미터.

        Yields:
            생성된 텍스트 청크.
        """
        generation_config: dict[str, object] = {
            "temperature": temperature or self.config.temperature,
            "max_output_tokens": max_output_tokens or self.config.max_output_tokens,
        }
        gen_config_param = cast("Any", generation_config)
        model = self._genai.GenerativeModel(
            model_name=self.config.model_name,
            system_instruction=system_instruction,
            generation_config=gen_config_param,
            safety_settings=self.safety_settings,
        )

        response = await model.generate_content_async(prompt, stream=True, **kwargs)
        async for chunk in response:
            text = getattr(chunk, "text", "") or getattr(chunk, "candidates", None)
            if isinstance(text, list) and text and hasattr(text[0], "content"):
                # Fallback for structured chunk objects
                candidate_text = getattr(text[0], "text", None)
                if candidate_text:
                    yield candidate_text
            elif text:
                yield cast("str", text)


def __getattr__(name: str) -> Any:
    """Lazy import of the caching module.

    Args:
        name: The attribute name to retrieve.

    Returns:
        The caching module if name is 'caching'.

    Raises:
        AttributeError: If name is not 'caching'.
    """
    if name == "caching":
        import google.generativeai.caching as caching_mod

        globals()["caching"] = caching_mod
        return caching_mod
    raise AttributeError(name)
