# mypy: allow-untyped-decorators
# mypy: disable-error-code="import-not-found"
"""프롬프트 템플릿 및 빌더 함수."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_length_constraint(qtype: str, ocr_len: int) -> tuple[str, int | None]:
    """타입과 OCR 길이에 따른 길이 제약 문자열 생성.

    Args:
        qtype: Query type (normalized 아닌 원본)
        ocr_len: OCR 텍스트 길이

    Returns:
        (length_constraint 문자열, max_chars 값 또는 None)
    """
    max_chars: int | None = None
    length_constraint = ""

    if qtype == "reasoning":
        length_constraint = """
[CRITICAL - 길이 제약]
**절대 규칙**: 이 응답은 최대 200단어, 3-5개 불릿 포인트의 간결한 추론이어야 합니다.
- 굵은 제목 1줄 + 불릿 포인트 3-5개
- 각 불릿은 1-2문장
- 최대 200단어 초과 금지
"""
    elif qtype == "global_explanation":
        min_chars = int(ocr_len * 0.6)
        max_chars = int(ocr_len * 0.8)
        length_constraint = f"""
[CRITICAL - 길이 제약]
**절대 규칙**: 이 응답은 OCR 원문 길이({ocr_len}자)에 비례하여 **최소 {min_chars}자 ~ 최대 {max_chars}자** 분량입니다.
- 5-8개 문단으로 구성
- 굵은 제목 1줄 + 도입 1-2문장 + 불릿 5개 이상 + 결론
- 각 불릿은 1-2문장
- 핵심 포인트를 빠짐없이 다룰 것
❌ {min_chars}자 미만 = 실패 (반드시 길이 준수)
"""
    elif qtype == "target_short":
        length_constraint = """
[CRITICAL - 길이 제약 ⚠️ 가장 중요]
1-2문장, 50-150자만 작성하세요.
❌ 3문장 이상 = 실패
❌ 150자 초과 = 실패
❌ 배경 설명 = 실패
❌ 볼드체(**) 사용 = 실패
❌ 설명문(global_explanation) 답변 내용 복사 = 실패
✅ 핵심 사실만 1-2문장으로, 마크다운 없이 답변

