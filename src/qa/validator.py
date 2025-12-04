"""Unified validation utilities for generated answers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from checks.detect_forbidden_patterns import (
    find_formatting_violations,
    find_violations,
)


@dataclass
class ValidationResult:
    """Aggregated validation output."""

    violations: List[Dict[str, Any]]
    warnings: List[str]
    score: float = 1.0

    def has_errors(self) -> bool:
        return bool(self.violations)

    def get_error_summary(self) -> str:
        if not self.violations:
            return ""
        types = {v.get("type", "unknown") for v in self.violations}
        return f"다음 사항 수정 필요: {', '.join(sorted(types))}"


class UnifiedValidator:
    """Run all available validators in one place."""

    def __init__(
        self,
        kg: Optional[Any] = None,
        pipeline: Optional[Any] = None,
    ) -> None:
        self.kg = kg
        self.pipeline = pipeline

    def validate_all(self, answer: str, query_type: str) -> ValidationResult:
        violations: List[Dict[str, Any]] = []
        warnings: List[str] = []
        score = 1.0

        # 1) 패턴/포맷 위반 검사
        violations.extend(find_violations(answer))
        violations.extend(find_formatting_violations(answer))

        # 2) 파이프라인 검증 (Neo4j/템플릿 기반)
        if self.pipeline:
            try:
                validation = self.pipeline.validate_output(query_type, answer)
                violations.extend(validation.get("violations", []))
                if not validation.get("valid", True):
                    warnings.append("파이프라인 검증 실패")
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"파이프라인 검증 오류: {exc}")

        # 3) Neo4j 규칙 검증
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
                # _check_rule_compliance returns list of strings in violations, wrap as dicts
                violations.extend(
                    [{"type": "rule", "description": v} for v in rule_violations]
                )
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"규칙 검증 오류: {exc}")

        return ValidationResult(violations=violations, warnings=warnings, score=score)
