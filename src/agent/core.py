# mypy: disable-error-code=misc
"""Gemini Agent 핵심 모듈.

GeminiAgent 클래스의 메인 로직을 포함합니다.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import sys
import time
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
from src.config.constants import MIN_CACHE_TOKENS
from src.config.exceptions import (
    APIRateLimitError,
    CacheCreationError,
    SafetyFilterError,
    ValidationFailedError,
)
from src.core.models import EvaluationResultSchema, QueryResult
from src.infra.logging import log_metrics as _log_metrics
from src.infra.telemetry import get_meter, traced_async
from src.infra.utils import clean_markdown_code_block, safe_json_parse

from .cache_manager import CacheManager
from .client import GeminiClient
from .context_manager import AgentContextManager
from .cost_tracker import CostTracker
from .rate_limiter import RateLimiter
from .retry_handler import RetryHandler

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
        self.client = GeminiClient(self)
        self.context_manager = AgentContextManager(self)
        self.retry_handler = RetryHandler(self)

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
        self._cache_manager.track_cache_usage(cached)

    def _local_cache_manifest_path(self) -> Any:
        """로컬 캐시 매니페스트 경로."""
        return self._cache_manager._local_cache_manifest_path()

    def _cleanup_expired_cache(self, ttl_minutes: int) -> None:
        """만료된 캐시 정리."""
        self._cache_manager.cleanup_expired_cache(ttl_minutes)

    def _load_local_cache(self, fingerprint: str, ttl_minutes: int) -> Any:
        """로컬 캐시 로드."""
        return self._cache_manager.load_local_cache(
            fingerprint, ttl_minutes, self._caching
        )

    def _store_local_cache(
        self, fingerprint: str, cache_name: str, ttl_minutes: int
    ) -> None:
        """로컬 캐시 저장."""
        self._cache_manager.store_local_cache(fingerprint, cache_name, ttl_minutes)

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
        system_prompt = self.jinja_env.get_template("system/eval.j2").render()
        combined_content = system_prompt + "\n\n" + ocr_text
        fingerprint = CacheManager.compute_fingerprint(combined_content)
        ttl_minutes = self.config.cache_ttl_minutes
        token_threshold = getattr(self.config, "cache_min_tokens", MIN_CACHE_TOKENS)

        local_cached = self._load_local_cache(fingerprint, ttl_minutes)
        if local_cached:
            self.logger.info("Reusing context cache from disk: %s", local_cached.name)
            return local_cached

        loop = asyncio.get_running_loop()

        def _count_tokens() -> int:
            model = self._genai.GenerativeModel(self.config.model_name)
            result: int = model.count_tokens(combined_content).total_tokens
            return result

        token_count = await loop.run_in_executor(None, _count_tokens)
        self.logger.info("Total Tokens for Caching: %s", token_count)

        if token_count < token_threshold:
            self.logger.info("Skipping cache creation (Tokens < %s)", token_threshold)
            return None

        try:

            def _create_cache() -> Any:
                return self._caching.CachedContent.create(
                    model=self.config.model_name,
                    display_name="ocr_context_cache",
                    system_instruction=system_prompt,
                    contents=[ocr_text],
                    ttl=datetime.timedelta(minutes=ttl_minutes),
                )

            cache = await loop.run_in_executor(None, _create_cache)
            self.logger.info(
                "Context Cache Created: %s (Expires in %sm)", cache.name, ttl_minutes
            )
            try:
                self._store_local_cache(fingerprint, cache.name, ttl_minutes)
            except OSError as e:
                self.logger.debug("Local cache manifest write skipped: %s", e)
            return cache
        except self._google_exceptions().ResourceExhausted as e:
            self.logger.error("Failed to create cache due to rate limit: %s", e)
            raise CacheCreationError(
                "Rate limit exceeded during cache creation: %s" % e
            ) from e
        except (ValueError, RuntimeError, OSError) as e:
            self.logger.error("Failed to create cache: %s", e)
            raise CacheCreationError("Failed to create cache: %s" % e) from e

    # ==================== API 호출 ====================

    async def _call_api_with_retry(self, model: Any, prompt_text: str) -> str:
        """재시도 로직이 포함된 API 호출."""
        exceptions = self._google_exceptions()
        retry_exceptions = (
            exceptions.ResourceExhausted,
            exceptions.ServiceUnavailable,
            exceptions.DeadlineExceeded,
            exceptions.Cancelled,
            TimeoutError,
        )

        async def _adaptive_backoff(attempt: int) -> None:
            self.api_retries += 1
            delay = min(10, 2 * attempt)
            self.logger.warning(
                "Retrying API call (attempt=%s, delay=%ss)", attempt, delay
            )
            await asyncio.sleep(delay)

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type(retry_exceptions),
            reraise=True,
        )
        async def _execute_with_retry() -> str:
            def _get_retry_attempt() -> int:
                """Extract attempt number from tenacity retry statistics."""
                retry_obj = getattr(_execute_with_retry, "retry", None)
                stats_dict: Dict[str, Any] = {}
                if retry_obj is not None and hasattr(retry_obj, "statistics"):
                    stats_dict = retry_obj.statistics
                return stats_dict.get("attempt_number", 1) or 1

            if self._rate_limiter:
                async with self._rate_limiter, self._semaphore:
                    try:
                        return await self._execute_api_call(model, prompt_text)
                    except retry_exceptions:
                        attempt = _get_retry_attempt()
                        await _adaptive_backoff(attempt)
                        raise
            async with self._semaphore:
                try:
                    return await self._execute_api_call(model, prompt_text)
                except retry_exceptions:
                    attempt = _get_retry_attempt()
                    await _adaptive_backoff(attempt)
                    raise

        try:
            result: str = await _execute_with_retry()
            return result
        except Exception:
            self.api_failures += 1
            raise

    async def _execute_api_call(self, model: Any, prompt_text: str) -> str:
        """실제 API 호출 로직."""
        if self.llm_provider:
            start = time.perf_counter()
            system_instruction = getattr(model, "_agent_system_instruction", None)
            response_schema = getattr(model, "_agent_response_schema", None)
            result = await self.llm_provider.generate_content_async(
                prompt_text,
                system_instruction=system_instruction,
                temperature=self.config.temperature,
                max_output_tokens=self.config.max_output_tokens,
                response_schema=response_schema,
                request_options={"timeout": self.config.timeout},
            )
            latency_ms = (time.perf_counter() - start) * 1000

            prompt_tokens = result.usage.get("prompt_tokens", 0)
            completion_tokens = result.usage.get("completion_tokens", 0)
            self._cost_tracker.add_tokens(prompt_tokens, completion_tokens)

            _get_log_metrics()(
                self.logger,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cache_hits=self.cache_hits,
                cache_misses=self.cache_misses,
                api_retries=self.api_retries,
                api_failures=self.api_failures,
            )

            finish_reason = result.finish_reason
            if finish_reason and finish_reason.upper() not in {"STOP", "MAX_TOKENS"}:
                safety_info = result.safety_ratings or ""
                raise SafetyFilterError(
                    "Blocked by safety filter or other reason: %s.%s"
                    % (finish_reason, safety_info)
                )
            return result.content

        protos = self._protos()
        self.logger.debug(
            "API Call - Model: %s, Prompt Length: %s",
            self.config.model_name,
            len(prompt_text),
        )
        start = time.perf_counter()
        response = await model.generate_content_async(
            prompt_text, request_options={"timeout": self.config.timeout}
        )
        latency_ms = (time.perf_counter() - start) * 1000
        self.logger.info("API latency: %.2f ms", latency_ms)

        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = response.usage_metadata
            self._cost_tracker.add_tokens(
                usage.prompt_token_count, usage.candidates_token_count
            )

            self.logger.info(
                "Token Usage - Prompt: %s, Response: %s, Total: %s",
                usage.prompt_token_count,
                usage.candidates_token_count,
                usage.total_token_count,
            )
            _get_log_metrics()(
                self.logger,
                latency_ms=latency_ms,
                prompt_tokens=usage.prompt_token_count,
                completion_tokens=usage.candidates_token_count,
                cache_hits=self.cache_hits,
                cache_misses=self.cache_misses,
                api_retries=self.api_retries,
                api_failures=self.api_failures,
            )

        if response.candidates:
            candidate = response.candidates[0]
            finish_reason = candidate.finish_reason
            self.logger.debug("API Response - Finish Reason: %s", finish_reason)

            if finish_reason not in [
                protos.Candidate.FinishReason.STOP,
                protos.Candidate.FinishReason.MAX_TOKENS,
            ]:
                safety_info = ""
                if hasattr(response, "prompt_feedback") and response.prompt_feedback:
                    safety_info = " Safety Ratings: %s" % response.prompt_feedback

                self.logger.warning(
                    "⚠️ Generation stopped unexpectedly. Finish Reason: %s.%s",
                    finish_reason,
                    safety_info,
                )
                raise SafetyFilterError(
                    "Blocked by safety filter or other reason: %s.%s"
                    % (finish_reason, safety_info)
                )

        try:
            return str(response.text)
        except ValueError:
            safety_info = ""
            if hasattr(response, "prompt_feedback") and response.prompt_feedback:
                safety_info = " Safety Filter: %s" % response.prompt_feedback

            error_msg = "No text content in response.%s" % safety_info
            self.logger.error(error_msg)

            if response.candidates and response.candidates[0].content.parts:
                parts = response.candidates[0].content.parts
                if len(parts) > 0 and hasattr(parts[0], "text"):
                    return str(parts[0].text)

            raise SafetyFilterError(error_msg)

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
        self._api_call_counter.add(1, {"operation": "generate_query"})
        user_template_name = template_name or "user/query_gen.j2"
        user_template = self.jinja_env.get_template(user_template_name)
        user_prompt = user_template.render(ocr_text=ocr_text, user_intent=user_intent)

        schema_json = json.dumps(
            QueryResult.model_json_schema(), indent=2, ensure_ascii=False
        )

        # constraints가 직접 전달되었으면 사용, 아니면 Neo4j 조회
        constraint_list = constraints if constraints is not None else []
        kg_obj = kg
        try:
            if not constraint_list and kg_obj is None:
                from src.qa.rag_system import QAKnowledgeGraph

                kg_obj = QAKnowledgeGraph()
            if not constraint_list and kg_obj is not None:
                all_constraints = kg_obj.get_constraints_for_query_type(query_type)
                constraint_list = [
                    c for c in all_constraints if c.get("category") in ["query", "both"]
                ]
        except Exception as e:  # noqa: BLE001
            self.logger.debug("Neo4j 제약사항 조회 실패: %s", e)

        # priority 높은 순으로 정렬
        if constraint_list:
            constraint_list.sort(key=lambda x: x.get("priority", 0), reverse=True)

        rules: List[str] = []
        try:
            if kg_obj is not None:
                rules = kg_obj.find_relevant_rules(ocr_text[:500], k=10)
        except Exception as e:  # noqa: BLE001
            self.logger.debug("Neo4j 규칙 조회 실패: %s", e)

        # Get formatting rules from Neo4j
        formatting_rules = ""
        try:
            if kg_obj:
                formatting_rules = kg_obj.get_formatting_rules("query_gen")
        except Exception as e:  # noqa: BLE001
            self.logger.debug("Formatting rules 조회 실패: %s", e)

        # Get CSV guide rules and common mistakes from Neo4j
        guide_rules: List[Dict[str, str]] = []
        common_mistakes: List[Dict[str, str]] = []
        try:
            from src.qa.template_rules import (
                get_all_template_context,
                get_neo4j_config,
            )

            neo4j_config = get_neo4j_config()
            if neo4j_config.get("neo4j_password"):
                template_context = get_all_template_context(
                    query_type=query_type,  # e.g. "explanation"
                    neo4j_uri=neo4j_config["neo4j_uri"],
                    neo4j_user=neo4j_config["neo4j_user"],
                    neo4j_password=neo4j_config["neo4j_password"],
                    include_mistakes=True,
                    context_stage="query",  # 질의 생성 단계임
                )
                guide_rules = template_context.get("guide_rules", []) or []
                common_mistakes = template_context.get("common_mistakes", []) or []
        except Exception as e:  # noqa: BLE001
            self.logger.debug("CSV 가이드 조회 실패 (선택사항): %s", e)

        system_template_name = "system/query_gen.j2"
        try:
            system_template = self.jinja_env.get_template(system_template_name)
            system_prompt = system_template.render(
                response_schema=schema_json,
                rules=rules,
                constraints=constraint_list,
                formatting_rules=formatting_rules,
                guide_rules=guide_rules,
                common_mistakes=common_mistakes,
            )
        except Exception as e:  # noqa: BLE001
            self.logger.debug("템플릿 렌더링 실패: %s", e)
            system_prompt = self.jinja_env.get_template(system_template_name).render(
                response_schema=schema_json,
                formatting_rules=formatting_rules,
                constraints=constraint_list,
            )

        model = self._create_generative_model(
            system_prompt, response_schema=QueryResult, cached_content=cached_content
        )

        self.context_manager.track_cache_usage(cached_content is not None)

        try:
            response_text = await self.retry_handler.call(model, user_prompt)
        except Exception as e:
            if self._is_rate_limit_error(e):
                raise APIRateLimitError(
                    "Rate limit exceeded during query generation: %s" % e
                ) from e
            raise

        cleaned_response = clean_markdown_code_block(response_text)
        if not cleaned_response or not cleaned_response.strip():
            self.logger.error("Query Generation: Empty response received")
            return []

        try:
            result = QueryResult.model_validate_json(cleaned_response)
            return result.queries if result.queries else []
        except ValidationError as e:
            self.logger.error(
                "Query Validation Failed: %s. Response: %s...",
                e,
                cleaned_response[:200],
            )
            return []
        except json.JSONDecodeError as e:
            self.logger.error(
                "Query JSON Parse Failed: %s. Response: %s...",
                e,
                cleaned_response[:200],
            )
            return []
        except (TypeError, KeyError, AttributeError) as e:
            self.logger.error("Unexpected error in query parsing: %s", e)
            return []

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
        if not query:
            return None
        self._api_call_counter.add(1, {"operation": "evaluate"})

        input_data = {
            "ocr_ground_truth": ocr_text,
            "target_query": query,
            "candidates": candidates,
        }

        rules: List[str] = []
        constraints: List[str] = []
        kg_obj = kg
        try:
            if kg_obj is None:
                from src.qa.rag_system import QAKnowledgeGraph

                kg_obj = QAKnowledgeGraph()
            constraint_list = kg_obj.get_constraints_for_query_type(query_type)
            for c in constraint_list:
                desc = c.get("description")
                if desc:
                    constraints.append(desc)
            rules = kg_obj.find_relevant_rules(ocr_text[:500], k=10)
        except Exception as e:  # noqa: BLE001
            self.logger.debug("Neo4j 규칙 조회 실패: %s", e)

        # Get formatting rules from Neo4j
        formatting_rules = ""
        try:
            if kg_obj:
                formatting_rules = kg_obj.get_formatting_rules("eval")
        except Exception as e:  # noqa: BLE001
            self.logger.debug("Formatting rules 조회 실패: %s", e)

        try:
            system_template = self.jinja_env.get_template("system/qa/compare_eval.j2")
            system_prompt = system_template.render(
                rules=rules,
                constraints=constraints,
                formatting_rules=formatting_rules,
            )
        except Exception as e:  # noqa: BLE001
            self.logger.debug("동적 템플릿 실패, 기본 사용: %s", e)
            system_prompt = self.jinja_env.get_template("system/eval.j2").render(
                formatting_rules=formatting_rules
            )

        model = self._create_generative_model(
            system_prompt,
            response_schema=EvaluationResultSchema,
            cached_content=cached_content,
        )

        self.context_manager.track_cache_usage(cached_content is not None)

        try:
            response_text = await self.retry_handler.call(
                model, json.dumps(input_data, ensure_ascii=False)
            )
        except Exception as e:
            if self._is_rate_limit_error(e):
                raise APIRateLimitError(
                    "Rate limit exceeded during evaluation: %s" % e
                ) from e
            raise
        cleaned_response = clean_markdown_code_block(response_text)

        if not cleaned_response or not cleaned_response.strip():
            self.logger.error("Evaluation: Empty response received")
            raise ValueError("Empty evaluation response")

        try:
            result = EvaluationResultSchema.model_validate_json(cleaned_response)
            return result
        except ValidationError as e:
            self.logger.error(
                "Evaluation Validation Failed: %s. Response: %s...",
                e,
                cleaned_response[:200],
            )
            raise ValidationFailedError("Evaluation validation failed: %s" % e) from e
        except json.JSONDecodeError as e:
            self.logger.error(
                "Evaluation JSON Parse Failed: %s. Response: %s...",
                e,
                cleaned_response[:200],
            )
            raise ValidationFailedError("Evaluation JSON parsing failed: %s" % e) from e

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
        from src.qa.rag_system import QAKnowledgeGraph

        template = self.jinja_env.get_template("user/rewrite.j2")
        payload = template.render(
            ocr_text=ocr_text, best_answer=best_answer, edit_request=edit_request
        )

        # constraints가 직접 전달되었으면 사용, 아니면 Neo4j 조회
        constraint_list = constraints if constraints is not None else []
        rules: List[str] = []
        kg_obj = kg
        try:
            if not constraint_list and kg_obj is None:
                from src.qa.rag_system import QAKnowledgeGraph

                kg_obj = QAKnowledgeGraph()
            if not constraint_list and kg_obj is not None:
                all_constraints = kg_obj.get_constraints_for_query_type(query_type)
                constraint_list = [
                    c
                    for c in all_constraints
                    if c.get("category") in ["answer", "both"]
                ]
            if kg_obj is not None:
                rules = kg_obj.find_relevant_rules(best_answer[:500], k=10)
        except Exception as e:  # noqa: BLE001
            self.logger.warning("Neo4j 규칙 조회 실패, 기본 템플릿 사용: %s", e)

        # priority 높은 순으로 정렬
        if constraint_list:
            constraint_list.sort(key=lambda x: x.get("priority", 0), reverse=True)

        # Get formatting rules from Neo4j
        formatting_rules = ""
        try:
            if kg_obj:
                formatting_rules = kg_obj.get_formatting_rules("rewrite")
        except Exception as e:  # noqa: BLE001
            self.logger.debug("Formatting rules 조회 실패: %s", e)

        # Get CSV guide rules and common mistakes from Neo4j
        guide_rules: List[Dict[str, str]] = []
        common_mistakes: List[Dict[str, str]] = []
        try:
            from src.qa.template_rules import (
                get_all_template_context,
                get_neo4j_config,
            )

            neo4j_config = get_neo4j_config()
            if neo4j_config.get("neo4j_password"):  # Neo4j 설정이 있으면
                template_context = get_all_template_context(
                    query_type=query_type,
                    neo4j_uri=neo4j_config["neo4j_uri"],
                    neo4j_user=neo4j_config["neo4j_user"],
                    neo4j_password=neo4j_config["neo4j_password"],
                    include_mistakes=True,
                )
                guide_rules = template_context.get("guide_rules", []) or []
                common_mistakes = template_context.get("common_mistakes", []) or []
                self.logger.debug(
                    "CSV 가이드 로드: rules=%d, mistakes=%d",
                    len(guide_rules),
                    len(common_mistakes),
                )
        except Exception as e:  # noqa: BLE001
            self.logger.debug("CSV 가이드 조회 실패 (선택사항): %s", e)

        try:
            system_template = self.jinja_env.get_template("system/qa/rewrite.j2")
            system_prompt = system_template.render(
                rules=rules,
                constraints=constraint_list,
                guide_rules=guide_rules,
                common_mistakes=common_mistakes,
                has_table_chart=False,
                formatting_rules=formatting_rules,
                length_constraint=length_constraint,
            )
        except Exception as e:  # noqa: BLE001
            self.logger.warning("동적 템플릿 실패, 기본 사용: %s", e)
            system_prompt = self.jinja_env.get_template("system/rewrite.j2").render(
                formatting_rules=formatting_rules,
                constraints=constraint_list,
                length_constraint=length_constraint,
            )

        model = self._create_generative_model(
            system_prompt, cached_content=cached_content
        )

        self.context_manager.track_cache_usage(cached_content is not None)

        try:
            response_text = await self.retry_handler.call(model, payload)
        except Exception as e:
            if self._is_rate_limit_error(e):
                raise APIRateLimitError(
                    "Rate limit exceeded during rewrite: %s" % e
                ) from e
            raise

        unwrapped = safe_json_parse(response_text, "rewritten_answer")

        if isinstance(unwrapped, str):
            return unwrapped

        return response_text if response_text else ""

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
