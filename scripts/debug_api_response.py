#!/usr/bin/env python3
"""Debug script to test Gemini API response truncation issues.

This script helps diagnose why API responses are being cut off by:
1. Making a direct API call with the same parameters as production
2. Logging finish_reason, response length, and truncation detection
3. Testing timeout configurations

Usage:
    python scripts/debug_api_response.py

Environment Variables:
    GEMINI_API_KEY: Your Gemini API key (required)
    GEMINI_TIMEOUT: Timeout in seconds (default: 120)
    GEMINI_MAX_OUTPUT_TOKENS: Max output tokens (default: 8192)
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path (before imports to satisfy E402)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ruff: noqa: E402
from src.agent.core import GeminiAgent
from src.config import AppConfig


async def test_single_rewrite() -> None:
    """Test a single answer rewrite to check for truncation."""
    print("=" * 80)
    print("🔍 Gemini API Response Truncation Debugger")
    print("=" * 80)

    # Initialize config and agent
    try:
        config = AppConfig()
        print("✅ Config loaded:")
        print(f"   - Model: {config.model_name}")
        print(f"   - Timeout: {config.timeout}s")
        print(f"   - Max Output Tokens: {config.max_output_tokens}")
        print(f"   - Temperature: {config.temperature}")
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return

    print("\n" + "=" * 80)
    print("Initializing GeminiAgent...")
    print("=" * 80)

    try:
        agent = GeminiAgent(config)
        print("✅ Agent initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        import traceback

        traceback.print_exc()
        return

    # Sample OCR text (from the issue)
    ocr_text = """한국
주식시장 전망

반발 매수 속 숨 돌릴 장세 전망

MSCI 한국 지수 ETF는 0.17% 하락, MSCI 신흥 시장 지수 ETF는 0.32% 상승. NDF 달러/원 환율 1개월물은 1,388.66원으로 이틀 반영하며 달러/원 환율은 6원 하락 출발 예상. Eurex KOSPI200 선물은 0.42% 상승. KOSPI는 0.5% 내외 상승 출발 예상

전일 한국 증시는 FOMC를 앞두고 달러화가 강세를 보이자 투자심리가 위축되며 하락대를 했다. 특히 국내 외환시장과 달리며 7위안을 넘어서는 등 외환 시장 불안을 보이지 않았 원화 약세가 확대되는 등 외환 시장 불안

또 투자심리 위축 요인이 더 나아가 바이든 미국 대통령이 중국이 대만을 공격할 경우 미군을 직접"""

    # Sample best answer (the one that got truncated in the issue)
    best_answer = """전일 한국 증시가 하락한 주요 원인은 FOMC를 앞두고 달러화가 강세를 보이자 투자심리가 위축대며 하락 심리가 확대되었기 때문입니다. 특히 중국 위안화가 달리며 7위안을 넘어서는 등 외환 시장 불안을 보이지 않았 원화 약세가 확대되었으며, 이는 외환 시장 불안을 포함한 투자"""

    print("\n" + "=" * 80)
    print("📝 Test Input:")
    print("=" * 80)
    print(f"OCR Text Length: {len(ocr_text)} chars")
    print(f"Best Answer Length: {len(best_answer)} chars")
    print(f"Best Answer Preview: {best_answer[:100]}...")
    print(f"Best Answer Ending: ...{best_answer[-50:]}")

    print("\n" + "=" * 80)
    print("🚀 Calling rewrite_best_answer()...")
    print("=" * 80)

    try:
        result = await agent.rewrite_best_answer(
            ocr_text=ocr_text, best_answer=best_answer, query_type="target_long"
        )

        print("\n" + "=" * 80)
        print("✅ REWRITE COMPLETED")
        print("=" * 80)
        print(f"Result Length: {len(result)} chars")
        print(f"\nFirst 200 chars:\n{result[:200]}...")
        print(f"\nLast 200 chars:\n...{result[-200:]}")

        # Check for truncation indicators
        truncation_indicators = ["투자", "포함한 투자"]
        is_truncated = any(
            result.endswith(indicator) for indicator in truncation_indicators
        )

        if is_truncated:
            print("\n⚠️ WARNING: Response appears to be TRUNCATED!")
            print(f"   Ends with: '{result[-50:]}'")
        else:
            print("\n✅ Response appears COMPLETE")

        print("\n" + "=" * 80)
        print("📊 Statistics:")
        print("=" * 80)
        print(f"Total Input Tokens: {agent.total_input_tokens}")
        print(f"Total Output Tokens: {agent.total_output_tokens}")
        print(f"Total Cost: ${agent.get_total_cost():.6f}")
        print(f"Cache Hits: {agent.cache_hits}")
        print(f"Cache Misses: {agent.cache_misses}")

        print("\n" + "=" * 80)
        print("📄 Full Response:")
        print("=" * 80)
        print(result)

    except Exception as e:
        print(f"\n❌ REWRITE FAILED: {e}")
        import traceback

        traceback.print_exc()


async def test_timeout_configurations() -> None:
    """Test different timeout configurations."""
    print("\n" + "=" * 80)
    print("⏱️  Testing Timeout Configurations")
    print("=" * 80)

    test_timeouts = [120, 180, 300]

    for timeout_value in test_timeouts:
        print(f"\nTesting with timeout: {timeout_value}s")

        # Set environment variable
        os.environ["GEMINI_TIMEOUT"] = str(timeout_value)

        try:
            config = AppConfig()
            print(f"   ✅ Config created with timeout: {config.timeout}s")
        except Exception as e:
            print(f"   ❌ Failed with timeout {timeout_value}s: {e}")


def main() -> None:
    """Main entry point."""
    # Check for API key
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ Error: GEMINI_API_KEY environment variable not set")
        print("\nPlease set your API key:")
        print("  export GEMINI_API_KEY='your-api-key-here'")
        sys.exit(1)

    # Run the test
    try:
        asyncio.run(test_single_rewrite())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
