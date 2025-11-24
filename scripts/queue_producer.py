from __future__ import annotations

import argparse
import asyncio
import os
import uuid
from typing import Any, Dict

from faststream.redis import RedisBroker


async def publish_task(image_path: str, session_id: str, redis_url: str) -> None:
    broker = RedisBroker(redis_url)
    await broker.connect()
    payload: Dict[str, Any] = {
        "request_id": str(uuid.uuid4()),
        "image_path": image_path,
        "session_id": session_id,
    }
    await broker.publish(payload, "ocr_task")
    await broker.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish an OCR task to Redis.")
    parser.add_argument(
        "--image-path", required=True, help="이미지 또는 텍스트 파일 경로"
    )
    parser.add_argument("--session-id", default="local-session", help="세션 식별자")
    parser.add_argument(
        "--redis-url",
        default=os.getenv("REDIS_URL", "redis://localhost:6379"),
        help="Redis URL (default: redis://localhost:6379)",
    )
    args = parser.parse_args()

    asyncio.run(publish_task(args.image_path, args.session_id, args.redis_url))
    print(f"Published task for {args.image_path} to Redis {args.redis_url}")


if __name__ == "__main__":
    main()
"""
Simple Redis producer for the FastStream OCR worker.

Usage:
  python scripts/queue_producer.py --image-path path/to/file.png --session-id demo

Notes:
- Redis 인스턴스가 `REDIS_URL` 환경변수(기본값 redis://localhost:6379)에서 접근 가능해야 합니다.
- FastStream RedisBroker와 동일한 채널 이름(ocr_task)에 JSON 메시지를 XADD 방식으로 게시합니다.
"""
