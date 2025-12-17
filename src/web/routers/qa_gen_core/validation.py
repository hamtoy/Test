"""검증 및 재생성 로직."""

from __future__ import annotations

import logging
from typing import Any, cast

from checks.detect_forbidden_patterns import (
    find_formatting_violations,
    find_violations,
)
from src.web.utils import strip_prose_bold

logger = logging.getLogger(__name__)


def _count_sentences(text: str) -> int:
    sentences = [
        s for s in text.replace("?", ".").replace("!", ".").split(".") if s.strip()
    ]
    return len(sentences)


def _collect_sentence_issues(draft_answer: str, qtype: str) -> list[str]:
    if qtype != "target_short":
        return []
    sentence_count = _count_sentences(draft_answer)
    if sentence_count > 2:
        return [f"1-2문장으로 축소 필요 (현재 {sentence_count}문장)"]
    return []


def _collect_summary_header_violations(
    draft_answer: str,
    normalized_qtype: str,
) -> list[str]:
    if normalized_qtype != "reasoning":
        return []
    first_line = draft_answer.splitlines()[0] if draft_answer.splitlines() else ""
    if "요약문" in draft_answer or "요약" in first_line:
        return ["summary_header_not_allowed"]
    return []


def _collect_kg_rule_violations(
    draft_answer: str,
    normalized_qtype: str,
    kg_wrapper: Any,
    validator_class: type | None,
) -> list[str]:
    if kg_wrapper is None or validator_class is None:
        return []
    try:
        validator = validator_class(kg_wrapper)
        rule_check = validator._check_rule_compliance(
            draft_answer,
            normalized_qtype,
        )
        score = rule_check.get("score")
        score_val = score if isinstance(score, (int, float)) else 1.0
        violations = rule_check.get("violations", [])
        if violations and score_val < 0.3:
            return list(violations)
    except Exception:
        return []
    return []


def _collect_pattern_violations(draft_answer: str) -> list[str]:
    violations = find_violations(draft_answer)
    if not violations:
        return []

    collected: list[str] = []
    for v in violations:
        v_type = v.get("type", "")
        if v_type.startswith("error_pattern:시의성"):
            continue
        if "temporal" in v_type.lower():
            continue
        collected.append(v_type)
    return collected


def _collect_formatting_violations(draft_answer: str) -> list[str]:
    """서식 위반 수집. prose_bold_violation은 별도 처리 필요."""
    formatting_violations = find_formatting_violations(draft_answer)
    collected: list[str] = []
    for fv in formatting_violations:
        if fv.get("severity") == "error":
            collected.append(fv.get("type", "formatting"))
            logger.warning(
                "서식 위반 감지: %s - '%s'",
                fv.get("description", ""),
                fv.get("match", ""),
            )
    return collected


def _collect_pipeline_violations(
    pipeline: Any,
    normalized_qtype: str,
    draft_answer: str,
) -> list[str]:
    if pipeline is None:
        return []
    validation = pipeline.validate_output(
        normalized_qtype,
        draft_answer,
    )
    collected: list[str] = []
    if not validation.get("valid", True):
        collected.extend(validation.get("violations", []))
    missing_rules = validation.get("missing_rules_hint", [])
    if missing_rules:
        logger.debug("누락 가능성 있는 규칙: %s", missing_rules)
    return collected


def _merge_unified_validator_results(val_result: Any) -> tuple[list[str], list[str]]:
    violations: list[str] = []
    warnings: list[str] = []
    if val_result.has_errors():
        violations.extend([v.get("type", "rule") for v in val_result.violations])
    if val_result.warnings:
        warnings.extend(val_result.warnings)
    return violations, warnings


def _filter_temporal_violations(violations: list[str]) -> list[str]:
    return [v for v in violations if "시의성" not in v and "temporal" not in v.lower()]


async def _try_rewrite_answer(
    agent: Any,
    draft_answer: str,
    ocr_text: str,
    issues: list[str],
    answer_constraints: list[dict[str, Any]],
    length_constraint: str,
) -> str | None:
    combined_request = "; ".join(issues[:2])  # 최대 2개 이슈만 처리
    logger.warning("검증 실패, 재생성 시도: %s", combined_request)
    try:
        rewritten = cast(
            str | None,
            await agent.rewrite_best_answer(
                ocr_text=ocr_text,
                best_answer=draft_answer,
                edit_request=f"다음 사항 수정: {combined_request}",
                cached_content=None,
                constraints=answer_constraints,
                length_constraint=length_constraint,
            ),
        )
        if rewritten and rewritten.strip():
            return rewritten
        logger.warning("재생성 빈 응답, 원본 답변 사용")
    except Exception as exc:  # noqa: BLE001
        logger.warning("재생성 실패, 원본 답변 사용: %s", str(exc)[:100])
    return None


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
    # 1. 먼저 prose_bold_violation 빠르게 검사 및 즉시 수정 (API 호출 없이)
    formatting_viols = _collect_formatting_violations(draft_answer)
    has_prose_bold = any("prose_bold" in v for v in formatting_viols)

    if has_prose_bold:
        logger.info("prose_bold_violation 감지 - strip_prose_bold로 즉시 수정")
        draft_answer = strip_prose_bold(draft_answer)
        # 수정 후 formatting 위반만 다시 검사
        formatting_viols = _collect_formatting_violations(draft_answer)
        has_prose_bold = any("prose_bold" in v for v in formatting_viols)
        if not has_prose_bold:
            logger.info("prose_bold_violation 수정 완료")

    # 2. 통합 검증으로 수집할 위반/경고 (질의 포함하여 금지 패턴 검증 강화)
    val_result = unified_validator.validate_all(
        draft_answer,
        normalized_qtype,
        query,
    )
    all_issues: list[str] = []
    all_violations: list[str] = []

    all_issues.extend(_collect_sentence_issues(draft_answer, qtype))
    all_violations.extend(
        _collect_summary_header_violations(draft_answer, normalized_qtype),
    )
    all_violations.extend(
        _collect_kg_rule_violations(
            draft_answer,
            normalized_qtype,
            kg_wrapper,
            validator_class,
        ),
    )
    all_violations.extend(_collect_pattern_violations(draft_answer))
    # prose_bold가 이미 수정됐으면 formatting_viols에서 제외됨
    all_violations.extend(formatting_viols)
    all_violations.extend(
        _collect_pipeline_violations(pipeline, normalized_qtype, draft_answer),
    )

    unified_violations, unified_warnings = _merge_unified_validator_results(val_result)
    all_violations.extend(unified_violations)
    all_issues.extend(unified_warnings)

    all_violations = _filter_temporal_violations(all_violations)
    if all_violations:
        all_issues.extend(all_violations[:3])

    if all_issues:
        rewritten = await _try_rewrite_answer(
            agent,
            draft_answer,
            ocr_text,
            all_issues,
            answer_constraints,
            length_constraint,
        )
        if rewritten is not None:
            return rewritten

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
