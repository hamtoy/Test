# mypy: allow-untyped-decorators
# mypy: disable-error-code="import-not-found"
"""프롬프트 템플릿 및 빌더 함수."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


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
**절대 규칙**: 이 응답은 최대 200단어, 3-5개 불릿 포인트의 간결한 추론이어야 합니다.
- 굵은 제목 1줄 + 불릿 포인트 3-5개
- 각 불릿은 1-2문장
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
- 굵은 제목 1줄 + 도입 1-2문장 + 불릿 5개 이상 + 결론
- 각 불릿은 1-2문장
- 핵심 포인트를 빠짐없이 다룰 것
❌ {min_chars}자 미만 또는 {min_words}단어 미만 = 실패 (반드시 길이 준수)
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

[필수 3단 구조 - 마크다운 사용 시 반드시 준수]

**1. 서론 (필수)**
- 첫 줄: **굵은 제목** (핵심 결론을 제목으로)
- 도입 1-2문장: 전체 맥락 요약

**2. 본론 (필수)**
- 불릿 포인트 3-5개로 근거 제시
- 각 불릿: - **항목명**: 설명 형식

**3. 결론 (필수 - 생략 불가)**
- 마지막 문단에서 종합 결론 작성
- "이처럼...", "따라서...", "종합하면..." 등으로 시작
- 앞서 제시한 근거를 바탕으로 최종 판단 제시

[올바른 형식 예시]
**금리 인하 결정에 가장 큰 영향을 미칠 핵심 지표: 인플레이션**

파월 의장의 발언과 최근 고용 시장 추이를 고려할 때... (도입)

- **디스인플레이션 확인**: 파월 의장은 하원 청문회에서...
- **고용 시장 상황**: 고용 시장은 일부 완화되는 조짐을...
- **정책 도구 활용**: 연준은 필요한 도구를 사용하고 있으며...

따라서, 연준이 금리 인하를 결정할 때 가장 중요하게 고려할 지표는 인플레이션 관련 데이터로 분석됩니다. (결론)

{fewshot_text}

[금지 사항]
- '근거', '추론 과정', '결론' 등 명시적 라벨 금지
- 불필요한 서론 금지 (바로 핵심으로)
- 장황한 설명 금지
- ❌ 결론 없이 본론만 나열하면 실패
- ❌ 마크다운 형식 사용 시 3단 구조 미준수 = 실패"""

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

[필수 구조 - 마크다운 형식 엄격 준수]

1. 도입 문단: 1-2문장으로 전체 맥락 요약
2. **굵은 소제목**: 섹션 구분용 (예: **파월 의장 발언 관련**)
3. 불릿 항목: - **항목명**: 설명 (항목명 반드시 굵게)
4. 결론 문단: "요약하면..." 또는 "이처럼..." 으로 시작

[올바른 형식 예시]
로블록스의 현황과 미래 전망을 분석한 내용입니다.

**노코드 개발 보편화와 개발자 저변 확대**
- **코드 어시스턴트 도입**: 로블록스는 생성형 AI가 코드를 자동 생성해주는 기능을 공개했습니다.
- **개발 진입장벽 완화**: 전문적인 코딩 지식이 없는 사람도 아이템 제작이 가능해졌습니다.

**로블록스 트래픽 회복세 지속**
- **트래픽 및 결제액 증가**: 2023년 앱 트래픽과 인앱결제액의 증가세가 지속되고 있습니다.
- **성장세 가속화**: 인앱결제액 전년 동기 대비 증가율이 가속화되었습니다.

요약하면, 로블록스는 생성형 AI 도입으로 긍정적인 성장 전망을 가지고 있습니다.

{fewshot_text}

[핵심 규칙 - 위반 시 실패]
❌ 소제목에 ** 없으면 실패 → 반드시 **굵은 소제목** 형식
❌ 불릿 항목명에 ** 없으면 실패 → 반드시 - **항목명**: 설명 형식
❌ 결론 문단 없으면 실패
❌ '서론', '본론', '결론' 라벨 사용 금지"""

    elif normalized_qtype == "target":
        if qtype == "target_short":
            # Few-Shot: Load examples from Neo4j for target_short
            fewshot_text = ""
            try:
                if kg is not None:
                    from src.qa.dynamic_examples import DynamicExampleSelector

                    example_selector = DynamicExampleSelector(kg)
                    fewshot_examples = example_selector.select_best_examples(
                        "target_short", {}, k=1
                    )
                    if fewshot_examples:
                        ex = fewshot_examples[0]
                        ex_text = ex.get("example", "")[:500]  # Short examples
                        fewshot_text = f"""
[좋은 단답 예시 - 이 길이와 형식을 참고하세요]
{ex_text}
---
위 예시처럼 **1-2문장, 마크다운 없이** 작성하세요.
"""
                        logger.info(
                            "Few-Shot target_short example loaded: %d chars",
                            len(ex_text),
                        )
            except Exception as e:
                logger.debug("Few-shot loading failed: %s", e)

            extra_instructions = f"""
⚠️ 중요: 반드시 1-2문장만 작성. 3문장 이상 작성하면 실패입니다.
- 명확하고 간결한 사실 전달
- 불필요한 수식어 배제
- 구체적 수치나 데이터 포함
❌ 볼드체(**) 사용 금지 - 줄글형 답변에는 **없이** 작성
❌ 설명문(global_explanation)에서 이미 사용된 문장을 그대로 가져오지 말 것
→ 같은 세션에서 생성된 설명문 내용과 중복되는 답변은 위반입니다.

{fewshot_text}"""
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
            "- **첫 번째 요인**: 설명\n"
            "- **두 번째 요인**: 설명\n"
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