[중요 규칙 - 설명문 정보 사용 금지]
같은 세션에서 생성된 설명문(global_explanation)의 내용을 그대로 가져와
단답형으로 요약하는 것은 금지됩니다.
→ target_short는 설명문에 없는 새로운 관점/정보를 제공해야 합니다.
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
    extra_instructions = "질의 유형에 맞게 작성하세요."

    if normalized_qtype == "reasoning":
        # Few-Shot: Load examples from Neo4j for reasoning
        fewshot_text = ""
        try:
            if kg is not None:
                from src.qa.dynamic_examples import DynamicExampleSelector

                example_selector = DynamicExampleSelector(kg)
                fewshot_examples = example_selector.select_best_examples(
                    "reasoning", {}, k=1
                )
                if fewshot_examples:
                    ex = fewshot_examples[0]
                    ex_text = ex.get("example", "")[:2000]  # Truncate if too long
                    fewshot_text = f"""
[좋은 추론 답변 예시 - 이 구조와 형식을 참고하세요]
{ex_text}
---
위 예시처럼 **일관된 형식**으로 작성하세요.
"""
                    logger.info(
                        "Few-Shot reasoning example loaded: %d chars", len(ex_text)
                    )
        except Exception as e:
            logger.debug("Few-shot loading failed: %s", e)

        extra_instructions = f"""추론형 답변입니다.

[두 가지 형식 중 선택 - 혼용 금지]

**형식 A: 구조화 형식 (마크다운 사용)**
1. 첫 줄: **굵은 제목** (핵심 전망)
2. 소제목: **굵은 소제목**으로 구분
3. 불릿: - **항목명**: 설명 (항목명도 굵게)
4. 결론

**형식 B: 일반 문장 형식 (마크다운 없이)**
문단 구분만 하고 **굵게**나 - 불릿 없이 일반 문장으로 서술.

{fewshot_text}

[핵심 규칙]
❌ 혼용 금지: 마크다운 쓸 거면 **굵은 제목**, **굵은 소제목**, - **굵은 항목명**: 모두 사용
❌ 첫 줄만 굵고 나머지 평문 = 실패
✅ 형식 A 또는 형식 B 중 하나를 일관되게 사용

[금지 사항]
- '근거', '추론 과정', '결론' 등 명시적 라벨 금지
- 불필요한 서론 금지 (바로 핵심으로)
- 장황한 설명 금지"""

    elif normalized_qtype == "explanation":
        # Few-Shot: Load examples from Neo4j for better length adherence
        fewshot_text = ""
        try:
            if kg is not None:
                from src.qa.dynamic_examples import DynamicExampleSelector

                example_selector = DynamicExampleSelector(kg)
                fewshot_examples = example_selector.select_best_examples(
                    "explanation", {}, k=1
                )
                if fewshot_examples:
                    ex = fewshot_examples[0]
                    ex_text = ex.get("example", "")[:1500]  # Truncate if too long
                    fewshot_text = f"""
[좋은 답변 예시 - 이 길이와 구조를 참고하세요]
{ex_text}
---
위 예시처럼 **충분한 길이와 구조**로 작성하세요.
"""
                    logger.info("Few-Shot example loaded: %d chars", len(ex_text))
        except Exception as e:
            logger.debug("Few-shot loading failed: %s", e)

        extra_instructions = f"""설명형 답변입니다.
[필수 구조 - 반드시 아래 형식 준수]
1. 첫 줄: **굵은 제목** 형식으로 핵심 내용 한 문장 (예: **미국 증시, 고용 완화로 상승 마감**)
2. 도입: 1-2문장으로 전체 맥락 요약
3. 소제목: "주요 변화 요인은 다음과 같습니다." 같은 전환문
4. 본문: 불릿 포인트로 주요 요인 나열 (최소 5개)
   - 각 불릿 형식: - **항목명**: 설명 (항목명 굵게!)
5. 결론: 마지막 문장으로 종합

[올바른 형식 예시]
**미국 증시, 고용 완화와 금리 인하 기대로 상승 마감**

미국 증시는 완화된 고용 데이터와 파월 의장 발언에 힘입어... (도입 1-2문장)

미국 증시 상승에 영향을 준 주요 변화 요인은 다음과 같습니다.

- **파월 의장의 금리 인하 기대 표명**: 파월 의장은 하원 청문회에서...
- **예상치를 하회한 1월 구인 건수**: 1월 채용공고는 전월 대비...
- **시장 기대치를 밑돈 2월 민간 고용 증가**: 2월 ADP 민간고용은...

이처럼 고용 시장의 완화 신호와... (결론)

{fewshot_text}

[금지 사항]
- '서론', '본론', '결론' 등 라벨 금지
- 불필요한 반복, 장황한 수식어 금지
- 첫 줄을 평문으로 작성하면 실패 (반드시 **굵은 제목**)
- 불릿 항목명을 평문으로 작성하면 실패 (반드시 **굵은 항목명**: 설명)"""

    elif normalized_qtype == "target":
        if qtype == "target_short":
            extra_instructions = """
⚠️ 중요: 반드시 1-2문장만 작성. 3문장 이상 작성하면 실패입니다.
- 명확하고 간결한 사실 전달
- 불필요한 수식어 배제
- 구체적 수치나 데이터 포함
❌ 볼드체(**) 사용 금지 - 줄글형 답변에는 **없이** 작성
❌ 설명문(global_explanation)에서 이미 사용된 문장을 그대로 가져오지 말 것
→ 같은 세션에서 생성된 설명문 내용과 중복되는 답변은 위반입니다."""
        elif qtype == "target_long":
            extra_instructions = """
- OCR 원문의 특정 내용에 집중하여 서술
- 핵심 맥락과 함께 간결하게 답변
- 불필요한 배경 설명 최소화
❌ 볼드체(**) 사용 금지 - 줄글형 답변에는 **없이** 작성
"""

    return extra_instructions


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
            "\n\n[마크다운 사용 규칙 - 필수 준수]\n"
            "✅ 허용되는 마크다운:\n"
            "  - **bold**: 핵심 키워드 강조용 (예: **주요 포인트**)\n"
            "  - 1. 2. 3.: 순서가 있는 목록\n"
            "  - - 항목: 순서가 없는 불릿 포인트\n"
            "\n"
            "❌ 사용 금지 마크다운:\n"
            "  - *italic*: 가독성 저하 (절대 사용 금지)\n"
            "  - ### 제목: 불필요한 헤더 (절대 사용 금지)\n"
            "  - `코드`: 일반 QA에 불필요\n"
            "\n"
            "예시 (올바른 형식):\n"
            "**미-중 갈등 고조 및 투자 심리 위축**\n"
            "전일 한국 증시는 여러 요인이 복합적으로 작용...\n"
            "- 첫 번째 요인: 설명\n"
            "- 두 번째 요인: 설명\n"
        )

    return formatting_text


def build_priority_hierarchy(
    normalized_qtype: str,
    length_constraint: str,
    formatting_text: str,
    extra_instructions: str,
) -> str:
    """우선순위 계층 프롬프트 생성.

    Args:
        normalized_qtype: 정규화된 query type
        length_constraint: 길이 제약 문자열
        formatting_text: 서식 규칙 문자열
        extra_instructions: 추가 지시사항

    Returns:
        우선순위 계층 프롬프트
    """
    markdown_rule = (
        "평문만 (마크다운 제거)"
        if normalized_qtype == "target"
        else "구조만 마크다운(제목/목록), 내용은 평문"
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
[PRIORITY HIERARCHY]
Priority 0 (CRITICAL):
- {normalized_qtype} 타입: {markdown_rule}

Priority 10 (HIGH):
- 최대 길이: {max_length_text} 이내
- 길이 제약 위반은 불가능

Priority 20 (MEDIUM):
- 구조화 형식: {formatting_text if formatting_text else "기본 서식"}

Priority 30 (LOW):
- 추가 지시: {extra_instructions}

[CONFLICT RESOLUTION]
만약 여러 제약이 충돌한다면:
→ Priority 0 > Priority 10 > Priority 20 > Priority 30

[REASONING BEFORE RESPONSE]
응답하기 전에 다음을 확인하세요:
1. 현재 qtype은 무엇인가? → 올바른 마크다운 규칙 확인 (Priority 0)
2. 길이 제약은 몇 단어인가? → {max_length_text} 이내 유지 (Priority 10)
3. 구조화 방식은? → formatting_text 규칙 적용 (Priority 20)
4. 추가 요청사항은? → extra_instructions 추가 처리 (Priority 30)
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

    return f"""{priority_hierarchy}

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
