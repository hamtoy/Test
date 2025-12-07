"""Tests for constraint validation (Phase 3: IMPROVEMENTS.md)."""

import pytest

from src.qa.validator import validate_constraints


def test_validate_constraints_no_conflict() -> None:
    """Test when constraints don't conflict."""
    is_valid, message = validate_constraints(
        qtype="target",
        max_length=300,
        min_per_paragraph=50,
        num_paragraphs=5,
    )
    assert is_valid is True
    assert message == "제약 일관성 확인됨"


def test_validate_constraints_conflict() -> None:
    """Test when constraints conflict (total needed > max_length)."""
    is_valid, message = validate_constraints(
        qtype="reasoning",
        max_length=300,
        min_per_paragraph=80,
        num_paragraphs=5,
    )
    assert is_valid is False
    assert "충돌" in message
    assert "400" in message  # 80 * 5 = 400
    assert "300" in message


def test_validate_constraints_no_paragraph_requirements() -> None:
    """Test when paragraph requirements are not set."""
    is_valid, message = validate_constraints(
        qtype="target",
        max_length=100,
    )
    assert is_valid is True
    assert message == "제약 일관성 확인됨"


def test_validate_constraints_partial_requirements() -> None:
    """Test when only some paragraph requirements are set."""
    # Only min_per_paragraph set
    is_valid, message = validate_constraints(
        qtype="target",
        max_length=100,
        min_per_paragraph=50,
    )
    assert is_valid is True
    
    # Only num_paragraphs set
    is_valid, message = validate_constraints(
        qtype="target",
        max_length=100,
        num_paragraphs=3,
    )
    assert is_valid is True


def test_validate_constraints_edge_case_equal() -> None:
    """Test when total needed equals max_length (should be valid)."""
    is_valid, message = validate_constraints(
        qtype="explanation",
        max_length=400,
        min_per_paragraph=80,
        num_paragraphs=5,
    )
    assert is_valid is True  # 400 = 400, not greater than
