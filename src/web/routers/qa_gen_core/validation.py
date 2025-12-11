"""검증 및 재생성 로직."""

from __future__ import annotations

import logging
from typing import Any

from checks.detect_forbidden_patterns import (
    find_formatting_violations,
    find_violations,
)

logger = logging.getLogger(__name__)


async def validate_and_regenerate(
    agent: Any,
    draft_answer: str,
    qtype: str,
    normalized_qtype: str,
    query: str,
    unified_validator: Any,
    answer_constraints: list[dict[str, Any]],
    length_constraint: str,
    ocr_text: str,
    kg_wrapper: Any = None,
    pipeline: Any = None,
    validator_class: type | None = None,
) -> str:
    """답변 검증 및 필요시 재생성.

    Args:
        agent: GeminiAgent 인스턴스
        draft_answer: 초안 답변
        qtype: 원본 query type
        normalized_qtype: 정규화된 query type
        query: 생성된 질의
        unified_validator: UnifiedValidator 인스턴스
        answer_constraints: 답변 제약조건 목록
        length_constraint: 길이 제약 문자열
        ocr_text: 원본 OCR 텍스트
        kg_wrapper: Knowledge Graph (옵션)
        pipeline: Pipeline 인스턴스 (옵션)
        validator_class: Validator 클래스 (옵션)

    Returns:
        검증/수정된 최종 답변
    """
    # 통합 검증으로 수집할 위반/경고 (질의 포함하여 금지 패턴 검증 강화)
    val_result = unified_validator.validate_all(
        draft_answer,
        normalized_qtype,
        query,
    )
    all_issues: list[str] = []

    # 문장 수 검증
    sentences = [
        s
        for s in draft_answer.replace("?", ".").replace("!", ".").split(".")
        if s.strip()
    ]
    sentence_count = len(sentences)

    # target_short만 문장 수 제한 (1-2문장), 나머지 타입은 검증 skip
    if qtype == "target_short" and sentence_count > 2:
        all_issues.append(f"1-2문장으로 축소 필요 (현재 {sentence_count}문장)")

    all_violations: list[str] = []

    # 요약문 헤더 검증
    if normalized_qtype == "reasoning" and (
        "요약문" in draft_answer or "요약" in draft_answer.splitlines()[0]
    ):
        all_violations.append("summary_header_not_allowed")

    # Explicit rule compliance check when KG is available
    if kg_wrapper is not None and validator_class is not None:
        try:
            validator = validator_class(kg_wrapper)
            rule_check = validator._check_rule_compliance(
                draft_answer,
                normalized_qtype,
            )
            score = rule_check.get("score")
            score_val = score if isinstance(score, (int, float)) else 1.0
            if rule_check.get("violations") and score_val < 0.3:
                all_violations.extend(rule_check.get("violations", []))
        except Exception:
            pass

    # 기존 탐지 + 통합 검증 병합
    violations = find_violations(draft_answer)
    if violations:
        for v in violations:
            v_type = v["type"]
            # NOTE: 시의성 표현은 인간 작업자가 최종 수정 예정이므로 검증 제외
            if v_type.startswith("error_pattern:시의성"):
                continue
            if "temporal" in v_type.lower():
                continue  # 시의성 관련 모든 패턴 제외
            all_violations.append(v_type)

    formatting_violations = find_formatting_violations(draft_answer)
    for fv in formatting_violations:
        if fv.get("severity") == "error":
            all_violations.append(fv["type"])
            logger.warning(
                "서식 위반 감지: %s - '%s'",
                fv.get("description", ""),
                fv["match"],
            )

    # Pipeline 검증
    if pipeline is not None:
        validation = pipeline.validate_output(
            normalized_qtype,
            draft_answer,
        )
        if not validation.get("valid", True):
            all_violations.extend(validation.get("violations", []))
        missing_rules = validation.get("missing_rules_hint", [])
        if missing_rules:
            logger.debug("누락 가능성 있는 규칙: %s", missing_rules)

    # UnifiedValidator 결과 병합
    if val_result.has_errors():
        all_violations.extend(
            [v.get("type", "rule") for v in val_result.violations],
        )
    if val_result.warnings:
        all_issues.extend(val_result.warnings)

    # 시의성 관련 위반 필터링 (인간 작업자가 최종 수정 예정)
    all_violations = [
        v for v in all_violations if "시의성" not in v and "temporal" not in v.lower()
    ]

    if all_violations:
        all_issues.extend(all_violations[:3])

    # 재생성 필요 시
    if all_issues:
        combined_request = "; ".join(all_issues)
        logger.warning("검증 실패, 재생성 시도: %s", combined_request)
        try:
            rewritten = await agent.rewrite_best_answer(
                ocr_text=ocr_text,
                best_answer=draft_answer,
                edit_request=f"다음 사항 수정: {combined_request}",
                cached_content=None,
                constraints=answer_constraints,
                length_constraint=length_constraint,
            )
            # 빈 응답이면 원본 유지
            if rewritten and rewritten.strip():
                return rewritten
            else:
                logger.warning("재생성 빈 응답, 원본 답변 사용")
        except Exception as e:
            # 재생성 실패 시 원본 답변 사용 (Gemini API 일시 오류 대응)
            logger.warning("재생성 실패, 원본 답변 사용: %s", str(e)[:100])

    return draft_answer


def validate_answer_length(
    final_answer: str,
    normalized_qtype: str,
    ocr_text: str,
    query: str,
) -> None:
    """답변 길이 검증 및 경고 로깅.

    Args:
        final_answer: 최종 답변
        normalized_qtype: 정규화된 query type
        ocr_text: OCR 텍스트
        query: 질의
    """
    if normalized_qtype != "explanation":
        return

    answer_length = len(final_answer)
    min_chars = int(len(ocr_text) * 0.6)

    if answer_length < min_chars:
        logger.warning(
            "⚠️ Answer too short for explanation type: "
            "%d chars (expected %d+, OCR %d chars). "
            "Query: %s",
            answer_length,
            min_chars,
            len(ocr_text),
            query[:50],
        )
