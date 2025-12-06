"""Tests for QA validator module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.qa.validator import UnifiedValidator, ValidationResult


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_validation_result_creation(self) -> None:
        """Test creating ValidationResult with default values."""
        result = ValidationResult(violations=[], warnings=[])
        assert result.violations == []
        assert result.warnings == []
        assert result.score == 1.0

    def test_validation_result_with_violations(self) -> None:
        """Test ValidationResult with violations."""
        violations = [{"type": "pattern", "description": "Forbidden pattern"}]
        warnings = ["Warning 1"]
        result = ValidationResult(violations=violations, warnings=warnings, score=0.8)
        assert result.violations == violations
        assert result.warnings == warnings
        assert result.score == 0.8

    def test_has_errors_with_violations(self) -> None:
        """Test has_errors returns True when violations exist."""
        result = ValidationResult(violations=[{"type": "test"}], warnings=[], score=1.0)
        assert result.has_errors() is True

    def test_has_errors_without_violations(self) -> None:
        """Test has_errors returns False when no violations."""
        result = ValidationResult(violations=[], warnings=[], score=1.0)
        assert result.has_errors() is False

    def test_get_error_summary_empty(self) -> None:
        """Test get_error_summary returns empty string when no violations."""
        result = ValidationResult(violations=[], warnings=[], score=1.0)
        assert result.get_error_summary() == ""

    def test_get_error_summary_single_violation(self) -> None:
        """Test get_error_summary with single violation type."""
        result = ValidationResult(
            violations=[{"type": "pattern"}], warnings=[], score=1.0
        )
        summary = result.get_error_summary()
        assert "pattern" in summary
        assert "다음 사항 수정 필요" in summary

    def test_get_error_summary_multiple_violations(self) -> None:
        """Test get_error_summary with multiple violation types."""
        result = ValidationResult(
            violations=[
                {"type": "pattern"},
                {"type": "format"},
                {"type": "pattern"},  # Duplicate type
            ],
            warnings=[],
            score=1.0,
        )
        summary = result.get_error_summary()
        assert "pattern" in summary
        assert "format" in summary
        # Should deduplicate types
        assert summary.count("pattern") == 1

    def test_get_error_summary_unknown_type(self) -> None:
        """Test get_error_summary handles missing type field."""
        result = ValidationResult(
            violations=[{"description": "No type field"}], warnings=[], score=1.0
        )
        summary = result.get_error_summary()
        assert "unknown" in summary


class TestUnifiedValidator:
    """Test UnifiedValidator class."""

    def test_unified_validator_init_no_dependencies(self) -> None:
        """Test UnifiedValidator initialization without dependencies."""
        validator = UnifiedValidator()
        assert validator.kg is None
        assert validator.pipeline is None

    def test_unified_validator_init_with_kg(self) -> None:
        """Test UnifiedValidator initialization with KG."""
        mock_kg = Mock()
        validator = UnifiedValidator(kg=mock_kg)
        assert validator.kg is mock_kg
        assert validator.pipeline is None

    def test_unified_validator_init_with_pipeline(self) -> None:
        """Test UnifiedValidator initialization with pipeline."""
        mock_pipeline = Mock()
        validator = UnifiedValidator(pipeline=mock_pipeline)
        assert validator.kg is None
        assert validator.pipeline is mock_pipeline

    def test_unified_validator_init_with_both(self) -> None:
        """Test UnifiedValidator initialization with both dependencies."""
        mock_kg = Mock()
        mock_pipeline = Mock()
        validator = UnifiedValidator(kg=mock_kg, pipeline=mock_pipeline)
        assert validator.kg is mock_kg
        assert validator.pipeline is mock_pipeline

    @patch("src.qa.validator.find_violations")
    @patch("src.qa.validator.find_formatting_violations")
    def test_validate_all_no_violations(
        self, mock_format_violations: Mock, mock_violations: Mock
    ) -> None:
        """Test validate_all with no violations detected."""
        mock_violations.return_value = []
        mock_format_violations.return_value = []

        validator = UnifiedValidator()
        result = validator.validate_all("Clean answer", "explanation")

        assert result.violations == []
        assert result.warnings == []
        assert result.score == 1.0
        mock_violations.assert_called_once_with("Clean answer")
        mock_format_violations.assert_called_once_with("Clean answer")

    @patch("src.qa.validator.find_violations")
    @patch("src.qa.validator.find_formatting_violations")
    def test_validate_all_with_pattern_violations(
        self, mock_format_violations: Mock, mock_violations: Mock
    ) -> None:
        """Test validate_all with pattern violations."""
        pattern_violation = {"type": "pattern", "description": "Bullet point found"}
        mock_violations.return_value = [pattern_violation]
        mock_format_violations.return_value = []

        validator = UnifiedValidator()
        result = validator.validate_all("- Answer with bullet", "explanation")

        assert pattern_violation in result.violations
        assert result.has_errors() is True

    @patch("src.qa.validator.find_violations")
    @patch("src.qa.validator.find_formatting_violations")
    def test_validate_all_with_formatting_violations(
        self, mock_format_violations: Mock, mock_violations: Mock
    ) -> None:
        """Test validate_all with formatting violations."""
        format_violation = {"type": "format", "description": "Bold text found"}
        mock_violations.return_value = []
        mock_format_violations.return_value = [format_violation]

        validator = UnifiedValidator()
        result = validator.validate_all("**Bold** text", "explanation")

        assert format_violation in result.violations

    @patch("src.qa.validator.find_violations")
    @patch("src.qa.validator.find_formatting_violations")
    def test_validate_all_with_pipeline_success(
        self, mock_format_violations: Mock, mock_violations: Mock
    ) -> None:
        """Test validate_all with successful pipeline validation."""
        mock_violations.return_value = []
        mock_format_violations.return_value = []

        mock_pipeline = Mock()
        mock_pipeline.validate_output.return_value = {
            "valid": True,
            "violations": [],
        }

        validator = UnifiedValidator(pipeline=mock_pipeline)
        result = validator.validate_all("Valid answer", "explanation")

        assert result.violations == []
        assert result.warnings == []
        mock_pipeline.validate_output.assert_called_once_with(
            "explanation", "Valid answer"
        )

    @patch("src.qa.validator.find_violations")
    @patch("src.qa.validator.find_formatting_violations")
    def test_validate_all_with_pipeline_violations(
        self, mock_format_violations: Mock, mock_violations: Mock
    ) -> None:
        """Test validate_all with pipeline validation violations."""
        mock_violations.return_value = []
        mock_format_violations.return_value = []

        pipeline_violation = {"type": "template", "description": "Template mismatch"}
        mock_pipeline = Mock()
        mock_pipeline.validate_output.return_value = {
            "valid": False,
            "violations": [pipeline_violation],
        }

        validator = UnifiedValidator(pipeline=mock_pipeline)
        result = validator.validate_all("Invalid answer", "explanation")

        assert pipeline_violation in result.violations
        assert "파이프라인 검증 실패" in result.warnings

    @patch("src.qa.validator.find_violations")
    @patch("src.qa.validator.find_formatting_violations")
    def test_validate_all_pipeline_exception(
        self, mock_format_violations: Mock, mock_violations: Mock
    ) -> None:
        """Test validate_all handles pipeline exceptions gracefully."""
        mock_violations.return_value = []
        mock_format_violations.return_value = []

        mock_pipeline = Mock()
        mock_pipeline.validate_output.side_effect = RuntimeError("Pipeline error")

        validator = UnifiedValidator(pipeline=mock_pipeline)
        result = validator.validate_all("Test answer", "explanation")

        assert len(result.warnings) == 1
        assert "파이프라인 검증 오류" in result.warnings[0]
        assert "Pipeline error" in result.warnings[0]

    @patch("src.qa.validator.find_violations")
    @patch("src.qa.validator.find_formatting_violations")
    def test_validate_all_with_kg_success(
        self, mock_format_violations: Mock, mock_violations: Mock
    ) -> None:
        """Test validate_all with successful KG validation."""
        mock_violations.return_value = []
        mock_format_violations.return_value = []

        mock_kg = Mock()

        with patch("src.analysis.cross_validation.CrossValidationSystem") as mock_cvs:
            mock_validator_instance = Mock()
            mock_validator_instance._check_rule_compliance.return_value = {
                "score": 1.0,
                "violations": [],
            }
            mock_cvs.return_value = mock_validator_instance

            validator = UnifiedValidator(kg=mock_kg)
            result = validator.validate_all("Valid answer", "explanation")

            assert result.score == 1.0
            assert result.violations == []
            mock_cvs.assert_called_once_with(mock_kg)

    @patch("src.qa.validator.find_violations")
    @patch("src.qa.validator.find_formatting_violations")
    def test_validate_all_with_kg_rule_violations(
        self, mock_format_violations: Mock, mock_violations: Mock
    ) -> None:
        """Test validate_all with KG rule violations."""
        mock_violations.return_value = []
        mock_format_violations.return_value = []

        mock_kg = Mock()

        with patch("src.analysis.cross_validation.CrossValidationSystem") as mock_cvs:
            mock_validator_instance = Mock()
            mock_validator_instance._check_rule_compliance.return_value = {
                "score": 0.7,
                "violations": ["Rule violation 1", "Rule violation 2"],
            }
            mock_cvs.return_value = mock_validator_instance

            validator = UnifiedValidator(kg=mock_kg)
            result = validator.validate_all("Invalid answer", "explanation")

            assert result.score == 0.7
            assert len(result.violations) == 2
            assert result.violations[0]["type"] == "rule"
            assert result.violations[0]["description"] == "Rule violation 1"
            assert result.violations[1]["description"] == "Rule violation 2"

    @patch("src.qa.validator.find_violations")
    @patch("src.qa.validator.find_formatting_violations")
    def test_validate_all_kg_exception(
        self, mock_format_violations: Mock, mock_violations: Mock
    ) -> None:
        """Test validate_all handles KG validation exceptions gracefully."""
        mock_violations.return_value = []
        mock_format_violations.return_value = []

        mock_kg = Mock()

        with patch("src.analysis.cross_validation.CrossValidationSystem") as mock_cvs:
            mock_cvs.side_effect = RuntimeError("KG error")

            validator = UnifiedValidator(kg=mock_kg)
            result = validator.validate_all("Test answer", "explanation")

            assert len(result.warnings) == 1
            assert "규칙 검증 오류" in result.warnings[0]
            assert "KG error" in result.warnings[0]
