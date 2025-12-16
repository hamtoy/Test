"""프롬프트 템플릿 및 빌더 함수.

이 모듈은 다양한 질의 유형에 맞는 프롬프트를 생성하는 빌더 함수를 제공합니다.
"""

from __future__ import annotations

import logging
from typing import Any

from src.processing.example_selector import DynamicExampleSelector

__all__ = [
    "DynamicExampleSelector",
    "build_answer_prompt",
    "build_extra_instructions",
    "build_formatting_text",
    "build_length_constraint",
    "build_priority_hierarchy",
]

logger = logging.getLogger(__name__)

_FEWSHOT_LOADING_FAILED = "Few-shot loading failed: %s"


def _load_fewshot_text(
    kg: Any,
    example_key: str,
    truncate_at: int,
    header: str,
    guidance: str,
    log_label: str,
) -> str:
    """Neo4j 기반 few-shot 예시를 안전하게 로드."""
    if kg is None:
        return ""
    try:
        example_selector = DynamicExampleSelector(kg)
        fewshot_examples = example_selector.select_best_examples(
            example_key,
            {},
            k=1,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug(_FEWSHOT_LOADING_FAILED, exc)
        return ""

    if not fewshot_examples:
        return ""

    ex_text = str(fewshot_examples[0].get("example", ""))[:truncate_at]
    if not ex_text:
        return ""

    logger.info("Few-Shot %s example loaded: %d chars", log_label, len(ex_text))
    return f"""
[{header}]
{ex_text}
---
{guidance}
"""


def build_length_constraint(
    qtype: str, ocr_len: int, ocr_text: str = ""
) -> tuple[str, int | None]:
    """타입과 OCR 길이에 따른 길이 제약 문자열 생성.

    Args:
        qtype: Query type (normalized 아닌 원본)
        ocr_len: OCR 텍스트 길이
        ocr_text: OCR 텍스트 (단어 수 계산용)

    Returns:
        (length_constraint 문자열, max_chars 값 또는 None)
    """
    max_chars: int | None = None
    length_constraint = ""

    if qtype == "reasoning":
        length_constraint = """
[CRITICAL - 길이 제약]
**절대 규칙**: 이 응답은 최대 200단어, 핵심 포인트 2-5개로 구성된 간결한 추론이어야 합니다.
- 핵심 포인트 2-5개 (각 포인트는 1-2문장)
- 최대 200단어 초과 금지
"""
    elif qtype == "global_explanation":
        min_chars = int(ocr_len * 0.6)
        max_chars = int(ocr_len * 0.8)
        # 단어 수 제약 추가 (OCR 텍스트 기반)
        ocr_word_count = len(ocr_text.split()) if ocr_text else ocr_len // 10
        min_words = int(ocr_word_count * 0.6)
        max_words = int(ocr_word_count * 0.8)
        length_constraint = f"""
[CRITICAL - 길이 제약]
**절대 규칙**: 이 응답은 OCR 원문 길이({ocr_len}자, {ocr_word_count}단어)에 비례합니다.
- 문자 수: **최소 {min_chars}자 ~ 최대 {max_chars}자**
- 단어 수: **최소 {min_words}단어 ~ 최대 {max_words}단어**
- 5-8개 문단으로 구성
- 도입 1-2문장 + 핵심 항목 5개 이상 + 결론
- 각 항목은 1-2문장
- 핵심 포인트를 빠짐없이 다룰 것
❌ {min_chars}자 미만 또는 {min_words}단어 미만 = 실패 (반드시 길이 준수)
"""
    elif qtype == "target_short":
        length_constraint = """
[길이 제약] 1-2문장(50-150자), 마크다운 금지, 설명문 내용 사용 금지
"""
    elif qtype == "target_long":
        length_constraint = """
[CRITICAL - 길이 제약]
200-400자, 3-4문장의 간결한 서술형 답변이어야 합니다.
- 정확히 3-4개 문장으로 구성
- 각 문장은 50-100자 정도
- 핵심 내용만 포함, 장황한 설명 금지
- 문단 구분 없이 하나의 문단으로 작성
❌ 볼드체(**) 사용 금지 - 마크다운 없이 평문으로 작성
"""

    return length_constraint, max_chars


def build_extra_instructions(
    qtype: str,
    normalized_qtype: str,
    kg: Any = None,
) -> str:
    """타입별 추가 지시사항 생성.

    Args:
        qtype: 원본 query type
        normalized_qtype: 정규화된 query type
        kg: Knowledge Graph (Few-shot 예시 로딩용)

    Returns:
        추가 지시사항 문자열
    """
    if normalized_qtype == "reasoning":
        fewshot_text = _load_fewshot_text(
            kg,
            example_key="reasoning",
            truncate_at=2000,
            header="좋은 추론 답변 예시 - 이 구조와 형식을 참고하세요",
            guidance="위 예시의 내용/흐름을 참고하되, 출력은 아래 JSON 스키마로 변환해 작성하세요.",
            log_label="reasoning",
        )
        return f"""추론형 답변입니다.

⚠️ 중요: 답변은 **마크다운/불릿 없이** 먼저 생성하고, 후처리에서 형식을 적용합니다.

[출력 형식 - JSON ONLY]
- 반드시 **JSON 객체 1개만** 출력 (코드펜스/추가 설명/머리말/꼬리말 금지)
- JSON 값 문자열에는 마크다운 금지 (**bold**, - 불릿, 1. 번호, ### 헤더 등)
- 스키마(키 이름 고정):
{{
  "intro": "1-2문장. 첫 문장에 핵심 결론(평문).",
  "sections": [
    {{
      "title": "소제목(서론/본론/결론/요약 같은 라벨 금지)",
      "items": [
        {{"label": "항목명", "text": "1-2문장 설명(평문)"}},
        {{"label": "항목명", "text": "1-2문장 설명(평문)"}}
      ]
    }}
  ],
  "conclusion": "마지막 1-2문장. '결론적으로' 또는 '종합하면'으로 시작"
}}

[구조/개수 규칙]
- sections: 1개 이상
- items(전체 합): **최소 2개 ~ 최대 5개**
- conclusion은 반드시 포함(불릿으로 끝내지 말 것)

{fewshot_text}"""

    if normalized_qtype == "explanation":
        fewshot_text = _load_fewshot_text(
            kg,
            example_key="explanation",
            truncate_at=1500,
            header="좋은 답변 예시 - 이 길이와 구조를 참고하세요",
            guidance="위 예시의 내용/흐름을 참고하되, 출력은 아래 JSON 스키마로 변환해 작성하세요.",
            log_label="explanation",
        )
        return f"""설명형 답변입니다.

⚠️ 중요: 답변은 **마크다운/불릿 없이** 먼저 생성하고, 후처리에서 형식을 적용합니다.

[출력 형식 - JSON ONLY]
- 반드시 **JSON 객체 1개만** 출력 (코드펜스/추가 설명/머리말/꼬리말 금지)
- JSON 값 문자열에는 마크다운 금지 (**bold**, - 불릿, 1. 번호, ### 헤더 등)
- 스키마(키 이름 고정):
{{
  "intro": "1-2문장 도입(평문)",
  "sections": [
    {{
      "title": "소제목(번호 금지)",
      "items": [
        {{"label": "항목명", "text": "1-2문장 설명(평문)"}}
      ]
    }}
  ],
  "conclusion": "마지막 1-2문장. 반드시 '요약하면,' 또는 '이처럼'로 시작"
}}

[구조/개수 규칙]
- items(전체 합): **최소 5개 이상**
- conclusion은 반드시 포함
- title/label/text에 '서론/본론/결론' 같은 라벨 사용 금지

{fewshot_text}"""

    if normalized_qtype == "target" and qtype == "target_short":
        fewshot_text = _load_fewshot_text(
            kg,
            example_key="target_short",
            truncate_at=500,
            header="좋은 단답 예시 - 이 길이와 형식을 참고하세요",
            guidance="위 예시처럼 **1-2문장, 마크다운 없이** 작성하세요.",
            log_label="target_short",
        )
        return f"""
⚠️ 중요: 반드시 1-2문장만 작성. 3문장 이상 작성하면 실패입니다.
- 명확하고 간결한 사실 전달
- 불필요한 수식어 배제
- 구체적 수치나 데이터 포함
❌ 볼드체(**) 사용 금지 - 줄글형 답변에는 **없이** 작성
❌ 설명문(global_explanation)에서 이미 사용된 문장을 그대로 가져오지 말 것
→ 같은 세션에서 생성된 설명문 내용과 중복되는 답변은 위반입니다.

{fewshot_text}"""

    if normalized_qtype == "target" and qtype == "target_long":
        return """
- OCR 원문의 특정 내용에 집중하여 서술
- 핵심 맥락과 함께 간결하게 답변
- 불필요한 배경 설명 최소화
❌ 볼드체(**) 사용 금지 - 줄글형 답변에는 **없이** 작성
"""

    return "질의 유형에 맞게 작성하세요."


def build_formatting_text(
    formatting_rules: list[str],
    normalized_qtype: str,
) -> str:
    """서식 규칙 및 마크다운 정책 생성.

    Args:
        formatting_rules: 서식 규칙 목록
        normalized_qtype: 정규화된 query type

    Returns:
        서식 지시 문자열
    """
    formatting_text = ""
    if formatting_rules:
        formatting_text = "\n[서식 규칙 - 필수 준수]\n" + "\n".join(
            f"- {r}" for r in formatting_rules
        )

    # Add markdown usage policy based on qtype
    if normalized_qtype == "target":
        formatting_text += (
            "\n\n[마크다운 사용]\n"
            "평문으로만 작성하세요. "
            "마크다운(**bold**, *italic*, - 등)은 사용하지 마세요. "
            "(→ 후처리에서 모두 제거됩니다)"
        )
    elif normalized_qtype in {"explanation", "reasoning"}:
        formatting_text += (
            "\n\n[출력 형식]\n"
            "⚠️ 마크다운을 직접 작성하지 마세요. (후처리에서 소제목/불릿 형식을 적용합니다)\n"
            "- 출력은 JSON 객체 1개만 허용\n"
            "- JSON 값 문자열은 평문으로만 작성\n"
        )

    return formatting_text


def build_priority_hierarchy(
    normalized_qtype: str,
    length_constraint: str,
    formatting_text: str,
) -> str:
    """우선순위 계층 프롬프트 생성.

    Args:
        normalized_qtype: 정규화된 query type
        length_constraint: 길이 제약 문자열
        formatting_text: 서식 규칙 문자열

    Returns:
        우선순위 계층 프롬프트
    """
    markdown_rule = (
        "평문만 (마크다운 제거)"
        if normalized_qtype == "target"
        else "JSON로 구조화 (후처리로 마크다운 적용)"
    )

    max_length_text = "[MAX_LENGTH]단어"
    if "최대 50단어" in length_constraint or "50단어" in length_constraint:
        max_length_text = "50단어"
    elif "최대 100단어" in length_constraint or "100단어" in length_constraint:
        max_length_text = "100단어"
    elif "200단어" in length_constraint:
        max_length_text = "200단어"
    elif "300단어" in length_constraint:
        max_length_text = "300단어"

    return f"""
[규칙] {normalized_qtype} 타입 | {markdown_rule} | 최대 {max_length_text}
{formatting_text if formatting_text else ""}
"""


def build_answer_prompt(
    query: str,
    truncated_ocr: str,
    constraints_text: str,
    rules_in_answer: str,
    priority_hierarchy: str,
    length_constraint: str,
    formatting_text: str,
    difficulty_text: str,
    extra_instructions: str,
) -> str:
    """최종 답변 생성 프롬프트 조합.

    Args:
        query: 생성된 질의
        truncated_ocr: 잘린 OCR 텍스트
        constraints_text: 제약조건 텍스트
        rules_in_answer: 규칙 목록 텍스트
        priority_hierarchy: 우선순위 계층 프롬프트
        length_constraint: 길이 제약 문자열
        formatting_text: 서식 규칙 문자열
        difficulty_text: 난이도 힌트
        extra_instructions: 추가 지시사항

    Returns:
        완성된 답변 프롬프트
    """
    evidence_clause = "숫자·고유명사는 OCR에 나온 값 그대로 사용하고, 근거가 되는 문장을 1개 포함하세요."

    # 교육 목적 면책 조항 (안전 필터용, 간소화)
    educational_disclaimer = (
        "[교육/분석 목적] 금융 교육 자료 제작용. OCR 내용 객관적 설명."
    )

    return f"""{educational_disclaimer}

{priority_hierarchy}

{length_constraint}

{formatting_text}

[제약사항]
{constraints_text or rules_in_answer}

[질의]: {query}

[OCR 텍스트]
{truncated_ocr}

위 길이/형식 제약과 규칙을 엄격히 준수하여 한국어로 답변하세요.
{difficulty_text}
{evidence_clause}
{extra_instructions}"""
