"""Tests for constraint validation in QA generation."""

from __future__ import annotations

from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from src.web.routers.qa_common import _CachedKG


class TestConstraintValidation:
    """Tests for constraint validation to prevent 'str' object errors."""

    def test_cached_kg_handles_string_constraints(self) -> None:
        """Test that _CachedKG handles invalid string constraints gracefully."""
        mock_kg = MagicMock()
        # Simulate KG returning a string instead of a list
        mock_kg.get_constraints_for_query_type = MagicMock(return_value="error string")
        
        cached_kg = _CachedKG(mock_kg)
        result = cached_kg.get_constraints_for_query_type("explanation")
        
        # Should return empty list instead of string
        assert isinstance(result, list)
        assert result == []

    def test_cached_kg_handles_valid_constraints(self) -> None:
        """Test that _CachedKG preserves valid constraint lists."""
        mock_kg = MagicMock()
        valid_constraints = [
            {"category": "query", "description": "test constraint"},
            {"category": "answer", "description": "another constraint"},
        ]
        mock_kg.get_constraints_for_query_type = MagicMock(return_value=valid_constraints)
        
        cached_kg = _CachedKG(mock_kg)
        result = cached_kg.get_constraints_for_query_type("explanation")
        
        # Should return the valid list as-is
        assert isinstance(result, list)
        assert result == valid_constraints

    def test_cached_kg_handles_string_formatting_rules(self) -> None:
        """Test that _CachedKG handles invalid string formatting rules gracefully."""
        mock_kg = MagicMock()
        # Simulate KG returning a string instead of a list
        mock_kg.get_formatting_rules_for_query_type = MagicMock(return_value="error string")
        
        cached_kg = _CachedKG(mock_kg)
        result = cached_kg.get_formatting_rules_for_query_type("explanation")
        
        # Should return empty list instead of string
        assert isinstance(result, list)
        assert result == []

    def test_cached_kg_handles_valid_formatting_rules(self) -> None:
        """Test that _CachedKG preserves valid formatting rule lists."""
        mock_kg = MagicMock()
        valid_rules = [
            {"description": "formatting rule 1", "priority": 1},
            {"description": "formatting rule 2", "priority": 2},
        ]
        mock_kg.get_formatting_rules_for_query_type = MagicMock(return_value=valid_rules)
        
        cached_kg = _CachedKG(mock_kg)
        result = cached_kg.get_formatting_rules_for_query_type("explanation")
        
        # Should return the valid list as-is
        assert isinstance(result, list)
        assert result == valid_rules

    def test_cached_kg_caches_validated_data(self) -> None:
        """Test that validated data is cached properly."""
        mock_kg = MagicMock()
        # First call returns invalid data, but we fix it
        mock_kg.get_constraints_for_query_type = MagicMock(return_value="error")
        
        cached_kg = _CachedKG(mock_kg)
        
        # First call
        result1 = cached_kg.get_constraints_for_query_type("explanation")
        # Second call should use cache
        result2 = cached_kg.get_constraints_for_query_type("explanation")
        
        # Should only call the base KG once
        assert mock_kg.get_constraints_for_query_type.call_count == 1
        # Both results should be the corrected empty list
        assert result1 == []
        assert result2 == []


@pytest.mark.asyncio
class TestGenerateSingleQAConstraintHandling:
    """Tests for generate_single_qa with constraint validation."""

    async def test_generate_qa_handles_string_constraints_from_kg(self) -> None:
        """Test that generate_single_qa handles invalid string constraints."""
        from src.web.routers.qa_generation import generate_single_qa
        
        # Create mock KG that returns string instead of list
        mock_kg = MagicMock()
        mock_kg.get_constraints_for_query_type = MagicMock(return_value="invalid string")
        mock_kg.get_formatting_rules_for_query_type = MagicMock(return_value=[])
        
        cached_kg = _CachedKG(mock_kg)
        
        # Mock agent
        mock_agent = MagicMock()
        mock_agent.generate_query = AsyncMock(return_value=["test query"])
        mock_agent.rewrite_best_answer = AsyncMock(return_value="test answer")
        
        with (
            patch("src.web.routers.qa_generation.get_cached_kg", return_value=cached_kg),
            patch("src.web.routers.qa_generation._get_kg", return_value=mock_kg),
            patch("src.web.routers.qa_generation._get_pipeline", return_value=None),
            patch("src.web.routers.qa_generation._get_validator_class", return_value=MagicMock),
        ):
            # This should not raise an error
            result = await generate_single_qa(
                mock_agent,
                "OCR text sample",
                "explanation"
            )
            
            # Should return a valid result
            assert isinstance(result, dict)
            assert "query" in result
            assert "answer" in result

    async def test_generate_qa_handles_string_formatting_rules_from_kg(self) -> None:
        """Test that generate_single_qa handles invalid string formatting rules."""
        from src.web.routers.qa_generation import generate_single_qa
        
        # Create mock KG that returns string for formatting rules
        mock_kg = MagicMock()
        mock_kg.get_constraints_for_query_type = MagicMock(return_value=[])
        mock_kg.get_formatting_rules_for_query_type = MagicMock(return_value="invalid string")
        
        cached_kg = _CachedKG(mock_kg)
        
        # Mock agent
        mock_agent = MagicMock()
        mock_agent.generate_query = AsyncMock(return_value=["test query"])
        mock_agent.rewrite_best_answer = AsyncMock(return_value="test answer")
        
        with (
            patch("src.web.routers.qa_generation.get_cached_kg", return_value=cached_kg),
            patch("src.web.routers.qa_generation._get_kg", return_value=mock_kg),
            patch("src.web.routers.qa_generation._get_pipeline", return_value=None),
            patch("src.web.routers.qa_generation._get_validator_class", return_value=MagicMock),
        ):
            # This should not raise an error
            result = await generate_single_qa(
                mock_agent,
                "OCR text sample",
                "explanation"
            )
            
            # Should return a valid result
            assert isinstance(result, dict)
            assert "query" in result
            assert "answer" in result

    async def test_generate_qa_filters_non_dict_constraints(self) -> None:
        """Test that non-dict items in constraint list are filtered."""
        from src.web.routers.qa_generation import generate_single_qa
        
        # Create mock KG that returns mixed list
        mock_kg = MagicMock()
        mock_kg.get_constraints_for_query_type = MagicMock(
            return_value=[
                {"category": "query", "description": "valid"},
                "invalid string item",
                {"category": "answer", "description": "another valid"},
                123,  # Invalid number
            ]
        )
        mock_kg.get_formatting_rules_for_query_type = MagicMock(return_value=[])
        
        cached_kg = _CachedKG(mock_kg)
        
        # Mock agent
        mock_agent = MagicMock()
        mock_agent.generate_query = AsyncMock(return_value=["test query"])
        mock_agent.rewrite_best_answer = AsyncMock(return_value="test answer")
        
        with (
            patch("src.web.routers.qa_generation.get_cached_kg", return_value=cached_kg),
            patch("src.web.routers.qa_generation._get_kg", return_value=mock_kg),
            patch("src.web.routers.qa_generation._get_pipeline", return_value=None),
            patch("src.web.routers.qa_generation._get_validator_class", return_value=MagicMock),
        ):
            # This should not raise an error
            result = await generate_single_qa(
                mock_agent,
                "OCR text sample",
                "explanation"
            )
            
            # Should return a valid result
            assert isinstance(result, dict)
            assert "query" in result
            assert "answer" in result
