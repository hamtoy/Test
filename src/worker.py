import asyncio
import logging
from datetime import datetime
from typing import Any, Dict

from faststream import FastStream
from faststream.redis import RedisBroker
from pydantic import BaseModel, Field

from src.config import AppConfig
from src.core.interfaces import RateLimitError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker")

# Load config (environment-driven; ignore call-arg check for BaseSettings)
config = AppConfig()  # type: ignore[call-arg]

# Initialize Broker
broker = RedisBroker(config.redis_url)
app = FastStream(broker)


class OCRTask(BaseModel):
    request_id: str
    image_path: str
    session_id: str


class DLQMessage(BaseModel):
    request_id: str
    error_type: str
    payload: Dict[str, Any]
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# Rate Limiter (Simple Token Bucket using Redis)
async def check_rate_limit(key: str, limit: int, window: int) -> bool:
    """
    Checks if the rate limit is exceeded for the given key.
    Returns True if allowed, False if blocked.
    """
    # Note: In a real production scenario, use a Lua script for atomicity.
    # This is a simplified pilot implementation.
    current = await broker.redis.incr(key)
    if current == 1:
        await broker.redis.expire(key, window)

    return current <= limit


@broker.subscriber("ocr_task", concurrency=1)  # Low concurrency for pilot
async def handle_ocr_task(task: OCRTask):
    logger.info(f"Received task: {task.request_id}")

    # 1. Global Rate Limiting (Shared across workers)
    # Limit: 10 requests per 60 seconds (conservative pilot limit)
    allowed = await check_rate_limit("global_rate_limit", 10, 60)
    if not allowed:
        logger.warning(f"Rate limit exceeded for task {task.request_id}. Re-queuing...")
        # Nack to retry later (FastStream handles backoff if configured,
        # or we can manually publish to a retry queue)
        # For pilot, we'll just raise an error to trigger FastStream's retry mechanism
        raise RateLimitError("Global rate limit exceeded")

    try:
        # 2. Process Task
        # provider = get_llm_provider(config) # Unused in pilot simulation

        # Simulate OCR processing (replace with actual logic)
        # In a real scenario, we would read the image and call provider.generate_content_async
        logger.info(f"Processing image: {task.image_path}")

        # Example call (commented out until we have actual image loading)
        # result = await provider.generate_content_async(
        #     prompt="Extract text from this image...",
        #     # ...
        # )

        # Simulate success
        await asyncio.sleep(1)
        logger.info(f"Task {task.request_id} completed successfully.")

    except Exception as e:
        logger.error(f"Task {task.request_id} failed: {e}")

        # 3. DLQ Logic for Permanent Failures
        # If it's not a transient error (like RateLimit), send to DLQ
        if not isinstance(e, RateLimitError):
            dlq_msg = DLQMessage(
                request_id=task.request_id,
                error_type=type(e).__name__,
                payload=task.model_dump(),
            )
            await broker.publish(dlq_msg, "ocr_dlq")
            logger.error(f"Sent task {task.request_id} to DLQ")
            return  # Ack the original message so it's removed from the main queue

        # If it IS a transient error, re-raise to let FastStream retry
        raise e
