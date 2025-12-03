# mypy: disable-error-code=misc
"""Gemini Agent 핵심 모듈.

GeminiAgent 클래스의 메인 로직을 포함합니다.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    List,
    Optional,
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
    import google.generativeai.caching as caching

    from src.core.interfaces import LLMProvider
    from src.qa.rag_system import QAKnowledgeGraph


def _get_log_metrics() -> Callable[..., None]:
    """log_metrics를 동적으로 가져옴 (테스트 패칭 지원)."""
    agent_mod = sys.modules.get("src.agent")
    if agent_mod and hasattr(agent_mod, "log_metrics"):
        return cast(Callable[..., None], agent_mod.log_metrics)
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
        jinja_env: Optional[Environment] = None,
        llm_provider: Optional["LLMProvider"] = None,
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
        self.llm_provider: Optional["LLMProvider"]
        if llm_provider is not None:
            self.llm_provider = llm_provider
        else:
            if getattr(config, "llm_provider_enabled", False):
                try:
                    from src.core.factory import get_llm_provider

                    self.llm_provider = get_llm_provider(config)
                except AttributeError:
                    self.llm_provider = None
            else:
                self.llm_provider = None

        # 서브모듈 초기화
        self._rate_limiter_module = RateLimiter(config.max_concurrency)
        self._cost_tracker = CostTracker(config)
        self._cache_manager = CacheManager(config)
        meter = get_meter()  # type: ignore[no-untyped-call]
        self._api_call_counter = meter.create_counter(
            "gemini.api.calls", description="Number of Gemini API calls"
        )
        self._token_counter = meter.create_counter(
            "gemini.tokens.total", description="Total tokens used"
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
                        f"Please ensure all .j2 files are in the templates/ directory."
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
        import google.generativeai.caching as caching

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

    def _get_safety_settings(self) -> Dict[Any, Any]:
        harm_block_threshold, harm_category = self._harm_types()
        return {
            category: harm_block_threshold.BLOCK_NONE
            for category in [
                harm_category.HARM_CATEGORY_HARASSMENT,
                harm_category.HARM_CATEGORY_HATE_SPEECH,
                harm_category.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                harm_category.HARM_CATEGORY_DANGEROUS_CONTENT,
            ]
        }

    # ==================== 캐시 관련 메서드 ====================

    def _track_cache_usage(self, cached: bool) -> None:
        """캐시 사용량 추적."""
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
            fingerprint, ttl_minutes, self._caching
        )

    def _store_local_cache(
        self, fingerprint: str, cache_name: str, ttl_minutes: int
    ) -> None:
        """로컬 캐시 저장."""
        self.context_manager.store_local_cache(fingerprint, cache_name, ttl_minutes)

    # ==================== 모델 생성 ====================

    def _create_generative_model(
        self,
        system_prompt: str,
        response_schema: type[BaseModel] | None = None,
        cached_content: Optional["caching.CachedContent"] = None,
    ) -> Any:
        """GenerativeModel 인스턴스를 생성하는 팩토리 메서드."""
        generation_config: Dict[str, object] = {
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_output_tokens,
        }

        if response_schema:
            generation_config["response_mime_type"] = "application/json"
            generation_config["response_schema"] = response_schema

        gen_config_param = cast(Any, generation_config)

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
            setattr(model, "_agent_system_instruction", system_prompt)
            setattr(model, "_agent_response_schema", response_schema)
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
                "Rate limit exceeded during cache creation: %s" % e
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
        user_intent: Optional[str] = None,
        cached_content: Optional["caching.CachedContent"] = None,
        template_name: Optional[str] = None,
        query_type: str = "explanation",
        kg: Optional["QAKnowledgeGraph"] = None,
        constraints: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        """OCR 텍스트와 사용자 의도에 기반한 전략적 쿼리 생성.

        Args:
            ocr_text: OCR 텍스트
            user_intent: 사용자 의도
            cached_content: 캐시된 컨텐츠
            template_name: 사용자 템플릿 이름 (A/B 테스트용, None이면 기본 템플릿 사용)
            query_type: 질의 유형 (Neo4j 규칙 조회용)
            kg: 재사용할 QAKnowledgeGraph 인스턴스 (없으면 새로 생성)
            constraints: Neo4j에서 미리 조회한 제약사항 리스트 (없으면 내부 조회)

        Returns:
            생성된 쿼리 목록
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
            (ValidationFailedError, ValidationError, json.JSONDecodeError)
        ),
        reraise=True,
    )
    @traced_async("gemini.evaluate_responses")
    async def evaluate_responses(
        self,
        ocr_text: str,
        query: str,
        candidates: Dict[str, str],
        cached_content: Optional["caching.CachedContent"] = None,
        query_type: str = "explanation",
        kg: Optional["QAKnowledgeGraph"] = None,
    ) -> Optional[EvaluationResultSchema]:
        """후보 답변을 평가하고 점수를 부여."""
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
        edit_request: Optional[str] = None,
        cached_content: Optional["caching.CachedContent"] = None,
        query_type: str = "explanation",
        kg: Optional["QAKnowledgeGraph"] = None,
        constraints: Optional[List[Dict[str, Any]]] = None,
        length_constraint: str = "",
    ) -> str:
        """선택된 최고 답변을 가독성 및 안전성 측면에서 개선.

        Neo4j 규칙을 동적으로 주입하여 templates/system/*.j2 사용.
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
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
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
        generation_config: Dict[str, object] = {
            "temperature": temperature or self.config.temperature,
            "max_output_tokens": max_output_tokens or self.config.max_output_tokens,
        }
        gen_config_param = cast(Any, generation_config)
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
                yield cast(str, text)


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
