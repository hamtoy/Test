import asyncio
import datetime
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

import google.generativeai as genai
import google.generativeai.caching as caching
from google.api_core import exceptions as google_exceptions
from google.generativeai import protos
from google.generativeai.types import HarmBlockThreshold, HarmCategory
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import AppConfig
from src.constants import (
    DEFAULT_RPM_LIMIT,
    DEFAULT_RPM_WINDOW_SECONDS,
    MIN_CACHE_TOKENS,
    PRICING_TIERS,
)
from src.exceptions import (
    APIRateLimitError,
    BudgetExceededError,
    CacheCreationError,
    SafetyFilterError,
    ValidationFailedError,
)
from src.models import EvaluationResultSchema, QueryResult
from src.utils import clean_markdown_code_block, safe_json_parse

if TYPE_CHECKING:
    from aiolimiter import AsyncLimiter


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

    def __init__(self, config: AppConfig, jinja_env: Optional[Environment] = None):
        """Gemini API 에이전트 초기화.

        Args:
            config: 애플리케이션 설정 (API 키, 타임아웃, 동시성 등)
            jinja_env: Jinja2 환경 (테스트 시 mock 주입 가능, 없으면 생성)

        Raises:
            FileNotFoundError: 필수 템플릿 파일이 누락된 경우
        """
        self.logger = logging.getLogger("GeminiWorkflow")
        self.config = config

        # 동시 실행 개수 제한
        self._semaphore = asyncio.Semaphore(config.max_concurrency)
        self._rate_limiter: Optional["AsyncLimiter"] = None

        # RPM(분당 요청 수) 제한 - 429 에러 방지
        try:
            from aiolimiter import AsyncLimiter

            # Gemini API 기본 RPM: DEFAULT_RPM_LIMIT (1분에 DEFAULT_RPM_LIMIT개)
            self._rate_limiter = AsyncLimiter(
                max_rate=DEFAULT_RPM_LIMIT, time_period=DEFAULT_RPM_WINDOW_SECONDS
            )
            self.logger.info(
                "Rate limiter enabled: %s requests/%s seconds",
                DEFAULT_RPM_LIMIT,
                DEFAULT_RPM_WINDOW_SECONDS,
            )
        except ImportError:
            self._rate_limiter = None
            self.logger.warning("aiolimiter not installed. Rate limiting disabled.")

        self.safety_settings = self._get_safety_settings()

        # 토큰 사용량 누적
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        # 캐시 적중률 추적
        self.cache_hits = 0
        self.cache_misses = 0

        # 외부에서 주입하거나, 없으면 생성 (Dependency Injection)
        if jinja_env is not None:
            self.jinja_env = jinja_env
        else:
            # 필수 템플릿 파일 존재 확인 (없으면 즉시 실패)
            required_templates = [
                "prompt_eval.j2",
                "prompt_query_gen.j2",
                "prompt_rewrite.j2",
                "query_gen_user.j2",
                "rewrite_user.j2",
            ]

            for template_name in required_templates:
                template_path = config.template_dir / template_name
                if not template_path.exists():
                    raise FileNotFoundError(
                        f"Required template not found: {template_path}\n"
                        f"Please ensure all .j2 files are in the templates/ directory."
                    )

            # 템플릿 엔진 초기화
            self.jinja_env = Environment(
                loader=FileSystemLoader(config.template_dir),
                autoescape=True,  # XSS 방지
            )

    def _get_safety_settings(self) -> Dict[HarmCategory, HarmBlockThreshold]:
        settings: Dict[HarmCategory, HarmBlockThreshold] = {
            category: cast(HarmBlockThreshold, HarmBlockThreshold.BLOCK_NONE)
            for category in [
                HarmCategory.HARM_CATEGORY_HARASSMENT,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            ]
        }
        return settings

    def _create_generative_model(
        self,
        system_prompt: str,
        response_schema: type[BaseModel] | None = None,
        cached_content: Optional[caching.CachedContent] = None,
    ) -> genai.GenerativeModel:
        """
        [Factory Method] GenerativeModel 생성
        - cached_content가 있으면 이를 사용하여 모델 생성 (Context Caching)
        """
        generation_config: Dict[str, object] = {
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_output_tokens,
        }

        if response_schema:
            generation_config["response_mime_type"] = "application/json"
            generation_config["response_schema"] = response_schema

        # 캐시된 컨텐츠가 있으면 이를 기반으로 모델 생성 (Context Caching)
        gen_config_param = cast(Any, generation_config)

        if cached_content:
            return genai.GenerativeModel.from_cached_content(  # type: ignore[arg-type,call-overload]
                cached_content=cached_content,
                generation_config=gen_config_param,
                safety_settings=self.safety_settings,
            )

        return genai.GenerativeModel(  # type: ignore[arg-type,call-overload]
            model_name=self.config.model_name,
            system_instruction=system_prompt,
            generation_config=gen_config_param,
            safety_settings=self.safety_settings,
        )

    def _local_cache_manifest_path(self) -> Path:
        base = Path(self.config.local_cache_dir)
        if not base.is_absolute():
            base = self.config.base_dir / base
        return base / "context_cache.json"

    def _cleanup_expired_cache(self, ttl_minutes: int) -> None:
        """Remove expired cache entries from the local manifest (best-effort)."""
        manifest_path = self._local_cache_manifest_path()
        if not manifest_path.exists():
            return
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self.logger.debug(f"Cache cleanup skipped (read error): {e}")
            return

        now = datetime.datetime.now(datetime.timezone.utc)
        updated: dict[str, dict[str, Any]] = {}

        for fingerprint, entry in data.items():
            created_raw = entry.get("created")
            created = (
                datetime.datetime.fromisoformat(created_raw) if created_raw else None
            )
            if created is None:
                continue
            if created.tzinfo is None:
                created = created.replace(tzinfo=datetime.timezone.utc)
            ttl = int(entry.get("ttl_minutes", ttl_minutes) or ttl_minutes)
            if now - created <= datetime.timedelta(minutes=ttl):
                updated[fingerprint] = entry

        if len(updated) == len(data):
            return

        try:
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(updated, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.debug(f"Cache cleanup skipped (write error): {e}")

    def _load_local_cache(
        self, fingerprint: str, ttl_minutes: int
    ) -> Optional[caching.CachedContent]:
        manifest_path = self._local_cache_manifest_path()
        if not manifest_path.exists():
            return None
        # Remove expired entries to keep manifest small and clean
        self._cleanup_expired_cache(ttl_minutes)
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            entry = data.get(fingerprint)
            if not entry:
                return None
            created_raw = entry.get("created")
            created = (
                datetime.datetime.fromisoformat(created_raw) if created_raw else None
            )
            if created is None:
                return None
            ttl_raw = entry.get("ttl_minutes", ttl_minutes)
            ttl = int(ttl_raw) if ttl_raw is not None else ttl_minutes
            now = datetime.datetime.now(datetime.timezone.utc)
            if created.tzinfo is None:
                created = created.replace(tzinfo=datetime.timezone.utc)
            if now - created > datetime.timedelta(minutes=ttl):
                return None
            cache_name = entry.get("name")
            if cache_name:
                return caching.CachedContent.get(name=cache_name)
        except Exception as e:
            self.logger.debug(f"Local cache load skipped: {e}")
        return None

    def _store_local_cache(
        self, fingerprint: str, cache_name: str, ttl_minutes: int
    ) -> None:
        manifest_path = self._local_cache_manifest_path()
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data[fingerprint] = {
            "name": cache_name,
            "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "ttl_minutes": ttl_minutes,
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def create_context_cache(
        self, ocr_text: str
    ) -> Optional[caching.CachedContent]:
        """OCR 텍스트를 기반으로 Gemini Context Cache 생성.

        MIN_CACHE_TOKENS 이상일 때만 캐시를 생성하며, 로컬 디스크 캐시로 재사용을 시도합니다.

        Args:
            ocr_text: 캐시할 OCR 텍스트

        Returns:
            생성된 캐시 객체. 토큰이 부족하거나 실패 시 None

        Raises:
            CacheCreationError: 캐시 생성 실패 시
        """
        # 1. 시스템 프롬프트 렌더링 (평가용 기준)
        system_prompt = self.jinja_env.get_template("prompt_eval.j2").render()
        combined_content = system_prompt + "\n\n" + ocr_text
        fingerprint = hashlib.sha256(combined_content.encode("utf-8")).hexdigest()
        ttl_minutes = self.config.cache_ttl_minutes

        # 재사용 가능한 캐시가 있으면 반환 (Local Disk Cache)
        local_cached = self._load_local_cache(fingerprint, ttl_minutes)
        if local_cached:
            self.logger.info(f"Reusing context cache from disk: {local_cached.name}")
            return local_cached

        loop = asyncio.get_running_loop()

        # 2. 토큰 수 계산을 블로킹하지 않도록 오프로드
        def _count_tokens() -> int:
            model = genai.GenerativeModel(self.config.model_name)
            return model.count_tokens(combined_content).total_tokens

        token_count = await loop.run_in_executor(None, _count_tokens)
        self.logger.info(f"Total Tokens for Caching: {token_count}")

        if token_count < MIN_CACHE_TOKENS:
            self.logger.info("Skipping cache creation (Tokens < %s)", MIN_CACHE_TOKENS)
            return None

        try:
            # 3. 캐시 생성 (Configurable TTL) - 블로킹 호출 오프로드
            def _create_cache():
                return caching.CachedContent.create(
                    model=self.config.model_name,
                    display_name="ocr_context_cache",
                    system_instruction=system_prompt,
                    contents=[ocr_text],
                    ttl=datetime.timedelta(minutes=ttl_minutes),
                )

            cache = await loop.run_in_executor(None, _create_cache)
            self.logger.info(
                f"Context Cache Created: {cache.name} (Expires in {ttl_minutes}m)"
            )
            try:
                self._store_local_cache(fingerprint, cache.name, ttl_minutes)
            except Exception as e:
                self.logger.debug(f"Local cache manifest write skipped: {e}")
            return cache
        except google_exceptions.ResourceExhausted as e:
            self.logger.error(f"Failed to create cache due to rate limit: {e}")
            raise CacheCreationError(
                f"Rate limit exceeded during cache creation: {e}"
            ) from e
        except Exception as e:
            self.logger.error(f"Failed to create cache: {e}")
            raise CacheCreationError(f"Failed to create cache: {e}") from e

    # [Retry Logic] Tenacity 라이브러리 사용
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(
            (
                google_exceptions.ResourceExhausted,
                google_exceptions.ServiceUnavailable,
                google_exceptions.DeadlineExceeded,
                TimeoutError,
            )
        ),
        reraise=True,
    )
    async def _call_api_with_retry(
        self, model: genai.GenerativeModel, prompt_text: str
    ) -> str:
        """[Retry Logic] 재시도 로직이 데코레이터로 추상화됨"""
        # RPM 제어 (시간 기반)
        if self._rate_limiter:
            async with self._rate_limiter:
                # 동시 실행 개수 제어 (공간 기반)
                async with self._semaphore:
                    return await self._execute_api_call(model, prompt_text)
        else:
            async with self._semaphore:
                return await self._execute_api_call(model, prompt_text)

    async def _execute_api_call(
        self, model: genai.GenerativeModel, prompt_text: str
    ) -> str:
        """실제 API 호출 로직"""
        self.logger.debug(
            f"API Call - Model: {self.config.model_name}, Prompt Length: {len(prompt_text)}"
        )
        start = time.perf_counter()
        response = await model.generate_content_async(
            prompt_text, request_options={"timeout": self.config.timeout}
        )
        latency_ms = (time.perf_counter() - start) * 1000
        self.logger.info(f"API latency: {latency_ms:.2f} ms")

        # 토큰 사용량 로깅 및 누적
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = response.usage_metadata
            self.total_input_tokens += usage.prompt_token_count
            self.total_output_tokens += usage.candidates_token_count

            self.logger.info(
                f"Token Usage - Prompt: {usage.prompt_token_count}, "
                f"Response: {usage.candidates_token_count}, "
                f"Total: {usage.total_token_count}"
            )

        # Finish Reason 및 Safety Filter 상세 검증
        if response.candidates:
            candidate = response.candidates[0]
            finish_reason = candidate.finish_reason
            self.logger.debug(f"API Response - Finish Reason: {finish_reason}")

            if finish_reason not in [
                protos.Candidate.FinishReason.STOP,
                protos.Candidate.FinishReason.MAX_TOKENS,
            ]:
                # Safety filter나 기타 이유로 중단됨
                safety_info = ""
                if hasattr(response, "prompt_feedback") and response.prompt_feedback:
                    safety_info = f" Safety Ratings: {response.prompt_feedback}"

                self.logger.warning(
                    f"⚠️ Generation stopped unexpectedly. "
                    f"Finish Reason: {finish_reason}.{safety_info}"
                )
                raise SafetyFilterError(
                    f"Blocked by safety filter or other reason: {finish_reason}.{safety_info}"
                )

        try:
            return response.text
        except ValueError:
            # Safety filter 정보 포함
            safety_info = ""
            if hasattr(response, "prompt_feedback") and response.prompt_feedback:
                safety_info = f" Safety Filter: {response.prompt_feedback}"

            error_msg = f"No text content in response.{safety_info}"
            self.logger.error(error_msg)

            # 텍스트 추출 실패 시 수동 추출 시도 (빈 상자 확인)
            if response.candidates and response.candidates[0].content.parts:
                parts = response.candidates[0].content.parts
                if len(parts) > 0 and hasattr(parts[0], "text"):
                    return parts[0].text

            raise SafetyFilterError(error_msg)

    async def generate_query(
        self, ocr_text: str, user_intent: Optional[str] = None
    ) -> List[str]:
        """
        Generate strategic queries based on OCR text and optional user intent.

        Returns an empty list on invalid/empty responses; raises APIRateLimitError on rate limiting.
        """
        # 템플릿 렌더링
        template = self.jinja_env.get_template("query_gen_user.j2")
        user_prompt = template.render(ocr_text=ocr_text, user_intent=user_intent)

        # Pydantic 스키마 추출 및 주입
        schema_json = json.dumps(
            QueryResult.model_json_schema(), indent=2, ensure_ascii=False
        )

        # 시스템 프롬프트 렌더링
        system_prompt = self.jinja_env.get_template("prompt_query_gen.j2").render(
            response_schema=schema_json
        )

        # Pydantic 모델 전달 (JSON Mode)
        model = self._create_generative_model(
            system_prompt, response_schema=QueryResult
        )

        try:
            response_text = await self._call_api_with_retry(model, user_prompt)
        except google_exceptions.ResourceExhausted as e:
            raise APIRateLimitError(
                f"Rate limit exceeded during query generation: {e}"
            ) from e

        # Pydantic Validation 사용 (안전한 파싱)
        cleaned_response = clean_markdown_code_block(response_text)
        if not cleaned_response or not cleaned_response.strip():
            self.logger.error("Query Generation: Empty response received")
            return []

        try:
            result = QueryResult.model_validate_json(cleaned_response)
            return result.queries if result.queries else []
        except ValidationError as e:
            self.logger.error(
                f"Query Validation Failed: {e}. Response: {cleaned_response[:200]}..."
            )
            return []
        except json.JSONDecodeError as e:
            self.logger.error(
                f"Query JSON Parse Failed: {e}. Response: {cleaned_response[:200]}..."
            )
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error in query parsing: {e}")
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
        cached_content: Optional[caching.CachedContent] = None,
    ) -> Optional[EvaluationResultSchema]:
        """후보 답변을 평가하고 점수를 부여.

        Args:
            ocr_text: 평가 기준이 되는 OCR 텍스트
            query: 평가 대상 질의
            candidates: 후보 답변 딕셔너리 (키: 후보 ID, 값: 답변)
            cached_content: 재사용할 캐시 객체 (선택)

        Returns:
            평가 결과. 질의가 비어있으면 None

        Raises:
            APIRateLimitError: API rate limit 초과 시
            ValidationFailedError: 스키마 검증 또는 JSON 파싱 실패 시
            ValueError: 응답이 비어있을 때
        """
        if not query:
            return None

        input_data = {
            "ocr_ground_truth": ocr_text,
            "target_query": query,
            "candidates": candidates,
        }

        # 시스템 프롬프트 렌더링
        system_prompt = self.jinja_env.get_template("prompt_eval.j2").render()

        # Pydantic 모델 전달
        model = self._create_generative_model(
            system_prompt,
            response_schema=EvaluationResultSchema,
            cached_content=cached_content,
        )

        # 캐시 적중률 모니터링
        if cached_content:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

        try:
            response_text = await self._call_api_with_retry(
                model, json.dumps(input_data, ensure_ascii=False)
            )
        except google_exceptions.ResourceExhausted as e:
            raise APIRateLimitError(
                f"Rate limit exceeded during evaluation: {e}"
            ) from e
        cleaned_response = clean_markdown_code_block(response_text)

        if not cleaned_response or not cleaned_response.strip():
            self.logger.error("Evaluation: Empty response received")
            raise ValueError("Empty evaluation response")

        try:
            # Pydantic을 사용하여 검증 및 파싱 (에러 발생 시 retry 데코레이터가 처리)
            result = EvaluationResultSchema.model_validate_json(cleaned_response)
            return result
        except ValidationError as e:
            self.logger.error(
                f"Evaluation Validation Failed: {e}. Response: {cleaned_response[:200]}..."
            )
            raise ValidationFailedError(f"Evaluation validation failed: {e}") from e
        except json.JSONDecodeError as e:
            self.logger.error(
                f"Evaluation JSON Parse Failed: {e}. Response: {cleaned_response[:200]}..."
            )
            raise ValidationFailedError(f"Evaluation JSON parsing failed: {e}") from e

    async def rewrite_best_answer(
        self,
        ocr_text: str,
        best_answer: str,
        cached_content: Optional[caching.CachedContent] = None,
    ) -> str:
        """선택된 최고 답변을 가독성 및 안전성 측면에서 개선.

        Args:
            ocr_text: 컨텍스트 정보
            best_answer: 재작성할 답변
            cached_content: 재사용할 캐시 객체 (선택)

        Returns:
            재작성된 답변. 파싱 실패 시 원본 텍스트 반환

        Raises:
            APIRateLimitError: API rate limit 초과 시
        """
        # 템플릿 렌더링
        template = self.jinja_env.get_template("rewrite_user.j2")
        payload = template.render(ocr_text=ocr_text, best_answer=best_answer)

        # 시스템 프롬프트 렌더링
        system_prompt = self.jinja_env.get_template("prompt_rewrite.j2").render()

        # rewrite는 순수 텍스트여야 하므로 response_schema=None
        model = self._create_generative_model(
            system_prompt, cached_content=cached_content
        )

        # 캐시 적중률 모니터링
        if cached_content:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

        try:
            response_text = await self._call_api_with_retry(model, payload)
        except google_exceptions.ResourceExhausted as e:
            raise APIRateLimitError(f"Rate limit exceeded during rewrite: {e}") from e

        # utils의 중앙화된 함수 사용 (DRY 원칙)
        unwrapped = safe_json_parse(response_text, "rewritten_answer")

        # Guard: unwrapping 성공 시 반환
        if isinstance(unwrapped, str):
            return unwrapped

        # Fallback: 원본 텍스트 반환
        return response_text if response_text else ""

    def get_total_cost(self) -> float:
        """
        세션의 총 API 비용 계산 (USD)
        모델별 단가를 constants에 정의된 티어로 계산 (입력 토큰 기반)
        """
        model_name = self.config.model_name.lower()
        tiers = PRICING_TIERS.get(model_name)
        if not tiers:
            raise ValueError(f"Unsupported model for pricing: {model_name}")

        input_rate = output_rate = None
        for tier in tiers:
            max_tokens = tier["max_input_tokens"]
            if max_tokens is None or self.total_input_tokens <= max_tokens:
                input_rate = tier["input_rate"]
                output_rate = tier["output_rate"]
                break

        if input_rate is None or output_rate is None:
            raise ValueError(
                f"No pricing tier matched for model '{model_name}' and tokens {self.total_input_tokens}"
            )

        input_cost = (self.total_input_tokens / 1_000_000) * input_rate
        output_cost = (self.total_output_tokens / 1_000_000) * output_rate
        return input_cost + output_cost

    def get_budget_usage_percent(self) -> float:
        """Return budget usage percent; 0 if no budget configured."""
        if not self.config.budget_limit_usd:
            return 0.0
        return (self.get_total_cost() / self.config.budget_limit_usd) * 100

    def check_budget(self) -> None:
        """Raise if total cost exceeds budget."""
        if not self.config.budget_limit_usd:
            return
        total = self.get_total_cost()
        if total > self.config.budget_limit_usd:
            raise BudgetExceededError(
                f"Session cost ${total:.4f} exceeded budget ${self.config.budget_limit_usd:.2f}"
            )
