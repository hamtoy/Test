"""Unified validation utilities for generated answers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from checks.detect_forbidden_patterns import (
    find_formatting_violations,
    find_violations,
)
from src.validation.rule_parser import RuleCSVParser, RuleManager

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Aggregated validation output."""

    violations: List[Dict[str, Any]]
    warnings: List[str]
    score: float = 1.0

    def has_errors(self) -> bool:
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
        kg: Optional[Any] = None,
        pipeline: Optional[Any] = None,
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
        violations: List[Any],
    ) -> List[Dict[str, Any]]:
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

    def validate_sentence_count(self, answer: str) -> List[Dict[str, Any]]:
        """동적 규칙을 사용한 문장 수 검증."""
        sentence_rule = self.rule_manager.get_sentence_rules()

        if not sentence_rule:
            return []

        sentences = answer.split(".")
        count = len([s for s in sentences if s.strip()])

        min_val = sentence_rule.get("min", 3)
        max_val = sentence_rule.get("max", 4)

        violations: List[Dict[str, Any]] = []
        if count < min_val or count > max_val:
            violations.append(
                {
                    "type": "sentence_count",
                    "message": f"문장 수: {count}개 (권장: {min_val}-{max_val})",
                    "severity": "warning",
                    "count": count,
                    "min": min_val,
                    "max": max_val,
                }
            )

        return violations

    def validate_temporal_expressions(self, text: str) -> List[Dict[str, Any]]:
        """동적 규칙을 사용한 시의성 표현 검증."""
        temporal_rules = self.rule_manager.get_temporal_rules()
        violations: List[Dict[str, Any]] = [
            {
                "type": "temporal_expression_found",
                "expression": expression,
                "message": f'시의성 표현 발견: "{expression}"',
                "severity": "info",
            }
            for expression in temporal_rules
            if expression in text
        ]

        return violations

    def validate_forbidden_patterns(self, text: str) -> List[Dict[str, Any]]:
        """기존 패턴 검증."""
        return find_violations(text)

    def validate_formatting(self, text: str) -> List[Dict[str, Any]]:
        """기존 포맷팅 검증."""
        return find_formatting_violations(text)

    def validate_all(
        self, answer: str, query_type: str, question: str = ""
    ) -> ValidationResult:
        """모든 검증 규칙 적용.

        검증 순서:
        1. CSV 기반 동적 규칙 (문장 수, 시의성 표현)
        2. 패턴/포맷 위반 (금지 패턴, 포맷팅)
        3. 파이프라인 검증
        4. Neo4j 규칙 검증 (CSV 규칙과 중복 제거)
        """
        violations: List[Dict[str, Any]] = []
        warnings: List[str] = []
        score = 1.0

        # 1) 동적 CSV 규칙 검증 (우선순위: 높음)
        csv_violations_sentence = self.validate_sentence_count(answer)
        csv_violations_temporal = self.validate_temporal_expressions(answer)
        violations.extend(csv_violations_sentence)
        violations.extend(csv_violations_temporal)

        if csv_violations_sentence or csv_violations_temporal:
            logger.debug(
                "CSV 규칙 검증: 문장 수 %d개, 시의성 표현 %d개",
                len(csv_violations_sentence),
                len(csv_violations_temporal),
            )

        # 2) 패턴/포맷 위반 검사 (우선순위: 높음)
        # Combine question and answer with space separator to avoid false positives
        combined_text = f"{question} {answer}" if question else answer
        pattern_violations = self.validate_forbidden_patterns(combined_text)
        format_violations = self.validate_formatting(answer)

        # [FIX] 타입 검증: 문자열이면 dict로 변환
        violations.extend(self._normalize_violations(pattern_violations))
        violations.extend(self._normalize_violations(format_violations))

        if pattern_violations or format_violations:
            logger.debug(
                "패턴 검증: 금지 패턴 %d개, 포맷팅 %d개",
                len(pattern_violations),
                len(format_violations),
            )

        # 3) 파이프라인 검증
        if self.pipeline:
            try:
                validation = self.pipeline.validate_output(query_type, answer)
                pipeline_violations = validation.get("violations", [])

                violations.extend(self._normalize_violations(pipeline_violations))

                if not validation.get("valid", True):
                    warnings.append("파이프라인 검증 실패")
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"파이프라인 검증 오류: {exc}")

        # 4) Neo4j 규칙 검증 (우선순위: 낮음, CSV 규칙과 중복 시 제외)
        if self.kg:
            try:
                from src.analysis.cross_validation import CrossValidationSystem

                validator = CrossValidationSystem(self.kg)
                rule_check = validator._check_rule_compliance(  # noqa: SLF001
                    answer, query_type
                )
                rule_score = rule_check.get("score", 1.0)
                if rule_score < 1.0:
                    score = min(score, rule_score)

                rule_violations = rule_check.get("violations", [])

                # Track existing violation types from CSV rules to avoid duplicates
                existing_types = {
                    v.get("type") for v in violations if isinstance(v, dict)
                }

                # Rule violations need special handling: add "rule" type for strings
                neo4j_added = 0
                for v in rule_violations:
                    normalized_v: Dict[str, Any]
                    if isinstance(v, dict):
                        normalized_v = v
                    elif isinstance(v, str):
                        normalized_v = {"type": "rule", "description": v}
                    else:
                        # Handle unexpected types gracefully
                        normalized_v = {"type": "rule", "description": str(v)}

                    # Only add Neo4j rule if not already detected by CSV rules
                    v_type = normalized_v.get("type", "")
                    if v_type not in existing_types:
                        violations.append(normalized_v)
                        neo4j_added += 1

                if neo4j_added > 0:
                    logger.debug(
                        "Neo4j 규칙 검증: %d개 추가 (중복 제외)",
                        neo4j_added,
                    )

            except Exception as exc:  # noqa: BLE001
                warnings.append(f"규칙 검증 오류: {exc}")

        return ValidationResult(violations=violations, warnings=warnings, score=score)


def validate_constraints(
    qtype: str,
    max_length: Optional[int] = None,
    min_per_paragraph: Optional[int] = None,
    num_paragraphs: Optional[int] = None,
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
    if min_per_paragraph and num_paragraphs and max_length:
        total_needed = min_per_paragraph * num_paragraphs
        if total_needed > max_length:
            return (
                False,
                f"충돌: {total_needed}단어 필요하나 {max_length}단어 제한",
            )
    
    return (True, "제약 일관성 확인됨")

