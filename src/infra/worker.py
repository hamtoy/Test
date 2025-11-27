import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from faststream import FastStream
from faststream.redis import RedisBroker
from pydantic import BaseModel, Field

from src.config import AppConfig
from src.agent import GeminiAgent
from src.core.factory import get_graph_provider, get_llm_provider
from src.core.interfaces import ProviderError, RateLimitError, SafetyBlockedError
from src.features.lats import LATSSearcher, SearchState, ValidationResult
from src.features.action_executor import ActionExecutor
from src.features.data2neo_extractor import Data2NeoExtractor

# Export private functions for backward compatibility with tests
__all__ = [
    "app",
    "broker",
    "config",
    "redis_client",
    "llm_provider",
    "lats_agent",
    "graph_provider",
    "data2neo_extractor",
    "setup_redis",
    "close_redis",
    "check_rate_limit",
    "ensure_redis_ready",
    "OCRTask",
    "DLQMessage",
    "handle_ocr_task",
    "_append_jsonl",
    "_process_task",
    "_run_task_with_lats",
    "_run_data2neo_extraction",
    # Re-export imported classes for test compatibility
    "RateLimitError",
    "SafetyBlockedError",
    "ProviderError",
    "SearchState",
    "ValidationResult",
    "LATSSearcher",
    "ActionExecutor",
    "GeminiAgent",
    "Data2NeoExtractor",
]

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker")

# Rough cost estimation (USD per token) for budgeting/cost guardrails
MODEL_COST_PER_TOKEN = 1e-6

# Load config (environment-driven; ignore call-arg check for BaseSettings)
config = AppConfig()

# Initialize Broker and Redis Client
broker = RedisBroker(config.redis_url)
app = FastStream(broker)
redis_client = None


@app.on_startup
async def setup_redis() -> None:
    global redis_client
    from redis.asyncio import Redis

    redis_client = Redis.from_url(config.redis_url)


@app.on_shutdown
async def close_redis() -> None:
    if redis_client:
        await redis_client.close()


# LLM provider (optional; requires llm_provider_enabled=True and valid creds)
llm_provider = None
lats_agent: Optional[GeminiAgent] = None
if getattr(config, "llm_provider_enabled", False):
    try:
        llm_provider = get_llm_provider(config)
        lats_agent = GeminiAgent(config)
    except Exception as e:  # noqa: BLE001
        logger.warning("LLM provider init failed; continuing without it: %s", e)

# Graph provider (optional; used for validation when available)
graph_provider = None
try:
    graph_provider = get_graph_provider(config)
except Exception as e:  # noqa: BLE001
    logger.debug("Graph provider init skipped: %s", e)

