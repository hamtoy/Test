"""
비용 예측 도구

실행 전 대략적인 API 비용을 추정합니다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def count_tokens_simple(text: str) -> int:
    """간단한 토큰 수 추정 (정확도 약 80%)

    한글: 1자당 약 1.5토큰
    영어/숫자: 1문자당 약 0.25토큰
    """
    korean_chars = sum(1 for c in text if "\uac00" <= c <= "\ud7a3")
    other_chars = len(text) - korean_chars

    return int(korean_chars * 1.5 + other_chars * 0.25)


def estimate_cost(
    ocr_file: str,
    num_queries: int = 4,
    candidates: int = 3,
) -> None:
    """워크플로우 비용 예측"""

    # OCR 텍스트 로드
    ocr_path = Path(ocr_file)
    if not ocr_path.exists():
        print(f"Error: File not found: {ocr_file}")
        sys.exit(1)

    ocr_text = ocr_path.read_text(encoding="utf-8")
    ocr_tokens = count_tokens_simple(ocr_text)

    print("=" * 60)
    print("💰 비용 예측")
    print("=" * 60)

    # 각 단계별 예상 토큰
    query_gen_input = ocr_tokens + 500  # 시스템 프롬프트
    query_gen_output = 100 * num_queries

    eval_input = ocr_tokens + 2000 * candidates  # 후보 답변
    eval_output = 500 * num_queries

    rewrite_input = ocr_tokens + 2000
    rewrite_output = 2500 * num_queries

    total_input = query_gen_input + eval_input + rewrite_input
    total_output = query_gen_output + eval_output + rewrite_output

    # 비용 계산 (gemini-3-pro-preview 기준)
    input_cost = (total_input / 1_000_000) * 2.00
    output_cost = (total_output / 1_000_000) * 12.00
    total_cost = input_cost + output_cost

    print(f"\n📄 입력 파일: {ocr_file}")
    print(f"   OCR 텍스트 길이: {len(ocr_text):,}자")
    print(f"   추정 토큰 수: {ocr_tokens:,}")

    print("\n⚙️  파라미터:")
    print(f"   생성할 질의 수: {num_queries}")
    print(f"   평가할 후보 수: {candidates}")

    print("\n📊 예상 토큰 사용량:")
    print(f"   입력: {total_input:,} 토큰")
    print(f"   출력: {total_output:,} 토큰")
    print(f"   총합: {total_input + total_output:,} 토큰")

    print("\n💵 예상 비용:")
    print(f"   입력: ${input_cost:.4f}")
    print(f"   출력: ${output_cost:.4f}")
    print(f"   총합: ${total_cost:.4f}")

    print("\n🔄 캐시 적용 시 (50% 절감 추정):")
    print(f"   예상: ${total_cost * 0.5:.4f}")

    print("\n⚠️  실제 비용은 ±20% 오차 가능")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate API cost before execution")
    parser.add_argument(
        "--ocr-file",
        type=str,
        required=True,
        help="Path to OCR text file",
    )
    parser.add_argument(
        "--num-queries",
        type=int,
        default=4,
        help="Number of queries to generate (default: 4)",
    )
    parser.add_argument(
        "--candidates",
        type=int,
        default=3,
        help="Number of candidates to evaluate (default: 3)",
    )

    args = parser.parse_args()

    estimate_cost(
        ocr_file=args.ocr_file,
        num_queries=args.num_queries,
        candidates=args.candidates,
    )


if __name__ == "__main__":
    main()
