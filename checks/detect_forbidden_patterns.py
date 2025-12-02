"""Detect forbidden patterns in prompts/answers to enforce session rules.

Covers:
- 전체 이미지 설명/요약 요구
- 표/그래프 인용
- 용어 정의 질문
"""

from __future__ import annotations

import re
from typing import List, Dict, Any

from src.config.constants import ALLOWED_BOLD_CONTEXTS, PROSE_BOLD_PATTERN

FORBIDDEN_PATTERNS: Dict[str, str] = {
    "전체이미지": r"\b전체\s*이미지(에 대해)?\s*(설명|요약)\b",
    "표참조": r"\b표\s*(에 따르면|에서 보이듯|참조)\b",
    "그래프참조": r"\b그래프\s*(에 따르면|에서 보이듯|참조)\b",
    "용어정의": r"\b용어\s*(정의|가 뭐야|설명해)\b",
}

FORMATTING_PATTERNS: Dict[str, Dict[str, Any]] = {
    "prose_bold_violation": {
        "pattern": PROSE_BOLD_PATTERN,
        "description": "줄글 본문 내 볼드체 사용 금지",
        "severity": "error",
        "example_bad": "**달러화**는 상승했습니다.",
        "example_good": "달러화는 상승했습니다.",
    },
    "composite_query": {
        "pattern": r".+[와과]\s+.+[은는이가]\s+무엇입니까\?",
        "description": "복합 질문 금지 (하나의 질의는 하나의 정보만)",
        "severity": "warning",
        "example_bad": "상승률과 전망은 무엇입니까?",
    },
    "explicit_structure_label": {
        "pattern": r"\*\*(근거|추론\s*과정|결론|서론|본론|요약문?|정리)\*\*",
        "description": "명시적 구조 라벨/소제목 사용 금지",
        "severity": "error",
        "example_bad": "**근거**\\n- 내용...",
        "example_good": "이러한 전망의 배경에는...",
    },
    "numbered_structure": {
        "pattern": r"(?m)^(첫째|둘째|셋째|넷째)[,.]",
        "description": "'첫째', '둘째' 등 나열형 구조 사용 지양",
        "severity": "warning",
        "example_bad": "첫째, ... 둘째, ...",
        "example_good": "먼저... 또한... 이와 함께...",
    },
}


def find_violations(text: str) -> List[Dict]:
    """Return list of violations with pattern key, match text, and span."""
    violations: List[Dict] = []
    for key, pat in FORBIDDEN_PATTERNS.items():
        violations.extend(
            {"type": key, "match": m.group(0), "span": m.span()}
            for m in re.finditer(pat, text, flags=re.IGNORECASE)
        )
    return violations


if __name__ == "__main__":
    sample = """
    전체 이미지 설명해줘. 표에서 보이듯 매출이 상승. What is this term?
    """
    print(find_violations(sample))


def find_formatting_violations(text: str) -> List[Dict[str, Any]]:
    """서식 규칙 위반을 검사한다."""
    violations: List[Dict[str, Any]] = []

    for name, config in FORMATTING_PATTERNS.items():
        for match in re.finditer(config["pattern"], text):
            line_start = text.rfind("\n", 0, match.start()) + 1
            line = text[line_start : match.end()]

            stripped = line.strip()
            is_allowed = False
            for allowed in ALLOWED_BOLD_CONTEXTS:
                if re.match(allowed, stripped):
                    is_allowed = True
                    break

            if not is_allowed:
                violations.append(
                    {
                        "type": f"formatting:{name}",
                        "match": match.group(),
                        "position": match.start(),
                        "description": config.get("description", ""),
                        "severity": config.get("severity", "warning"),
                    }
                )

    return violations
