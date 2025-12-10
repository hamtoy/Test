# mypy: allow-untyped-decorators
"""QA 타입 정규화 및 쿼리 의도 생성."""

from __future__ import annotations

# Query type mapping for rule loading
QTYPE_MAP: dict[str, str] = {
    "global_explanation": "explanation",
    "reasoning": "reasoning",
    "target_short": "target",
    "target_long": "target",
}


def normalize_qtype(qtype: str) -> str:
    """Query type을 규칙 로딩용으로 정규화.

    Args:
        qtype: 원본 query type (e.g., "target_short")

    Returns:
        정규화된 query type (e.g., "target")
    """
    return QTYPE_MAP.get(qtype, "explanation")


def get_query_intent(
    qtype: str,
    previous_queries: list[str] | None = None,
) -> str:
    """쿼리 타입에 따른 질의 의도 문자열 생성.

    Args:
        qtype: Query type
        previous_queries: 이전 질의 목록 (중복 방지용)

    Returns:
        질의 의도 지시문
    """
    query_intent: str | None = None

    if qtype == "target_short":
        query_intent = "간단한 사실 확인 질문"
        if previous_queries:
            prev_text = "\n".join(f"- {q}" for q in previous_queries if q)
            query_intent += f"""

[중복 방지]
다음 질의에서 다룬 내용과 겹치지 않도록 구체적 팩트(날짜, 수치, 명칭 등)를 질문하세요:
{prev_text}
"""
    elif qtype == "target_long":
        query_intent = "핵심 요점을 묻는 질문"
        if previous_queries:
            prev_text = "\n".join(f"- {q}" for q in previous_queries if q)
            query_intent += f"""

[중복 방지]
다음 질의와 다른 관점/세부 항목을 묻는 질문을 생성하세요:
{prev_text}
"""
    elif qtype == "reasoning":
        query_intent = "추론/예측 질문"
    elif qtype == "global_explanation":
        query_intent = "전체 내용 설명 질문"

    # 중복/병렬 질문 방지 및 서식 공통 지시
    single_focus_clause = """
[단일 포커스 필수]
- 한 가지 과업만 질문 (근거+전망처럼 두 항목을 동시에 묻지 말 것)
- '와/과/및/또는'으로 서로 다른 질문을 병렬 연결 금지
- 필요하면 한 항목만 묻도록 재작성

[서식 금지]
- 괄호() 사용 절대 금지 - 부연 설명이나 동의어 표기 불가
- 정보가 중복되더라도 괄호 없이 자연스러운 문장으로 작성
"""
    if query_intent:
        query_intent += single_focus_clause
    else:
        query_intent = single_focus_clause

    return query_intent
