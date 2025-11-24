import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from faststream.redis import RedisBroker
from src.config import AppConfig
from src.worker import OCRTask


async def main():
    config = AppConfig()
    broker = RedisBroker(config.redis_url)

    # Connect to Redis
    try:
        await broker.connect()
        print(f"Connected to Redis at {config.redis_url}")
    except Exception as e:
        print(f"Failed to connect to Redis: {e}")
        print("Please ensure Redis is running.")
        return

    # Create a dummy task
    task = OCRTask(
        request_id=f"req-{int(asyncio.get_event_loop().time())}",
        image_path="sample_image.txt",  # Using txt for pilot as per worker logic
        session_id="sess-001",
    )

    # Create a dummy file if it doesn't exist
    Path("sample_image.txt").write_text("This is a test OCR content.", encoding="utf-8")

    # Publish
    await broker.publish(task, "ocr_task")
    print(f"Published task: {task}")

    await broker.close()


if __name__ == "__main__":
    asyncio.run(main())
