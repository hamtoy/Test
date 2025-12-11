"""제약조건 로딩 및 관리."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ConstraintSet:
    """제약조건 세트."""

    query_constraints: list[dict[str, Any]] = field(default_factory=list)
    answer_constraints: list[dict[str, Any]] = field(default_factory=list)
    formatting_rules: list[str] = field(default_factory=list)
    rules_list: list[str] = field(default_factory=list)


def load_constraints_from_kg(
    kg: Any,
    normalized_qtype: str,
) -> ConstraintSet:
    """Knowledge Graph에서 제약조건 로딩.

    Args:
        kg: Knowledge Graph 인스턴스
        normalized_qtype: 정규화된 query type

    Returns:
        ConstraintSet with query/answer constraints and formatting rules
    """
    result = ConstraintSet()

    if kg is None:
        return result

    try:
        # Step 1: Enhanced type validation with detailed logging
        constraints = kg.get_constraints_for_query_type(normalized_qtype)

        if not isinstance(constraints, list):
            logger.error(
                "🔴 Invalid constraints type from Neo4j: expected list, got %s. Value: %r",
                type(constraints).__name__,
                repr(constraints)[:100],
            )
            constraints = []

        # Step 2: Validate each item is a dict with detailed logging
        valid_constraints = []
        invalid_items = []

        for c in constraints:
            if isinstance(c, dict):
                valid_constraints.append(c)
            else:
                invalid_items.append(
                    {"type": type(c).__name__, "value": repr(c)[:50]},
                )

        if invalid_items:
            logger.error(
                "🔴 Invalid constraint items dropped: %d/%d. Samples: %s",
                len(invalid_items),
                len(constraints),
                str(invalid_items[:3])[:200],
            )

        # Step 3: Safe category access with .get()
        result.query_constraints = [
            c for c in valid_constraints if c.get("category") in ["query", "both"]
        ]
        result.answer_constraints = [
            c for c in valid_constraints if c.get("category") in ["answer", "both"]
        ]

        # Success logging
        logger.info(
            "✅ Constraints loaded: query=%d, answer=%d",
            len(result.query_constraints),
            len(result.answer_constraints),
        )

        # Step 4: Load formatting rules
        result.formatting_rules = _load_formatting_rules(kg, normalized_qtype)

        logger.info(
            "%s 타입: 질의 제약 %s개, 답변 제약 %s개 조회",
            normalized_qtype,
            len(result.query_constraints),
            len(result.answer_constraints),
        )
    except Exception as e:
        logger.warning("규칙 조회 실패: %s", e)

    # 질의 중복/복합 방지용 공통 제약 추가
    result.query_constraints.append(
        {
            "description": "단일 과업만 묻기: '와/과/및/또는'으로 병렬 질문(두 가지 이상 요구) 금지",
            "priority": 100,
            "category": "query",
        },
    )

    return result


def _load_formatting_rules(
    kg: Any,
    normalized_qtype: str,
) -> list[str]:
    """서식 규칙 로딩.

    Args:
        kg: Knowledge Graph 인스턴스
        normalized_qtype: 정규화된 query type

    Returns:
        서식 규칙 설명 목록
    """
    formatting_rules: list[str] = []

    try:
        fmt_rules = kg.get_formatting_rules_for_query_type(normalized_qtype)

        # Type validation with detailed logging
        if not isinstance(fmt_rules, list):
            logger.error(
                "🔴 Invalid formatting rules type: expected list, got %s",
                type(fmt_rules).__name__,
            )
            return []

        # Validate each rule is a dict
        for fr in fmt_rules:
            if isinstance(fr, dict):
                desc = fr.get("description") or fr.get("text")
                if desc:
                    formatting_rules.append(desc)
            else:
                logger.warning(
                    "Invalid formatting rule (not dict): %s",
                    type(fr).__name__,
                )

        logger.info("✅ Formatting rules loaded: %d", len(formatting_rules))
    except Exception as e:
        logger.debug("서식 규칙 로드 실패: %s", e)

    return formatting_rules


def build_constraints_text(
    answer_constraints: list[dict[str, Any]],
) -> str:
    """답변 제약조건 텍스트 생성.

    Args:
        answer_constraints: 답변 제약조건 목록

    Returns:
        우선순위별 정렬된 제약조건 텍스트
    """
    if not answer_constraints:
        return ""

    def _priority_value(item: dict[str, Any]) -> float:
        val = item.get("priority")
        return float(val) if isinstance(val, (int, float)) else 0.0

    sorted_constraints = sorted(answer_constraints, key=_priority_value, reverse=True)
    return "\n".join(
        f"[우선순위 {c.get('priority', 0)}] {c.get('description', '')}"
        for c in sorted_constraints
    )


def validate_constraint_conflicts(
    answer_constraints: list[dict[str, Any]],
    length_constraint: str,
    normalized_qtype: str,
) -> None:
    """제약조건 충돌 검사 및 경고 로깅.

    Args:
        answer_constraints: 답변 제약조건 목록
        length_constraint: 길이 제약 문자열
        normalized_qtype: 정규화된 query type
    """
    # Extract max_length from length_constraint if present
    max_length_val: int | None = None
    if "50단어" in length_constraint:
        max_length_val = 50
    elif "100단어" in length_constraint:
        max_length_val = 100
    elif "200단어" in length_constraint:
        max_length_val = 200
    elif "300단어" in length_constraint:
        max_length_val = 300

    # Check for paragraph constraints
    min_per_para: int | None = None
    num_paras: int | None = None
    for constraint in answer_constraints:
        desc = constraint.get("description", "").lower()
        if "문단" in desc and "단어" in desc:
            numbers = re.findall(r"\d+", desc)
            if len(numbers) >= 2:
                try:
                    if "각" in desc or "당" in desc:
                        num_paras = int(numbers[0])
                        min_per_para = int(numbers[1])
                except (ValueError, IndexError):
                    pass

    if max_length_val and num_paras and min_per_para:
        # Simple conflict check: if min words per para * num paras > max length
        min_total = min_per_para * num_paras
        if min_total > max_length_val:
            logger.warning(
                "⚠️ 제약 충돌 감지: 최소 %d단어 필요하지만 최대 %d단어 (qtype=%s)",
                min_total,
                max_length_val,
                normalized_qtype,
            )
