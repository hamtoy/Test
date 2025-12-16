"""Tests for kg_provider.py - KG singleton provider."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def reset_kg_singleton() -> None:
    """Reset KG singleton before and after each test."""
    from src.qa.kg_provider import reset_kg_for_test

    reset_kg_for_test()
    yield
    reset_kg_for_test()


class TestKGProvider:
    """Tests for KG provider functions."""

    def test_set_kg_instance(self) -> None:
        """Test setting KG singleton instance."""
        from src.qa import kg_provider
        from src.qa.kg_provider import set_kg_instance

        mock_kg = MagicMock()
        set_kg_instance(mock_kg)

        assert kg_provider._kg_instance is mock_kg

    def test_set_kg_instance_none(self) -> None:
        """Test setting KG instance to None."""
        from src.qa import kg_provider
        from src.qa.kg_provider import set_kg_instance

        mock_kg = MagicMock()
        set_kg_instance(mock_kg)
        set_kg_instance(None)

        assert kg_provider._kg_instance is None

    def test_get_or_create_kg_returns_existing(self) -> None:
        """Test get_or_create_kg returns existing instance."""
        from src.qa.kg_provider import get_or_create_kg, set_kg_instance

        mock_kg = MagicMock()
        set_kg_instance(mock_kg)

        result = get_or_create_kg()
        assert result is mock_kg

    def test_get_kg_if_available_returns_existing(self) -> None:
        """Test get_kg_if_available returns existing instance."""
        from src.qa.kg_provider import get_kg_if_available, set_kg_instance

        mock_kg = MagicMock()
        set_kg_instance(mock_kg)

        result = get_kg_if_available()
        assert result is mock_kg

    def test_reset_kg_for_test(self) -> None:
        """Test reset_kg_for_test clears the singleton."""
        from src.qa import kg_provider
        from src.qa.kg_provider import reset_kg_for_test, set_kg_instance

        mock_kg = MagicMock()
        set_kg_instance(mock_kg)

        reset_kg_for_test()

        assert kg_provider._kg_instance is None

    def test_reset_kg_for_test_calls_close(self) -> None:
        """Test reset_kg_for_test calls close on existing instance."""
        from src.qa.kg_provider import reset_kg_for_test, set_kg_instance

        mock_kg = MagicMock()
        set_kg_instance(mock_kg)

        reset_kg_for_test()

        mock_kg.close.assert_called_once()

    def test_reset_kg_for_test_handles_close_exception(self) -> None:
        """Test reset_kg_for_test handles exception during close."""
        from src.qa import kg_provider
        from src.qa.kg_provider import reset_kg_for_test, set_kg_instance

        mock_kg = MagicMock()
        mock_kg.close.side_effect = Exception("Close failed")
        set_kg_instance(mock_kg)

        # Should not raise
        reset_kg_for_test()

        assert kg_provider._kg_instance is None

    def test_fast_path_already_initialized(self) -> None:
        """Test fast path when instance is already set."""
        from src.qa.kg_provider import get_or_create_kg, set_kg_instance

        mock_kg = MagicMock()
        set_kg_instance(mock_kg)

        # Should return immediately without lock
        result1 = get_or_create_kg()
        result2 = get_or_create_kg()

        assert result1 is mock_kg
        assert result2 is mock_kg
