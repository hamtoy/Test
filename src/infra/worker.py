"""FastStream Redis Worker module.

Background task processor for OCR/LLM workloads using FastStream and Redis.
Supports LATS-based tree search, Data2Neo entity extraction, rate limiting,
and dead-letter queue handling.
"""

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
from src.core.factory import get_graph_provider, get_llm_provider
from src.core.interfaces import ProviderError, RateLimitError, SafetyBlockedError
from src.features.action_executor import ActionExecutor
from src.features.data2neo_extractor import Data2NeoExtractor
from src.features.lats import LATSSearcher, SearchState, ValidationResult

# LATS logic delegated to separate module for maintainability
from src.infra.lats_worker import run_lats_search

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

# Note: LATS constants moved to src.infra.lats_worker

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

    # Initialize OpenTelemetry if OTLP endpoint is configured
    from src.infra.telemetry import init_telemetry

    init_telemetry(service_name="gemini-qa-worker")

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


async def _run_task_with_lats(task: OCRTask) -> dict[str, Any]:
    """LATS 토글 시 사용되는 경량 트리 탐색 래퍼.

    Note: LATS 로직은 src.infra.lats_worker 모듈로 분리되었습니다.
    """
    config = get_config()
    return await run_lats_search(
        task=task,
        config=config,
        redis_client=redis_client,
        lats_agent=lats_agent,
        llm_provider=llm_provider,
        graph_provider=graph_provider,
        process_task_fn=_process_task,
    )


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
