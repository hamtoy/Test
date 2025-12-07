#!/usr/bin/env python3
"""데모: 웹 API 로깅 기능 확인.

이 스크립트는 웹 API에서 app.log 파일이 생성되는 것을 시연합니다.

Usage:
    # From project root:
    python examples/demo_web_logging.py
    
    # Or with explicit PYTHONPATH:
    PYTHONPATH=. python examples/demo_web_logging.py
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from src.infra.logging import setup_logging


def main() -> None:
    """웹 API 로깅 데모 실행."""
    print("=" * 70)
    print("웹 API 로깅 데모")
    print("=" * 70)
    print()

    # 환경 변수 설정
    os.environ["GEMINI_API_KEY"] = "AIza" + ("A" * 35)

    # 기존 로그 파일 정리
    for log_file in ["app.log", "error.log"]:
        if Path(log_file).exists():
            Path(log_file).unlink()
            print(f"✓ 기존 {log_file} 삭제")

    print()
    print("1. 로깅 시스템 초기화 중...")

    logger, listener = setup_logging(log_level="INFO")

    print("   ✓ 로깅 시스템 초기화 완료")
    print()

    # 다양한 레벨의 로그 메시지 생성
    print("2. 로그 메시지 작성 중...")
    logger.info("웹 API 서버가 시작되었습니다")
    logger.info("서버 주소: http://127.0.0.1:8000")
    logger.warning("Neo4j 연결 실패 (RAG 기능 비활성화)")
    logger.error("테스트 에러 메시지")

    print("   ✓ 다양한 레벨의 로그 작성 완료")
    print()

    # 로그 파일이 생성될 때까지 대기
    time.sleep(0.5)

    print("3. 로그 파일 확인...")
    print()

    for log_file in ["app.log", "error.log"]:
        if Path(log_file).exists():
            print(f"   📄 {log_file} 생성 완료")
            with open(log_file) as f:
                content = f.read()
                lines = content.strip().split("\n")
                print(f"      - 총 {len(lines)}줄")
                print(f"      - 파일 크기: {len(content)} bytes")
                print()
                print("      내용 미리보기:")
                for line in lines[:3]:  # 처음 3줄만 표시
                    print(f"      {line}")
                if len(lines) > 3:
                    print(f"      ... (총 {len(lines)}줄)")
            print()
        else:
            print(f"   ✗ {log_file} 생성되지 않음")

    # 정리
    listener.stop()

    print()
    print("4. 정리 완료")
    print()
    print("=" * 70)
    print("✓ 데모 완료!")
    print("=" * 70)
    print()
    print("📝 참고:")
    print("  - app.log에는 모든 로그 레벨이 기록됩니다")
    print("  - error.log에는 ERROR 레벨 이상만 기록됩니다")
    print("  - 웹 서버 실행 시 (run_web.py) 자동으로 생성됩니다")
    print("  - LOG_LEVEL 환경변수로 로그 레벨 조정 가능")
    print()

    # 로그 파일 정리
    for log_file in ["app.log", "error.log"]:
        if Path(log_file).exists():
            Path(log_file).unlink()

    print("✓ 데모 로그 파일 정리 완료")


if __name__ == "__main__":
    main()
