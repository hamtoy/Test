import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from faststream import FastStream
from faststream.redis import RedisBroker
from pydantic import BaseModel, Field

from src.agent import GeminiAgent
from src.config import AppConfig
from src.config.constants import DEFAULT_CACHE_TTL_SECONDS
from src.core.factory import get_graph_provider, get_llm_provider
from src.core.interfaces import ProviderError, RateLimitError, SafetyBlockedError
from src.features.action_executor import ActionExecutor
from src.features.data2neo_extractor import Data2NeoExtractor
from src.features.lats import LATSSearcher, SearchState, ValidationResult

# Export private functions for backward compatibility with tests
__all__ = [
    "app",
    "broker",
    "get_config",
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

# LATS related constants
_ALLOWED_LATS_ACTION_PREFIXES: set[str] = {
    "clean",
    "summarize",
    "clarify",
    "validate",
    "rerank",
}
_LATS_ALLOWED_FLOW: dict[str, set[str]] = {
    "clean": {"summarize", "clarify", "validate", "rerank", "clean"},
    "summarize": {"clarify", "validate", "rerank", "summarize"},
    "clarify": {"validate", "rerank", "clarify"},
    "validate": {"rerank", "validate"},
    "rerank": {"rerank"},
}
_LATS_BLOCKED_KEYWORDS = ("drop ", "delete ", "remove ")

# Lazy loading for config (environment-driven; ignore call-arg check for BaseSettings)
_config: AppConfig | None = None


def get_config() -> AppConfig:
    """Get the AppConfig instance, creating it lazily if needed."""
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


# Initialize Broker with default URL (redis://localhost:6379)
# Note: RedisBroker default URL matches AppConfig.redis_url default
# The broker connects during app.run() startup, not at instantiation
broker = RedisBroker(url=os.getenv("REDIS_URL", "redis://localhost:6379"))
app = FastStream(broker)
redis_client = None
llm_provider = None
lats_agent: GeminiAgent | None = None
graph_provider = None
data2neo_extractor: Data2NeoExtractor | None = None
_providers_initialized = False


def _init_providers() -> None:
    """Initialize providers lazily on first use."""
    global \
        llm_provider, \
        lats_agent, \
        graph_provider, \
        data2neo_extractor, \
        _providers_initialized
    if _providers_initialized:
        return
    _providers_initialized = True

    config = get_config()

    # LLM provider (optional; requires llm_provider_enabled=True and valid creds)
    if getattr(config, "llm_provider_enabled", False):
        try:
            llm_provider = get_llm_provider(config)
            lats_agent = GeminiAgent(config)
        except Exception as e:  # noqa: BLE001
            logger.warning("LLM provider init failed; continuing without it: %s", e)

    # Graph provider (optional; used for validation when available)
    try:
        graph_provider = get_graph_provider(config)
    except Exception as e:  # noqa: BLE001
        logger.debug("Graph provider init skipped: %s", e)

    # Data2Neo extractor (optional; enabled via ENABLE_DATA2NEO)
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


@app.on_startup
async def setup_redis() -> None:
    """Initialize Redis connection on application startup."""
    global redis_client
    from redis.asyncio import Redis

    config = get_config()
    redis_client = Redis.from_url(config.redis_url)
    _init_providers()


@app.on_shutdown
async def close_redis() -> None:
    """Close Redis connection on application shutdown."""
    if redis_client:
        await redis_client.close()


RESULTS_DIR = Path("data/queue_results")


class OCRTask(BaseModel):
    """Model for OCR processing task messages."""

    request_id: str
    image_path: str
    session_id: str


class DLQMessage(BaseModel):
    """Model for dead letter queue messages."""

    request_id: str
    error_type: str
    payload: dict[str, Any]
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    """Append a record to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


async def check_rate_limit(key: str, limit: int, window: int) -> bool:
    """Checks if the rate limit is exceeded for the given key.

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
    except Exception as exc:
        logger.error("Redis not available: %s", exc)
        raise


async def _process_task(task: OCRTask) -> dict[str, Any]:
    """Minimal OCR/LLM processing stub.

    - Reads text if the path is a .txt file; otherwise uses filename as content.
    - If llm_provider is available, rewrites/cleans text via LLM.
    """
    path = Path(task.image_path)
    if path.suffix.lower() == ".txt" and path.exists():
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            content = f"OCR placeholder for {path.name}"
    else:
        content = f"OCR placeholder for {path.name}"

    llm_text: str | None = None
    if llm_provider:
        config = get_config()
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


async def _run_data2neo_extraction(task: OCRTask) -> dict[str, Any]:
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

        entity_counts: dict[str, int] = {}
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


def _lats_action_prefix(action: str) -> str:
    """Extract the prefix for an action (before ':' if present)."""
    return action.split(":", 1)[0] if ":" in action else action


def _lats_repeat_penalty(
    state: SearchState, prefix: str
) -> tuple[bool, float, str | None]:
    repeats = sum(1 for a in state.focus_history if a.startswith(prefix))
    if repeats >= 3:
        return False, 1.0, "too many repeats"
    if repeats == 2:
        return True, 0.5, None
    return True, 0.0, None


def _lats_flow_penalty(state: SearchState, prefix: str) -> float:
    if not state.focus_history:
        return 0.0
    last_prefix = _lats_action_prefix(state.focus_history[-1])
    allowed_next = _LATS_ALLOWED_FLOW.get(last_prefix)
    if allowed_next is not None and prefix not in allowed_next:
        return 0.5
    return 0.0


def _basic_lats_validation(
    state: SearchState, action: str
) -> tuple[bool, float, str | None]:
    if action.startswith(("invalid", "forbidden")):
        return False, 1.0, "invalid action"
    penalty = 0.2 if action in state.focus_history else 0.0
    prefix = _lats_action_prefix(action)
    ok, rep_penalty, reason = _lats_repeat_penalty(state, prefix)
    if not ok:
        return False, 1.0, reason
    penalty += rep_penalty
    penalty += _lats_flow_penalty(state, prefix)
    return True, penalty, None


def _lats_has_blocked_keyword(action: str) -> bool:
    lower = action.lower()
    return any(bad in lower for bad in _LATS_BLOCKED_KEYWORDS)


def _lats_unrecognized_prefix(action: str) -> bool:
    prefix = _lats_action_prefix(action).lower()
    return bool(prefix) and prefix not in _ALLOWED_LATS_ACTION_PREFIXES


async def _check_lats_graph_constraints(
    action: str, provider: Any
) -> ValidationResult | None:
    if not provider:
        return None
    try:
        session_ctx = provider.session()
        async with session_ctx as session:
            if _lats_has_blocked_keyword(action):
                return ValidationResult(
                    allowed=False,
                    reason="blocked keyword",
                    penalty=1.0,
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
                    allowed=False,
                    reason="graph constraint",
                    penalty=1.0,
                )
            if _lats_unrecognized_prefix(action):
                return ValidationResult(
                    allowed=True,
                    reason="unrecognized action",
                    penalty=0.5,
                )
    except Exception as exc:  # noqa: BLE001
        return ValidationResult(allowed=False, reason=str(exc))
    return None


async def _validate_lats_action(
    state: SearchState,
    action: str,
    provider: Any,
) -> ValidationResult:
    ok, penalty, reason = _basic_lats_validation(state, action)
    if not ok:
        return ValidationResult(allowed=False, reason=reason, penalty=penalty)
    provider_result = await _check_lats_graph_constraints(action, provider)
    if provider_result is not None:
        return provider_result
    return ValidationResult(allowed=True, penalty=penalty)


async def _read_ocr_text_for_lats(image_path: str) -> str:
    try:
        return Path(image_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


async def _propose_from_lats_agent(
    agent: GeminiAgent | None, ocr_text: str
) -> list[str]:
    if not agent or not ocr_text:
        return []
    try:
        queries = await agent.generate_query(ocr_text, None)
        return [q for q in queries if q]
    except Exception as exc:  # noqa: BLE001
        logger.debug("LATS propose via agent failed: %s", exc)
        return []


async def _propose_from_llm(provider: Any) -> list[str]:
    prompt = (
        "Propose 3 next actions (comma separated) for OCR post-processing. "
        "Include at least one clean and one summarize variant."
    )
    try:
        resp = await provider.generate_content_async(prompt=prompt)
        return [a.strip() for a in resp.content.split(",") if a.strip()]
    except Exception as exc:  # noqa: BLE001
        logger.debug("LLM propose failed, fallback to defaults: %s", exc)
        return []


def _default_lats_candidates(request_id: str) -> list[str]:
    return [
        f"clean:{request_id}",
        f"summarize:{request_id}",
        f"clarify:{request_id}",
    ]


def _dedup_actions(actions: list[str]) -> list[str]:
    dedup: list[str] = []
    seen: set[str] = set()
    for act in actions:
        if act and act not in seen:
            dedup.append(act)
            seen.add(act)
    return dedup


def _reorder_actions_for_failure(
    actions: list[str], last_failure: str | None
) -> list[str]:
    if not last_failure:
        return actions
    return [a for a in actions if last_failure not in a] + [
        a for a in actions if last_failure in a
    ]


def _ensure_required_actions(actions: list[str], request_id: str) -> list[str]:
    required = {
        "clean": f"clean:{request_id}",
        "summarize": f"summarize:{request_id}",
        "clarify": f"clarify:{request_id}",
    }
    for prefix, act in required.items():
        if not any(a.startswith(prefix + ":") for a in actions):
            actions.append(act)
    return actions


def _make_lats_proposer(
    task: OCRTask,
    agent: GeminiAgent | None,
    provider: Any,
):
    async def propose(node: Any) -> list[str]:
        candidates: list[str] = []
        if agent:
            ocr_text = await _read_ocr_text_for_lats(task.image_path)
            candidates.extend(await _propose_from_lats_agent(agent, ocr_text))
        if provider and len(candidates) < 2:
            candidates.extend(await _propose_from_llm(provider))
        if not candidates:
            candidates = _default_lats_candidates(task.request_id)
        dedup = _dedup_actions(candidates)
        dedup = _reorder_actions_for_failure(dedup, node.state.last_failure_reason)
        dedup = _ensure_required_actions(dedup, task.request_id)
        return dedup[:3]

    return propose


def _action_type(action: str | None) -> str:
    if not action:
        return ""
    return _lats_action_prefix(action)


def _base_score_for_action(action_type: str) -> float:
    return {
        "clean": 0.9,
        "summarize": 0.8,
        "clarify": 0.85,
        "validate": 0.7,
        "rerank": 0.75,
    }.get(action_type, 0.5)


def _normalize_action_output(
    action_output: Any,
    action_type: str,
    original_text: str,
) -> tuple[float, str, dict[str, Any]]:
    if isinstance(action_output, dict):
        base_score = float(action_output.get("quality_score", 0.5))
        return base_score, original_text, action_output
    text = str(action_output)
    meta = {"type": action_type or "", "text": text}
    return _base_score_for_action(action_type), text, meta


def _quality_penalty(output_text: str) -> float:
    if len(output_text) < 10:
        return 0.3
    if "error" in output_text.lower():
        return 0.5
    return 0.0


def _extract_total_tokens(usage: dict[str, Any], fallback: int) -> int:
    token_total = usage.get("total_tokens")
    if token_total is not None:
        return int(token_total)
    if "prompt_tokens" in usage or "completion_tokens" in usage:
        return int(usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0))
    if "input_tokens" in usage or "output_tokens" in usage:
        return int(usage.get("input_tokens", 0) + usage.get("output_tokens", 0))
    return fallback


def _update_lats_budget(node: Any, tokens: int, executor: Any, tracker: Any) -> None:
    usage = getattr(executor, "last_llm_usage", None)
    if usage:
        usage_dict = dict(usage)
        record = tracker.record_usage(usage_dict)
        token_total = _extract_total_tokens(usage_dict, tokens)
        node.state = node.state.update_budget(tokens=token_total, cost=record.cost_usd)
        return
    node.state = node.state.update_budget(tokens=tokens)


def _make_lats_evaluator(
    task: OCRTask,
    provider: Any,
    eval_cache: Any,
    budget_tracker: Any,
):
    async def evaluate(node: Any) -> float:
        executor = ActionExecutor(llm_provider=provider)
        result = await _process_task(task)
        original_text = result.get("ocr_text", "")
        tokens = len(original_text.split())

        cache_key = f"{node.state.hash_key()}::{node.action}"
        cached_score = await eval_cache.get(cache_key)
        if cached_score is not None:
            node.state = node.state.update_budget(tokens=tokens)
            return float(cached_score + node.reward)

        action_output = await executor.execute_action(
            action=node.action or "clean",
            text=original_text,
            max_length=120,
            use_llm=bool(provider),
        )

        action_type = _action_type(node.action)
        base_score, processed_text, action_meta = _normalize_action_output(
            action_output,
            action_type,
            original_text,
        )
        output_text = (
            processed_text
            if isinstance(action_output, str)
            else str(action_meta.get("text", ""))
        )
        final_score = max(0.0, base_score - _quality_penalty(output_text))

        result["processed_text"] = processed_text
        result["action_output"] = action_meta
        node.result = result

        _update_lats_budget(node, tokens, executor, budget_tracker)
        await eval_cache.set(cache_key, final_score)

        return float(final_score + node.reward)

    return evaluate


async def _run_task_with_lats(task: OCRTask) -> dict[str, Any]:
    """LATS 토글 시 사용되는 경량 트리 탐색 래퍼."""
    from src.caching.redis_cache import RedisEvalCache
    from src.infra.budget import BudgetTracker

    config = get_config()

    eval_cache = RedisEvalCache(
        redis_client=redis_client,
        ttl=DEFAULT_CACHE_TTL_SECONDS,
    )
    budget_tracker = BudgetTracker(
        budget_limit_usd=getattr(config, "budget_limit_usd", 1.0),
    )

    graph_validator = lambda s, a, gp=graph_provider: _validate_lats_action(s, a, gp)
    propose_actions = _make_lats_proposer(task, lats_agent, llm_provider)
    evaluate_action = _make_lats_evaluator(
        task,
        llm_provider,
        eval_cache,
        budget_tracker,
    )

    searcher = LATSSearcher(
        llm_provider=llm_provider,
        graph_validator=graph_validator,
        propose_actions=propose_actions,
        evaluate_action=evaluate_action,
        budget_tracker=budget_tracker,
        max_visits=8,
        max_depth=4,
        exploration_constant=2.0,
        token_budget=getattr(config, "max_output_tokens", 8192),
        cost_budget=0.5,
    )
    best = await searcher.run(SearchState())
    return best.result or {}


@broker.subscriber("ocr_task")  # Low concurrency for pilot
async def handle_ocr_task(task: OCRTask) -> None:
    """Handle incoming OCR tasks from the message queue."""
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
        config = get_config()
        if getattr(config, "enable_data2neo", False):
            result = await _run_data2neo_extraction(task)
        elif getattr(config, "enable_lats", False):
            result = await _run_task_with_lats(task)
        else:
            result = await _process_task(task)
        _append_jsonl(RESULTS_DIR / "results.jsonl", result)
        logger.info(f"Task {task.request_id} completed successfully.")
    except ProviderError:
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
