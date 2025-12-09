"""Debug API response utility."""
# ruff: noqa: E402

import sys
from pathlib import Path
from datetime import datetime

# sys.path 설정 (import 이전에 수행)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 이후 모든 import는 상단에 배치됨
from src.agent.core import GeminiAgent
from src.config import AppConfig


def main() -> None:
    """Debug script to test API responses."""
    config = AppConfig()
    agent = GeminiAgent(config=config)

    # 테스트 코드...
    print(f"Agent initialized: {agent.__class__.__name__}")
    print(f"Timestamp: {datetime.now()}")


if __name__ == "__main__":
    main()
