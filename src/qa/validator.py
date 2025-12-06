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
        """모든 검증 규칙 적용."""
        violations: List[Dict[str, Any]] = []
        warnings: List[str] = []
        score = 1.0

        # 1) 동적 CSV 규칙 검증
        violations.extend(self.validate_sentence_count(answer))
        violations.extend(self.validate_temporal_expressions(answer))

        # 2) 패턴/포맷 위반 검사
        # Combine question and answer with space separator to avoid false positives
        combined_text = f"{question} {answer}" if question else answer
        pattern_violations = self.validate_forbidden_patterns(combined_text)
        format_violations = self.validate_formatting(answer)

        # [FIX] 타입 검증: 문자열이면 dict로 변환
        violations.extend(self._normalize_violations(pattern_violations))
        violations.extend(self._normalize_violations(format_violations))

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

        # 4) Neo4j 규칙 검증
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
                # Rule violations need special handling: add "rule" type for strings
                for v in rule_violations:
                    if isinstance(v, dict):
                        violations.append(v)
                    elif isinstance(v, str):
                        violations.append({"type": "rule", "description": v})
                    else:
                        # Handle unexpected types gracefully
                        violations.append({"type": "rule", "description": str(v)})

            except Exception as exc:  # noqa: BLE001
                warnings.append(f"규칙 검증 오류: {exc}")

        return ValidationResult(violations=violations, warnings=warnings, score=score)
