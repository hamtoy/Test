import re


def test_regex():
    text = "**고용시장 완화 및 파월 의장 발언의 주요 내용*\n*"

    print(f"Original: {repr(text)}")

    # 1.2 볼드 마커 정규화: 짝이 안 맞는 **텍스트* / *텍스트** 제거
    # Current regex in src/web/utils.py
    text = re.sub(r"\*\*([^*]+)\*(?!\*)", r"\1", text)
    print(f"After 1.2: {repr(text)}")

    # 5. 공통 정리: 남은 마크다운 제거 및 불릿 제거
    # Current regex in src/web/utils.py
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    print(f"After 5: {repr(text)}")

    # Proposed fix: Handle multiline and broken markers
    text = "**고용시장 완화 및 파월 의장 발언의 주요 내용*\n*"
    print(f"\nTesting Fix on: {repr(text)}")

    # Fix broken markers like **...* \n *
    text = re.sub(r"\*\*([^*]+)\*\s*\n\s*\*", r"**\1**", text)
    print(f"After Fix 1: {repr(text)}")

    # Remove bolding (handling newlines)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text, flags=re.DOTALL)
    print(f"After Fix 2: {repr(text)}")


if __name__ == "__main__":
    test_regex()