# Data2Neo extractor (optional; enabled via ENABLE_DATA2NEO)
data2neo_extractor: Optional[Data2NeoExtractor] = None
if getattr(config, "enable_data2neo", False):
    try:
        data2neo_extractor = Data2NeoExtractor(
            config=config,
            llm_provider=llm_provider,
            graph_provider=graph_provider,
        )
        logger.info(
            "Data2Neo extractor initialized (batch_size=%d, confidence=%.2f)",
            data2neo_extractor.batch_size,
            data2neo_extractor.confidence_threshold,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Data2Neo extractor init failed: %s", e)

RESULTS_DIR = Path("data/queue_results")


class OCRTask(BaseModel):
    request_id: str
    image_path: str
    session_id: str


class DLQMessage(BaseModel):
    request_id: str
    error_type: str
    payload: Dict[str, Any]
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def _append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


async def check_rate_limit(key: str, limit: int, window: int) -> bool:
    """
    Checks if the rate limit is exceeded for the given key.
    Returns True if allowed, False if blocked.
    """
    if not redis_client:
        return True  # Fail open if redis not ready (or raise)

    current = await redis_client.incr(key)
    if current == 1:
        await redis_client.expire(key, window)
    return bool(current <= limit)


async def ensure_redis_ready() -> None:
    """Ping Redis once; raise if unavailable."""
    try:
        if not redis_client:
            raise RuntimeError("Redis client not initialized")
        pong = await redis_client.ping()
        if pong is not True:
            raise RuntimeError("Redis ping failed")
    except Exception as exc:  # noqa: BLE001
        logger.error("Redis not available: %s", exc)
        raise


async def _process_task(task: OCRTask) -> Dict[str, Any]:
    """
    Minimal OCR/LLM processing stub.
    - Reads text if the path is a .txt file; otherwise uses filename as content.
    - If llm_provider is available, rewrites/cleans text via LLM.
    """
    path = Path(task.image_path)
    if path.suffix.lower() == ".txt" and path.exists():
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:  # noqa: PERF203
            logger.warning("Failed to read %s: %s", path, exc)
            content = f"OCR placeholder for {path.name}"
    else:
        content = f"OCR placeholder for {path.name}"

    llm_text: Optional[str] = None
    if llm_provider:
        result = await llm_provider.generate_content_async(
            prompt=f"Clean up the OCR text:\n{content}",
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
            request_options={"timeout": config.timeout},
        )
        llm_text = result.content

    return {
        "request_id": task.request_id,
        "session_id": task.session_id,
        "image_path": task.image_path,
        "ocr_text": content,
        "llm_output": llm_text,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }


async def _run_data2neo_extraction(task: OCRTask) -> Dict[str, Any]:
    """Extract entities from OCR text and import to Neo4j.

    This function implements the Data2Neo pipeline:
    1. Read OCR text from file or use placeholder
    2. Extract entities (Person, Organization, DocumentRule) using LLM
    3. Import entities and relationships to Neo4j graph
    4. Return result with extraction statistics

    Args:
        task: OCR task containing image/text path and metadata

    Returns:
        Dict with extraction results and statistics
    """
    if not data2neo_extractor:
        logger.warning("Data2Neo extractor not available, falling back to basic task")
        return await _process_task(task)

    path = Path(task.image_path)

    # Read OCR text
    if path.suffix.lower() == ".txt" and path.exists():
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            content = f"OCR placeholder for {path.name}"
    else:
        content = f"OCR placeholder for {path.name}"

    # Skip extraction for placeholder content
    if content.startswith("OCR placeholder"):
        logger.info("Skipping Data2Neo extraction for placeholder content")
        return await _process_task(task)

    try:
        # Extract and import entities
        result = await data2neo_extractor.extract_and_import(
            ocr_text=content,
            document_path=task.image_path,
        )

        entity_counts: Dict[str, int] = {}
        for entity in result.entities:
            entity_type = entity.type.value
            entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1

        return {
            "request_id": task.request_id,
            "session_id": task.session_id,
            "image_path": task.image_path,
            "ocr_text": content,
            "data2neo": {
                "document_id": result.document_id,
                "entity_count": len(result.entities),
                "relationship_count": len(result.relationships),
                "chunk_count": result.chunk_count,
                "entity_types": entity_counts,
            },
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Data2Neo extraction failed: %s", exc)
        # Fall back to basic processing
        return await _process_task(task)


async def _run_task_with_lats(task: OCRTask) -> Dict[str, Any]:
    """LATS 토글 시 사용되는 경량 트리 탐색 래퍼."""
    from src.infra.budget import BudgetTracker
    from src.caching.redis_cache import RedisEvalCache

    # Initialize Redis-backed cache with fallback
    eval_cache = RedisEvalCache(redis_client=redis_client, ttl=3600)
    budget_tracker = BudgetTracker(
        budget_limit_usd=getattr(config, "budget_limit_usd", 1.0)
    )

    async def graph_validator(state: SearchState, action: str) -> ValidationResult:
        # 간단한 제약: 동일 액션 반복 시 페널티, 금지 접두어 거부
        if action.startswith(("invalid", "forbidden")):
            return ValidationResult(allowed=False, reason="invalid action")
        penalty = 0.2 if action in state.focus_history else 0.0
        # 반복된 액션 타입(접두어 기준) 누적 시 페널티/차단
        action_prefix = action.split(":", 1)[0] if ":" in action else action
        repeats = sum(1 for a in state.focus_history if a.startswith(action_prefix))
        if repeats >= 3:
            return ValidationResult(
                allowed=False, reason="too many repeats", penalty=1.0
            )
        if repeats == 2:
            penalty += 0.5
        # 간단한 순서 규칙: clean → summarize/clarify → validate/rerank
        if state.focus_history:
            last_prefix = state.focus_history[-1].split(":", 1)[0]
            allowed_flow = {
                "clean": {"summarize", "clarify", "validate", "rerank", "clean"},
                "summarize": {"clarify", "validate", "rerank", "summarize"},
                "clarify": {"validate", "rerank", "clarify"},
                "validate": {"rerank", "validate"},
                "rerank": {"rerank"},
            }
            if (
                last_prefix in allowed_flow
                and action_prefix not in allowed_flow[last_prefix]
            ):
                penalty += 0.5
        if graph_provider:
            try:
                session_ctx = graph_provider.session()
                async with session_ctx as session:
                    # 금지 패턴 + 간단한 제약 검증 (실제 규칙으로 확장 가능)
                    blocked = any(
                        bad in action.lower() for bad in ["drop ", "delete ", "remove "]
                    )
                    if blocked:
                        return ValidationResult(
                            allowed=False, reason="blocked keyword", penalty=1.0
                        )
                    result = await session.run(
                        """
                        WITH $action AS act
                        RETURN
                          act CONTAINS 'error' AS bad_pattern,
                          act STARTS WITH 'forbidden:' AS bad_prefix
                        """,
                        action=action,
                    )
                    data = await result.single()
                    if data and (data.get("bad_pattern") or data.get("bad_prefix")):
                        return ValidationResult(
                            allowed=False, reason="graph constraint", penalty=1.0
                        )
                    allowed_types = {
                        "clean",
                        "summarize",
                        "clarify",
                        "validate",
                        "rerank",
                    }
                    prefix = action.split(":", 1)[0].lower()
                    if prefix and prefix not in allowed_types:
                        return ValidationResult(
                            allowed=True, reason="unrecognized action", penalty=0.5
                        )
            except Exception as exc:  # noqa: BLE001
                return ValidationResult(allowed=False, reason=str(exc))
        return ValidationResult(allowed=True, penalty=penalty)

    async def propose(_node: Any) -> list[str]:
        # 복수 브랜치 제안: LLM 제안 우선, 실패 시 기본값
        candidates: list[str] = []
        if lats_agent:
            try:
                ocr_text = Path(task.image_path).read_text(
                    encoding="utf-8", errors="ignore"
                )
            except OSError:
                ocr_text = ""
            if ocr_text:
                try:
                    queries = await lats_agent.generate_query(ocr_text, None)
                    candidates.extend([q for q in queries if q])
                except Exception as exc:  # noqa: BLE001
                    logger.debug("LATS propose via agent failed: %s", exc)
        if llm_provider and len(candidates) < 2:
            try:
                prompt = (
                    "Propose 3 next actions (comma separated) for OCR post-processing. "
                    "Include at least one clean and one summarize variant."
                )
                resp = await llm_provider.generate_content_async(prompt=prompt)
                actions = [a.strip() for a in resp.content.split(",") if a.strip()]
                candidates.extend(actions)
            except Exception as exc:  # noqa: BLE001
                logger.debug("LLM propose failed, fallback to defaults: %s", exc)
        if not candidates:
            candidates = [
                f"clean:{task.request_id}",
                f"summarize:{task.request_id}",
                f"clarify:{task.request_id}",
            ]
        # 상태 기반: 동일 액션 중복 제거, 최근 실패(있다면)와 다른 액션 우선
        dedup = []
        seen = set()
        for act in candidates:
            if act and act not in seen:
                dedup.append(act)
                seen.add(act)
        if state_last := _node.state.last_failure_reason:
            dedup = [a for a in dedup if state_last not in a] + [
                a for a in dedup if state_last in a
            ]
        # 필수 액션 유형 보장
        if not any(a.startswith("clean:") for a in dedup):
            dedup.append(f"clean:{task.request_id}")
        if not any(a.startswith("summarize:") for a in dedup):
            dedup.append(f"summarize:{task.request_id}")
        if not any(a.startswith("clarify:") for a in dedup):
            dedup.append(f"clarify:{task.request_id}")
        return dedup[:3]

    async def evaluate(node: Any) -> float:
        # ActionExecutor 인스턴스 생성 (LLM provider 주입)
        executor = ActionExecutor(llm_provider=llm_provider)

        # 원본 OCR 텍스트 로드
        result = await _process_task(task)
        original_text = result.get("ocr_text", "")
        tokens = len(original_text.split())

        # 캐시 체크
        cache_key = f"{node.state.hash_key()}::{node.action}"
        cached_score = await eval_cache.get(cache_key)
        if cached_score is not None:
            # Use cached score directly
            node.state = node.state.update_budget(tokens=tokens)
            return float(cached_score + node.reward)

        # 액션 실행: 실제 출력물 생성
        action_output = await executor.execute_action(
            action=node.action or "clean",
            text=original_text,
            max_length=120,
            use_llm=bool(llm_provider),
        )

        # 액션 결과를 result에 저장
        if isinstance(action_output, dict):
            # validate 액션의 경우 dict 반환
            result["action_output"] = action_output
            result["processed_text"] = original_text  # 원본 유지
            # 품질 점수를 base_score로 사용
            base_score = action_output.get("quality_score", 0.5)
        else:
            # 다른 액션들은 문자열 반환
            result["processed_text"] = action_output
            result["action_output"] = {"type": node.action, "text": action_output}
            # 액션 타입별 기본 점수
            action_type = (node.action or "").split(":", 1)[0]
            base_score = {
                "clean": 0.9,
                "summarize": 0.8,
                "clarify": 0.85,
                "validate": 0.7,
                "rerank": 0.75,
            }.get(action_type, 0.5)

        # 품질 평가 (간소화: 텍스트 길이 기반)
        output_text = (
            action_output
            if isinstance(action_output, str)
            else action_output.get("text", "")
        )
        quality_penalty = 0.0
        if len(output_text) < 10:
            quality_penalty = 0.3
        elif "error" in output_text.lower():
            quality_penalty = 0.5

        final_score = max(0.0, base_score - quality_penalty)

        # BudgetTracker 업데이트 (실제 LLM usage 기록)
        if hasattr(executor, "last_llm_usage") and executor.last_llm_usage:
            usage = dict(executor.last_llm_usage)
            record = budget_tracker.record_usage(usage)
            token_total = usage.get("total_tokens")
            if token_total is None:
                if "prompt_tokens" in usage or "completion_tokens" in usage:
                    token_total = usage.get("prompt_tokens", 0) + usage.get(
                        "completion_tokens", 0
                    )
                elif "input_tokens" in usage or "output_tokens" in usage:
                    token_total = usage.get("input_tokens", 0) + usage.get(
                        "output_tokens", 0
                    )
                else:
                    token_total = tokens

            node.state = node.state.update_budget(
                tokens=token_total or tokens, cost=record.cost_usd
            )
        else:
            # Fallback: 추정치 사용
            node.state = node.state.update_budget(tokens=tokens)

        # 노드 결과 저장
        node.result = result

        # 캐시에 저장
        await eval_cache.set(cache_key, final_score)

        return float(final_score + node.reward)

    searcher = LATSSearcher(
        llm_provider=llm_provider,
        graph_validator=graph_validator,
        propose_actions=propose,
        evaluate_action=evaluate,
        budget_tracker=budget_tracker,
        max_visits=8,  # Increased from 5 for more exploration
        max_depth=4,  # Increased from 3 for deeper paths
        exploration_constant=2.0,  # Increased from 1.41 for more exploration
        token_budget=getattr(config, "max_output_tokens", 8192),
        cost_budget=0.5,
    )
    best = await searcher.run(SearchState())
    return best.result or {}


@broker.subscriber("ocr_task")  # Low concurrency for pilot
async def handle_ocr_task(task: OCRTask) -> None:
    try:
        await ensure_redis_ready()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis not ready, continuing with in-memory cache: %s", exc)
        # fail open: allow downstream to use in-memory cache paths
        global redis_client
        redis_client = None
    logger.info(f"Received task: {task.request_id}")

    allowed = await check_rate_limit("global_rate_limit", 10, 60)
    if not allowed:
        logger.warning(f"Rate limit exceeded for task {task.request_id}. Re-queuing...")
        raise RateLimitError("Global rate limit exceeded")

    try:
        # Feature flag priority: Data2Neo > LATS > Basic processing
        # Note: These features are mutually exclusive; only one runs per task
        if getattr(config, "enable_data2neo", False):
            result = await _run_data2neo_extraction(task)
        elif getattr(config, "enable_lats", False):
            result = await _run_task_with_lats(task)
        else:
            result = await _process_task(task)
        _append_jsonl(RESULTS_DIR / "results.jsonl", result)
        logger.info(f"Task {task.request_id} completed successfully.")
    except (RateLimitError, SafetyBlockedError, ProviderError):
        # Transient or provider-related errors should be retried by FastStream
        raise
    except Exception as e:
        logger.error(f"Task {task.request_id} failed: {e}")
        dlq_msg = DLQMessage(
            request_id=task.request_id,
            error_type=type(e).__name__,
            payload=task.model_dump(),
        )
        await broker.publish(dlq_msg, "ocr_dlq")
        logger.error(f"Sent task {task.request_id} to DLQ")


if __name__ == "__main__":
    import asyncio

    asyncio.run(app.run())
