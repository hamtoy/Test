"""GeminiAgent 메인 클래스."""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.agent.cache_manager import CacheManager
from src.agent.cost_tracker import CostTracker
from src.agent.rate_limiter import RateLimitManager
from src.config import AppConfig
from src.constants import MIN_CACHE_TOKENS
from src.core.factory import get_llm_provider
from src.core.interfaces import LLMProvider
from src.exceptions import (
    APIRateLimitError,
    CacheCreationError,
    SafetyFilterError,
    ValidationFailedError,
)
from src.logging_setup import log_metrics
from src.models import EvaluationResultSchema, QueryResult
from src.utils import clean_markdown_code_block, safe_json_parse

if TYPE_CHECKING:
    import google.generativeai as genai
    import google.generativeai.caching as caching


class GeminiAgent:
    """Gemini API와의 통신을 담당하는 에이전트 (Refactored).

    주요 기능:
    - 의존성 주입을 통한 테스트 용이성 확보
    - Rate limiting 및 동시성 제어 (RateLimitManager 위임)
    - 비용 추적 (CostTracker 위임)
    - 캐시 관리 (CacheManager 위임)
    """

    def __init__(
        self,
        config: AppConfig,
        jinja_env: Optional[Environment] = None,
        llm_provider: Optional[LLMProvider] = None,
    ):
        self.logger = logging.getLogger("GeminiWorkflow")
        self.config = config

        # 컴포넌트 초기화
        self.cost_tracker = CostTracker(
            model_name=config.model_name, budget_limit_usd=config.budget_limit_usd
        )
        self.rate_limiter = RateLimitManager(max_concurrency=config.max_concurrency)

        # Resolve cache directory
        cache_path = Path(config.local_cache_dir)
        if not cache_path.is_absolute():
            cache_path = config.base_dir / cache_path

        self.cache_manager = CacheManager(
            cache_dir=cache_path, ttl_minutes=config.cache_ttl_minutes
        )

        # LLM Provider 설정
        self.llm_provider: Optional[LLMProvider]
        if llm_provider is not None:
            self.llm_provider = llm_provider
        else:
            if getattr(config, "llm_provider_enabled", False):
                try:
                    self.llm_provider = get_llm_provider(config)
                except AttributeError:
                    self.llm_provider = None
            else:
                self.llm_provider = None

        self.safety_settings = self._get_safety_settings()
        self.api_retries = 0
        self.api_failures = 0

        # Jinja 환경 설정
        if jinja_env is not None:
            self.jinja_env = jinja_env
        else:
            self._init_jinja_env()

    def _init_jinja_env(self) -> None:
        required_templates = [
            "prompt_eval.j2",
            "prompt_query_gen.j2",
            "prompt_rewrite.j2",
            "query_gen_user.j2",
            "rewrite_user.j2",
        ]
        for template_name in required_templates:
            template_path = self.config.template_dir / template_name
            if not template_path.exists():
                raise FileNotFoundError(
                    f"Required template not found: {template_path}\n"
                    f"Please ensure all .j2 files are in the templates/ directory."
                )
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.config.template_dir),
            autoescape=True,
        )

    # --- Properties for Backward Compatibility ---
    @property
    def total_input_tokens(self) -> int:
        return self.cost_tracker.total_input_tokens

    @total_input_tokens.setter
    def total_input_tokens(self, value: int) -> None:
        # Allow setting for tests or manual adjustments
        self.cost_tracker.total_input_tokens = value

    @property
    def total_output_tokens(self) -> int:
        return self.cost_tracker.total_output_tokens

    @total_output_tokens.setter
    def total_output_tokens(self, value: int) -> None:
        self.cost_tracker.total_output_tokens = value

    @property
    def cache_hits(self) -> int:
        return self.cache_manager.cache_hits

    @cache_hits.setter
    def cache_hits(self, value: int) -> None:
        self.cache_manager.cache_hits = value

    @property
    def cache_misses(self) -> int:
        return self.cache_manager.cache_misses

    @cache_misses.setter
    def cache_misses(self, value: int) -> None:
        self.cache_manager.cache_misses = value

    @property
    def _rate_limiter(self):
        return self.rate_limiter.limiter

    @_rate_limiter.setter
    def _rate_limiter(self, value):
        self.rate_limiter.limiter = value

    @property
    def _semaphore(self):
        return self.rate_limiter.semaphore

    @_semaphore.setter
    def _semaphore(self, value):
        self.rate_limiter.semaphore = value

    # --- Helper Properties ---
    @property
    def _genai(self):
        import google.generativeai as genai

        return genai

    @property
    def _caching(self):
        cached = globals().get("caching")
        if cached is not None:
            return cached
        import google.generativeai.caching as caching

        globals()["caching"] = caching
        return caching

    @staticmethod
    def _google_exceptions():
        from google.api_core import exceptions as google_exceptions

        return google_exceptions

    @staticmethod
    def _protos():
        from google.generativeai import protos

        return protos

    @staticmethod
    def _harm_types():
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

    def _is_rate_limit_error(self, exc: Exception) -> bool:
        try:
            google_exceptions = self._google_exceptions()
            if isinstance(exc, google_exceptions.ResourceExhausted):
                return True
        except (ImportError, AttributeError):
            pass
        return exc.__class__.__name__ == "ResourceExhausted"

    # --- Private Methods for Backward Compatibility (Proxies) ---
    def _store_local_cache(
        self, fingerprint: str, cache_name: str, ttl_minutes: int
    ) -> None:
        self.cache_manager.store_cache(fingerprint, cache_name, ttl_minutes)

    def _load_local_cache(
        self, fingerprint: str, ttl_minutes: Optional[int] = None
    ) -> Any:
        # Note: ttl_minutes is ignored in new implementation or handled differently
        return self.cache_manager.load_cached(fingerprint, self._caching)

    def _local_cache_manifest_path(self) -> Path:
        return self.cache_manager._resolve_manifest_path(self.cache_manager.cache_dir)

    def _cleanup_expired_cache(self, ttl_minutes: int) -> None:
        self.cache_manager.cleanup_expired(ttl_minutes)

    def _get_fingerprint(self, content: str) -> str:
        return self.cache_manager.get_fingerprint(content)

    # --- Core Methods ---

    def get_total_cost(self) -> float:
        return self.cost_tracker.get_total_cost()

    def get_budget_usage_percent(self) -> float:
        return self.cost_tracker.get_budget_usage_percent()

    def check_budget(self) -> None:
        self.cost_tracker.check_budget()

    def _create_generative_model(
        self,
        system_prompt: str,
        response_schema: type[BaseModel] | None = None,
        cached_content: Optional["caching.CachedContent"] = None,
    ) -> "genai.GenerativeModel":
        generation_config: Dict[str, object] = {
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_output_tokens,
        }

        if response_schema:
            generation_config["response_mime_type"] = "application/json"
            generation_config["response_schema"] = response_schema

        gen_config_param = cast(Any, generation_config)

        if cached_content:
            model = self._genai.GenerativeModel.from_cached_content(  # type: ignore
                cached_content=cached_content,
                generation_config=gen_config_param,
                safety_settings=self.safety_settings,
            )
        else:
            model = self._genai.GenerativeModel(  # type: ignore
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

    async def create_context_cache(
        self, ocr_text: str
    ) -> Optional["caching.CachedContent"]:
        system_prompt = self.jinja_env.get_template("prompt_eval.j2").render()
        combined_content = system_prompt + "\n\n" + ocr_text
        fingerprint = self.cache_manager.get_fingerprint(combined_content)

        # Try loading from local cache
        local_cached = self.cache_manager.load_cached(fingerprint, self._caching)
        if local_cached:
            self.logger.info("Reusing context cache from disk: %s", local_cached.name)
            return local_cached

        loop = asyncio.get_running_loop()
        token_threshold = getattr(self.config, "cache_min_tokens", MIN_CACHE_TOKENS)

        def _count_tokens() -> int:
            model = self._genai.GenerativeModel(self.config.model_name)
            return model.count_tokens(combined_content).total_tokens

        token_count = await loop.run_in_executor(None, _count_tokens)
        self.logger.info("Total Tokens for Caching: %s", token_count)

        if token_count < token_threshold:
            self.logger.info("Skipping cache creation (Tokens < %s)", token_threshold)
            return None

        try:

            def _create_cache():
                return self._caching.CachedContent.create(
                    model=self.config.model_name,
                    display_name="ocr_context_cache",
                    system_instruction=system_prompt,
                    contents=[ocr_text],
                    ttl=datetime.timedelta(minutes=self.config.cache_ttl_minutes),
                )

            cache = await loop.run_in_executor(None, _create_cache)
            self.logger.info(
                "Context Cache Created: %s (Expires in %sm)",
                cache.name,
                self.config.cache_ttl_minutes,
            )
            try:
                self.cache_manager.store_cache(
                    fingerprint, cache.name, self.config.cache_ttl_minutes
                )
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

    async def _call_api_with_retry(
        self, model: "genai.GenerativeModel", prompt_text: str
    ) -> str:
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
        async def _execute_with_retry():
            limiter = self.rate_limiter.limiter
            semaphore = self.rate_limiter.semaphore

            if limiter:
                async with limiter, semaphore:
                    try:
                        return await self._execute_api_call(model, prompt_text)
                    except retry_exceptions:
                        stats = getattr(_execute_with_retry.retry, "statistics", {})  # type: ignore
                        attempt = stats.get("attempt_number", 1) or 1
                        await _adaptive_backoff(attempt)
                        raise

            async with semaphore:
                try:
                    return await self._execute_api_call(model, prompt_text)
                except retry_exceptions:
                    stats = getattr(_execute_with_retry.retry, "statistics", {})  # type: ignore
                    attempt = stats.get("attempt_number", 1) or 1
                    await _adaptive_backoff(attempt)
                    raise

        try:
            return await _execute_with_retry()
        except Exception:
            self.api_failures += 1
            raise

    async def _execute_api_call(
        self, model: "genai.GenerativeModel", prompt_text: str
    ) -> str:
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
            self.cost_tracker.record_usage(prompt_tokens, completion_tokens)

            log_metrics(
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
            self.cost_tracker.record_usage(
                usage.prompt_token_count, usage.candidates_token_count
            )

            self.logger.info(
                "Token Usage - Prompt: %s, Response: %s, Total: %s",
                usage.prompt_token_count,
                usage.candidates_token_count,
                usage.total_token_count,
            )
            log_metrics(
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
            return response.text
        except ValueError:
            safety_info = ""
            if hasattr(response, "prompt_feedback") and response.prompt_feedback:
                safety_info = " Safety Filter: %s" % response.prompt_feedback

            error_msg = "No text content in response.%s" % safety_info
            self.logger.error(error_msg)

            if response.candidates and response.candidates[0].content.parts:
                parts = response.candidates[0].content.parts
                if len(parts) > 0 and hasattr(parts[0], "text"):
                    return parts[0].text

            raise SafetyFilterError(error_msg)

    async def generate_query(
        self, ocr_text: str, user_intent: Optional[str] = None
    ) -> List[str]:
        template = self.jinja_env.get_template("query_gen_user.j2")
        user_prompt = template.render(ocr_text=ocr_text, user_intent=user_intent)

        schema_json = json.dumps(
            QueryResult.model_json_schema(), indent=2, ensure_ascii=False
        )

        system_prompt = self.jinja_env.get_template("prompt_query_gen.j2").render(
            response_schema=schema_json
        )

        model = self._create_generative_model(
            system_prompt, response_schema=QueryResult
        )

        try:
            response_text = await self._call_api_with_retry(model, user_prompt)
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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(
            (ValidationFailedError, ValidationError, json.JSONDecodeError)
        ),
        reraise=True,
    )
    async def evaluate_responses(
        self,
        ocr_text: str,
        query: str,
        candidates: Dict[str, str],
        cached_content: Optional["caching.CachedContent"] = None,
    ) -> Optional[EvaluationResultSchema]:
        if not query:
            return None

        input_data = {
            "ocr_ground_truth": ocr_text,
            "target_query": query,
            "candidates": candidates,
        }

        system_prompt = self.jinja_env.get_template("prompt_eval.j2").render()

        model = self._create_generative_model(
            system_prompt,
            response_schema=EvaluationResultSchema,
            cached_content=cached_content,
        )

        self.cache_manager.track_usage(cached_content is not None)

        try:
            response_text = await self._call_api_with_retry(
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

    async def rewrite_best_answer(
        self,
        ocr_text: str,
        best_answer: str,
        cached_content: Optional["caching.CachedContent"] = None,
    ) -> str:
        template = self.jinja_env.get_template("rewrite_user.j2")
        payload = template.render(ocr_text=ocr_text, best_answer=best_answer)

        system_prompt = self.jinja_env.get_template("prompt_rewrite.j2").render()

        model = self._create_generative_model(
            system_prompt, cached_content=cached_content
        )

        self.cache_manager.track_usage(cached_content is not None)

        try:
            response_text = await self._call_api_with_retry(model, payload)
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
