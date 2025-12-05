"""Tests for QA graph validators module."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock, patch

import pytest

from src.qa.graph.validators import validate_session_structure


class TestValidateSessionStructure:
    """Test validate_session_structure function."""

    def test_validate_session_structure_empty_turns(self) -> None:
        """Test validation with empty turns."""
        session = {"turns": []}

        result = validate_session_structure(session)

        assert result["ok"] is False
        assert "비어있습니다" in result["issues"][0]

    def test_validate_session_structure_missing_turns(self) -> None:
        """Test validation with missing turns key."""
        session: dict[str, Any] = {}

        result = validate_session_structure(session)

        assert result["ok"] is False
        assert len(result["issues"]) > 0

    @patch("scripts.build_session.SessionContext")
    @patch("src.qa.graph.validators.validate_turns")
    def test_validate_session_structure_success(
        self, mock_validate_turns: Mock, mock_session_context: Mock
    ) -> None:
        """Test successful session validation."""
        session = {
            "turns": [{"query": "test query", "answer": "test answer"}],
            "context": {"user_id": "test_user"},
        }

        mock_context_instance = Mock()
        mock_session_context.return_value = mock_context_instance
        mock_validate_turns.return_value = {"ok": True, "issues": []}

        result = validate_session_structure(session)

        assert result["ok"] is True
        assert result["issues"] == []
        mock_session_context.assert_called_once_with(user_id="test_user")
        mock_validate_turns.assert_called_once()

    @patch("scripts.build_session.SessionContext")
    def test_validate_session_structure_context_creation_error(
        self, mock_session_context: Mock
    ) -> None:
        """Test validation when context creation fails."""
        session = {
            "turns": [{"query": "test"}],
            "context": {"invalid_field": "value"},
        }

        mock_session_context.side_effect = TypeError("Invalid context")

        result = validate_session_structure(session)

        assert result["ok"] is False
        assert "컨텍스트 생성 실패" in result["issues"][0]
        assert "Invalid context" in result["issues"][0]

    @patch("scripts.build_session.SessionContext")
    def test_validate_session_structure_context_value_error(
        self, mock_session_context: Mock
    ) -> None:
        """Test validation when context raises ValueError."""
        session = {
            "turns": [{"query": "test"}],
            "context": {"bad_value": -1},
        }

        mock_session_context.side_effect = ValueError("Bad value")

        result = validate_session_structure(session)

        assert result["ok"] is False
        assert "컨텍스트 생성 실패" in result["issues"][0]

    @patch("scripts.build_session.SessionContext")
    @patch("src.qa.graph.validators.validate_turns")
    def test_validate_session_structure_validation_error(
        self, mock_validate_turns: Mock, mock_session_context: Mock
    ) -> None:
        """Test validation when turn validation fails."""
        session = {
            "turns": [{"query": "test"}],
            "context": {},
        }

        mock_context_instance = Mock()
        mock_session_context.return_value = mock_context_instance
        mock_validate_turns.side_effect = AttributeError("Validation failed")

        result = validate_session_structure(session)

        assert result["ok"] is False
        assert "컨텍스트 검증 실패" in result["issues"][0]

    @patch("scripts.build_session.SessionContext")
    @patch("src.qa.graph.validators.validate_turns")
    def test_validate_session_structure_runtime_error(
        self, mock_validate_turns: Mock, mock_session_context: Mock
    ) -> None:
        """Test validation when runtime error occurs."""
        session = {
            "turns": [{"query": "test"}],
            "context": {},
        }

        mock_context_instance = Mock()
        mock_session_context.return_value = mock_context_instance
        mock_validate_turns.side_effect = RuntimeError("Runtime error")

        result = validate_session_structure(session)

        assert result["ok"] is False
        assert "컨텍스트 검증 실패" in result["issues"][0]
