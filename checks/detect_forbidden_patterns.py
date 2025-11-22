"""
Detect forbidden patterns in prompts/answers to enforce session rules.

Covers:
- 전체 이미지 설명/요약 요구
- 표/그래프 인용
- 용어 정의 질문
"""

from __future__ import annotations

import re
from typing import List, Dict

FORBIDDEN_PATTERNS: Dict[str, str] = {
    "전체이미지": r"\b전체\s*이미지(에 대해)?\s*(설명|요약)\b",
    "표참조": r"\b표\s*(에 따르면|에서 보이듯|참조)\b",
    "그래프참조": r"\b그래프\s*(에 따르면|에서 보이듯|참조)\b",
    "용어정의": r"\b용어\s*(정의|가 뭐야|설명해)\b",
}


def find_violations(text: str) -> List[Dict]:
    """Return list of violations with pattern key, match text, and span."""
    violations = []
    for key, pat in FORBIDDEN_PATTERNS.items():
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            violations.append({"type": key, "match": m.group(0), "span": m.span()})
    return violations


if __name__ == "__main__":
    sample = """
    전체 이미지 설명해줘. 표에서 보이듯 매출이 상승. What is this term?
    """
    print(find_violations(sample))
