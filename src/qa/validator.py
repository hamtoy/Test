"""Unified validation utilities for generated answers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from scripts.validation.detect_forbidden_patterns import (
    find_formatting_violations,
    find_violations,
)
from src.validation.rule_parser import RuleCSVParser, RuleManager

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Aggregated validation output."""

    violations: list[dict[str, Any]]
    warnings: list[str]
    score: float = 1.0

    def has_errors(self) -> bool:
        """Check if any violations exist."""
        return bool(self.violations)

    def get_error_summary(self) -> str:
        """안전한 에러 요약 생성 (str/dict 모두 처리)."""
        if not self.violations:
            return ""

        # [FIX] violations가 str 또는 dict를 포함할 수 있음
        types = set()
        for v in self.violations:
            if isinstance(v, dict):
                types.add(v.get("type", "unknown"))
            elif isinstance(v, str):  # type: ignore[unreachable]
                types.add(v)
            else:
                types.add("unknown")

        return f"다음 사항 수정 필요: {', '.join(sorted(types))}"


class UnifiedValidator:
    """Run all available validators in one place."""

    def __init__(
        self,
        kg: Any | None = None,
        pipeline: Any | None = None,
        config_path: str = "data/neo4j",
    ) -> None:
        """Initialize UnifiedValidator.

        Args:
            kg: Neo4j 기반 규칙 시스템
            pipeline: 파이프라인 검증기
            config_path: 설정 파일 경로 (CSV 파일 경로)
        """
        self.kg = kg
        self.pipeline = pipeline

        # CSV 기반 규칙 로드
        parser = RuleCSVParser(
            guide_path=f"{config_path}/guide.csv",
            qna_path=f"{config_path}/qna.csv",
            patterns_path="config/patterns.yaml",
        )
        self.rule_manager = RuleManager(parser)
        self.rule_manager.load_rules()

    @staticmethod
    def _normalize_violations(
        violations: list[Any],
    ) -> list[dict[str, Any]]:
        """violations를 dict 형식으로 정규화 (str → dict 변환).

        String violations are converted to {"type": str_value, "description": str_value}.
        Other types are converted to {"type": "unknown", "description": str(value)}.
        """
        normalized = []
        for v in violations:
            if isinstance(v, dict):
                normalized.append(v)
            elif isinstance(v, str):
                normalized.append({"type": v, "description": v})
            else:
                # Handle unexpected types gracefully
                normalized.append({"type": "unknown", "description": str(v)})
        return normalized

    def validate_sentence_count(self, answer: str) -> list[dict[str, Any]]:
        """동적 규칙을 사용한 문장 수 검증."""
        sentence_rule = self.rule_manager.get_sentence_rules()

        if not sentence_rule:
            return []

        sentences = answer.split(".")
        count = len([s for s in sentences if s.strip()])

        min_val = sentence_rule.get("min") or 3
        max_val = sentence_rule.get("max") or 4

        violations: list[dict[str, Any]] = []
        if count < min_val or count > max_val:
            violations.append(
                {
                    "type": "sentence_count",
                    "message": f"문장 수: {count}개 (권장: {min_val}-{max_val})",
                    "severity": "warning",
                    "count": count,
                    "min": min_val,
                    "max": max_val,
                },
            )

        return violations

    def validate_temporal_expressions(self, _: str) -> list[dict[str, Any]]:
        """동적 규칙을 사용한 시의성 표현 검증.

        NOTE: 시의성 표현은 인간 작업자가 최종 수정하므로 비활성화됨.
        Phase 4 Complete: Gemini 생성 후 인간이 기준 시점 명시.
        """
        # 시의성 검증 비활성화 - 인간 작업자가 수동 수정 예정
        return []

    def validate_forbidden_patterns(self, text: str) -> list[dict[str, Any]]:
        """기존 패턴 검증."""
        violations: list[dict[str, Any]] = find_violations(text)
        return violations

    def validate_formatting(self, text: str) -> list[dict[str, Any]]:
        """기존 포맷팅 검증."""
        violations: list[dict[str, Any]] = find_formatting_violations(text)
        return violations

    def validate_all(
        self,
        answer: str,
        query_type: str,
        question: str = "",
    ) -> ValidationResult:
        """모든 검증 규칙 적용.

        검증 순서:
        1. CSV 기반 동적 규칙 (문장 수, 시의성 표현)
        2. 패턴/포맷 위반 (금지 패턴, 포맷팅)
        3. 파이프라인 검증
        4. Neo4j 규칙 검증 (CSV 규칙과 중복 제거)
        """
        violations: list[dict[str, Any]] = []
        warnings: list[str] = []
        score = 1.0

        violations.extend(self._collect_csv_violations(answer))
        violations.extend(self._collect_pattern_violations(answer, question))

        pipeline_violations, pipeline_warnings = self._collect_pipeline_violations(
            answer,
            query_type,
        )
        violations.extend(pipeline_violations)
        warnings.extend(pipeline_warnings)

        existing_types = {v.get("type") for v in violations if isinstance(v, dict)}
        neo4j_violations, rule_score, neo4j_warnings = self._collect_neo4j_violations(
            answer,
            query_type,
            existing_types,
        )
        if rule_score < 1.0:
            score = min(score, rule_score)
        violations.extend(neo4j_violations)
        warnings.extend(neo4j_warnings)

        return ValidationResult(violations=violations, warnings=warnings, score=score)

    def _collect_csv_violations(self, answer: str) -> list[dict[str, Any]]:
        sentence = self.validate_sentence_count(answer)
        temporal = self.validate_temporal_expressions(answer)
        if sentence or temporal:
            logger.debug(
                "CSV 규칙 검증: 문장 수 %d개, 시의성 표현 %d개",
                len(sentence),
                len(temporal),
            )
        return [*sentence, *temporal]

    def _collect_pattern_violations(
        self,
        answer: str,
        question: str,
    ) -> list[dict[str, Any]]:
        combined_text = f"{question} {answer}" if question else answer
        pattern_violations = self.validate_forbidden_patterns(combined_text)
        format_violations = self.validate_formatting(answer)
        if pattern_violations or format_violations:
            logger.debug(
                "패턴 검증: 금지 패턴 %d개, 포맷팅 %d개",
                len(pattern_violations),
                len(format_violations),
            )
        return [
            *self._normalize_violations(pattern_violations),
            *self._normalize_violations(format_violations),
        ]

    def _collect_pipeline_violations(
        self,
        answer: str,
        query_type: str,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        if not self.pipeline:
            return [], []
        try:
            validation = self.pipeline.validate_output(query_type, answer)
            pipeline_violations = validation.get("violations", [])
            violations = self._normalize_violations(pipeline_violations)
            warnings: list[str] = []
            if not validation.get("valid", True):
                warnings.append("파이프라인 검증 실패")
            return violations, warnings
        except Exception as exc:  # noqa: BLE001
            return [], [f"파이프라인 검증 오류: {exc}"]

    def _collect_neo4j_violations(
        self,
        answer: str,
        query_type: str,
        existing_types: set[str],
    ) -> tuple[list[dict[str, Any]], float, list[str]]:
        if not self.kg:
            return [], 1.0, []
        try:
            from src.analysis.cross_validation import CrossValidationSystem

            validator = CrossValidationSystem(self.kg)
            rule_check = validator._check_rule_compliance(  # noqa: SLF001
                answer,
                query_type,
            )
        except Exception as exc:  # noqa: BLE001
            return [], 1.0, [f"규칙 검증 오류: {exc}"]

        rule_score = float(rule_check.get("score", 1.0))
        rule_violations = rule_check.get("violations", [])
        added: list[dict[str, Any]] = []

        for v in rule_violations:
            if isinstance(v, dict):
                normalized_v = v
            elif isinstance(v, str):
                normalized_v = {"type": "rule", "description": v}
            else:
                normalized_v = {"type": "rule", "description": str(v)}

            v_type = normalized_v.get("type", "")
            if v_type not in existing_types:
                added.append(normalized_v)

        if added:
            logger.debug("Neo4j 규칙 검증: %d개 추가 (중복 제외)", len(added))

        return added, rule_score, []


def validate_constraints(
    qtype: str,
    max_length: int | None = None,
    min_per_paragraph: int | None = None,
    num_paragraphs: int | None = None,
) -> tuple[bool, str]:
    """제약 충돌 감지 (EMNLP 2025 기법).

    Phase 3: IMPROVEMENTS.md - Length constraint conflict detection

    Args:
        qtype: Query type (target, reasoning, explanation, etc.)
        max_length: Maximum word count constraint
        min_per_paragraph: Minimum words per paragraph
        num_paragraphs: Number of paragraphs required

    Returns:
        Tuple of (is_valid, message)
        - (True, "제약 일관성 확인됨") if no conflicts
        - (False, error_message) if conflicts detected
    """
    _ = qtype  # keep signature compatibility; currently unused

    if min_per_paragraph and num_paragraphs and max_length:
        total_needed = min_per_paragraph * num_paragraphs
        if total_needed > max_length:
            return (
                False,
                f"충돌: {total_needed}단어 필요하나 {max_length}단어 제한",
            )

    return (True, "제약 일관성 확인됨")
