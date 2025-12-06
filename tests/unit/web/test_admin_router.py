"""Tests for admin router endpoints."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.web.routers.admin import clear_cache, get_cache_stats, cache_health


class TestGetCacheStats:
    """Test get_cache_stats endpoint."""

    @patch("src.web.routers.admin.get_global_cache_info")
    @pytest.mark.asyncio
    async def test_get_cache_stats_success(self, mock_get_cache_info: Mock) -> None:
        """Test successful cache stats retrieval."""
        mock_cache_info = {
            "hits": 100,
            "misses": 20,
            "hit_rate": 0.833,
            "size": 50,
        }
        mock_get_cache_info.return_value = mock_cache_info

        result = await get_cache_stats()

        assert result["status"] == "ok"
        assert result["cache"] == mock_cache_info
        mock_get_cache_info.assert_called_once()

    @patch("src.web.routers.admin.get_global_cache_info")
    @pytest.mark.asyncio
    async def test_get_cache_stats_exception(self, mock_get_cache_info: Mock) -> None:
        """Test cache stats retrieval with exception."""
        mock_get_cache_info.side_effect = RuntimeError("Cache error")

        with pytest.raises(HTTPException) as exc_info:
            await get_cache_stats()

        assert exc_info.value.status_code == 500
        assert "Cache error" in str(exc_info.value.detail)

    @patch("src.web.routers.admin.get_global_cache_info")
    @pytest.mark.asyncio
    async def test_get_cache_stats_empty_cache(self, mock_get_cache_info: Mock) -> None:
        """Test cache stats with empty cache."""
        mock_cache_info = {
            "hits": 0,
            "misses": 0,
            "hit_rate": 0.0,
            "size": 0,
        }
        mock_get_cache_info.return_value = mock_cache_info

        result = await get_cache_stats()

        assert result["status"] == "ok"
        assert result["cache"]["hits"] == 0
        assert result["cache"]["misses"] == 0


class TestClearCache:
    """Test clear_cache endpoint."""

    @patch("src.web.routers.admin.clear_global_rule_cache")
    @pytest.mark.asyncio
    async def test_clear_cache_success(self, mock_clear_cache: Mock) -> None:
        """Test successful cache clear."""
        result = await clear_cache()

        assert result["status"] == "ok"
        assert "cleared" in result["message"].lower()
        mock_clear_cache.assert_called_once()

    @patch("src.web.routers.admin.clear_global_rule_cache")
    @pytest.mark.asyncio
    async def test_clear_cache_exception(self, mock_clear_cache: Mock) -> None:
        """Test cache clear with exception."""
        mock_clear_cache.side_effect = RuntimeError("Clear failed")

        with pytest.raises(HTTPException) as exc_info:
            await clear_cache()

        assert exc_info.value.status_code == 500
        assert "Clear failed" in str(exc_info.value.detail)


class TestCacheHealth:
    """Test cache_health endpoint."""

    @patch("src.web.routers.admin.get_global_cache_info")
    @pytest.mark.asyncio
    async def test_cache_health_ok(self, mock_get_cache_info: Mock) -> None:
        """Test cache health with good hit rate."""
        mock_cache_info = {
            "hits": 80,
            "misses": 20,
            "hit_rate": 0.8,
        }
        mock_get_cache_info.return_value = mock_cache_info

        result = await cache_health()

        assert result["status"] == "ok"
        assert result["hit_rate"] == 0.8
        assert "healthy" in result["message"].lower()
        assert result["cache"] == mock_cache_info

    @patch("src.web.routers.admin.get_global_cache_info")
    @pytest.mark.asyncio
    async def test_cache_health_warning(self, mock_get_cache_info: Mock) -> None:
        """Test cache health with low hit rate."""
        mock_cache_info = {
            "hits": 30,
            "misses": 70,
            "hit_rate": 0.3,
        }
        mock_get_cache_info.return_value = mock_cache_info

        result = await cache_health()

        assert result["status"] == "warning"
        assert result["hit_rate"] == 0.3
        assert "low" in result["message"].lower()

    @patch("src.web.routers.admin.get_global_cache_info")
    @pytest.mark.asyncio
    async def test_cache_health_exactly_threshold(
        self, mock_get_cache_info: Mock
    ) -> None:
        """Test cache health at exactly 50% threshold."""
        mock_cache_info = {
            "hits": 50,
            "misses": 50,
            "hit_rate": 0.5,
        }
        mock_get_cache_info.return_value = mock_cache_info

        result = await cache_health()

        assert result["status"] == "ok"
        assert result["hit_rate"] == 0.5

    @patch("src.web.routers.admin.get_global_cache_info")
    @pytest.mark.asyncio
    async def test_cache_health_zero_hit_rate(self, mock_get_cache_info: Mock) -> None:
        """Test cache health with zero hit rate."""
        mock_cache_info = {
            "hits": 0,
            "misses": 100,
            "hit_rate": 0.0,
        }
        mock_get_cache_info.return_value = mock_cache_info

        result = await cache_health()

        assert result["status"] == "warning"
        assert result["hit_rate"] == 0.0

    @patch("src.web.routers.admin.get_global_cache_info")
    @pytest.mark.asyncio
    async def test_cache_health_missing_hit_rate(
        self, mock_get_cache_info: Mock
    ) -> None:
        """Test cache health when hit_rate is missing."""
        mock_cache_info = {
            "hits": 50,
            "misses": 50,
        }
        mock_get_cache_info.return_value = mock_cache_info

        result = await cache_health()

        # Should default to 0.0
        assert result["hit_rate"] == 0.0
        assert result["status"] == "warning"

    @patch("src.web.routers.admin.get_global_cache_info")
    @pytest.mark.asyncio
    async def test_cache_health_none_hit_rate(self, mock_get_cache_info: Mock) -> None:
        """Test cache health when hit_rate is None."""
        mock_cache_info = {
            "hits": 50,
            "misses": 50,
            "hit_rate": None,
        }
        mock_get_cache_info.return_value = mock_cache_info

        result = await cache_health()

        assert result["hit_rate"] == 0.0
        assert result["status"] == "warning"
