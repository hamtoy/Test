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
from src.lats_searcher import LATSSearcher, SearchState, ValidationResult

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker")

# Load config (environment-driven; ignore call-arg check for BaseSettings)
config = AppConfig()  # type: ignore[call-arg]

# Initialize Broker and Redis Client
broker = RedisBroker(config.redis_url)
app = FastStream(broker)
redis_client = None


@app.on_startup
async def setup_redis():
    global redis_client
    from redis.asyncio import Redis

    redis_client = Redis.from_url(config.redis_url)


@app.on_shutdown
async def close_redis():
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


def _append_jsonl(path: Path, record: dict) -> None:
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
    return current <= limit


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


async def _process_task(task: OCRTask) -> dict:
    """
    Minimal OCR/LLM processing stub.
    - Reads text if the path is a .txt file; otherwise uses filename as content.
    - If llm_provider is available, rewrites/cleans text via LLM.
    """
    path = Path(task.image_path)
    if path.suffix.lower() == ".txt" and path.exists():
        content = path.read_text(encoding="utf-8", errors="ignore")
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


async def _run_task_with_lats(task: OCRTask) -> dict:
    """LATS 토글 시 사용되는 경량 트리 탐색 래퍼."""

    async def graph_validator(state: SearchState, action: str) -> ValidationResult:
        # 간단한 제약: 동일 액션 반복 시 페널티, 금지 접두어 거부
        if action.startswith(("invalid", "forbidden")):
            return ValidationResult(allowed=False, reason="invalid action")
        penalty = 0.2 if action in state.focus_history else 0.0
        if graph_provider:
            try:
                session_ctx = graph_provider.session()
                async with session_ctx as session:  # type: ignore[union-attr]
                    # 금지 패턴 + 간단한 제약 검증 (실제 규칙으로 확장 가능)
                    blocked = any(
                        bad in action.lower() for bad in ["drop ", "delete ", "remove "]
                    )
                    if blocked:
                        return ValidationResult(
                            allowed=False, reason="blocked keyword", penalty=1.0
                        )
                    # Neo4j 제약 예시: 에러 패턴/쿼리 타입 검증
                    result = await session.run(
                        "RETURN coalesce($action CONTAINS 'error', false) AS bad",
                        action=action,
                    )
                    data = await result.single()
                    if data and data.get("bad"):
                        return ValidationResult(
                            allowed=False, reason="graph constraint", penalty=1.0
                        )
            except Exception as exc:  # noqa: BLE001
                return ValidationResult(allowed=False, reason=str(exc))
        return ValidationResult(allowed=True, penalty=penalty)

    async def propose(_node):
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
            candidates = [f"clean:{task.request_id}", f"summarize:{task.request_id}"]
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
        return dedup[:3]

    async def evaluate(node):
        result = await _process_task(task)
        tokens = len(result.get("ocr_text", "").split())
        node.state = node.state.update_budget(tokens=tokens)
        node.result = result
        # 간단한 점수: clean 우선, LLM 평가 시 점수 교체
        base_score = 0.9 if node.action and node.action.startswith("clean") else 0.6
        # 후보 응답 준비: 원본/정제/요약
        original_text = result.get("ocr_text", "")
        cleaned_text = " ".join(original_text.split())
        summary_text = cleaned_text
        if len(summary_text) > 120:
            summary_text = summary_text[:120] + "..."

        if lats_agent and node.action:
            try:
                eval_result = await lats_agent.evaluate_responses(
                    ocr_text=original_text,
                    query=node.action,
                    candidates={
                        "A": original_text,
                        "B": cleaned_text or original_text,
                        "C": summary_text or node.action,
                    },
                    cached_content=None,
                )
                if eval_result:
                    scored = [item.score for item in eval_result.evaluations]
                    if scored:
                        base_score = max(base_score, max(scored) / 10)
            except Exception as exc:  # noqa: BLE001
                logger.debug("LATS evaluate via agent failed: %s", exc)
        elif llm_provider:
            try:
                rating = await llm_provider.generate_content_async(
                    prompt=(
                        "Rate from 0-1 the quality of processed OCR text: "
                        f"{result.get('ocr_text','')[:200]}"
                    ),
                    max_output_tokens=4,
                    temperature=0,
                )
                score = float(rating.content.strip())
                base_score = max(base_score, score)
                if rating.usage:
                    node.state = node.state.update_budget(
                        tokens=rating.usage.get("total_tokens", 0)
                    )
            except Exception as exc:  # noqa: BLE001
                logger.debug("LLM evaluate failed, fallback score: %s", exc)
        return base_score + node.reward

    searcher = LATSSearcher(
        llm_provider=llm_provider,
        graph_validator=graph_validator,
        propose_actions=propose,
        evaluate_action=evaluate,
        max_visits=3,
        max_depth=2,
        token_budget=getattr(config, "max_output_tokens", 8192),
    )
    best = await searcher.run(SearchState())
    return best.result or {}


@broker.subscriber("ocr_task")  # Low concurrency for pilot
async def handle_ocr_task(task: OCRTask):
    await ensure_redis_ready()
    logger.info(f"Received task: {task.request_id}")

    allowed = await check_rate_limit("global_rate_limit", 10, 60)
    if not allowed:
        logger.warning(f"Rate limit exceeded for task {task.request_id}. Re-queuing...")
        raise RateLimitError("Global rate limit exceeded")

    try:
        if getattr(config, "enable_lats", False):
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
