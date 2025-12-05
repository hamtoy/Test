"""Tests for health router endpoints."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from src.infra.health import HealthStatus
from src.web.routers.health import (
    api_health,
    api_liveness,
    api_readiness,
    set_dependencies,
)


class TestSetDependencies:
    """Test set_dependencies function."""

    def test_set_dependencies_with_health_checker(self) -> None:
        """Test setting dependencies with health checker."""
        from src.web.routers import health as health_module

        mock_health_checker = Mock()
        set_dependencies(health_checker=mock_health_checker)

        assert health_module._health_checker is mock_health_checker

    def test_set_dependencies_ignores_extra_kwargs(self) -> None:
        """Test that extra kwargs are ignored."""
        from src.web.routers import health as health_module

        mock_health_checker = Mock()
        set_dependencies(
            health_checker=mock_health_checker, extra_arg="ignored", another="also_ignored"
        )

        assert health_module._health_checker is mock_health_checker


class TestApiLiveness:
    """Test api_liveness endpoint."""

    @pytest.mark.asyncio
    async def test_api_liveness_returns_alive(self) -> None:
        """Test liveness probe always returns alive."""
        result = await api_liveness()

        assert result == {"status": "alive"}
        assert isinstance(result, dict)


class TestApiReadiness:
    """Test api_readiness endpoint."""

    @pytest.mark.asyncio
    async def test_api_readiness_not_initialized(self) -> None:
        """Test readiness probe when health checker not initialized."""
        from src.web.routers import health as health_module

        # Save current state
        original_checker = health_module._health_checker
        try:
            health_module._health_checker = None

            with pytest.raises(HTTPException) as exc_info:
                await api_readiness()

            assert exc_info.value.status_code == 503
            assert "not initialized" in exc_info.value.detail.lower()
        finally:
            # Restore state
            health_module._health_checker = original_checker

    @pytest.mark.asyncio
    async def test_api_readiness_healthy(self) -> None:
        """Test readiness probe when system is healthy."""
        from src.web.routers import health as health_module

        mock_health_checker = Mock()
        mock_result = Mock()
        mock_result.status = HealthStatus.HEALTHY
        mock_result.to_dict.return_value = {"status": "healthy", "checks": []}

        mock_health_checker.check_all = AsyncMock(return_value=mock_result)

        # Save current state
        original_checker = health_module._health_checker
        try:
            health_module._health_checker = mock_health_checker

            result = await api_readiness()

            assert isinstance(result, JSONResponse)
            assert result.status_code == 200
            mock_health_checker.check_all.assert_called_once()
        finally:
            # Restore state
            health_module._health_checker = original_checker

    @pytest.mark.asyncio
    async def test_api_readiness_unhealthy(self) -> None:
        """Test readiness probe when system is unhealthy."""
        from src.web.routers import health as health_module

        mock_health_checker = Mock()
        mock_result = Mock()
        mock_result.status = HealthStatus.UNHEALTHY
        mock_result.to_dict.return_value = {"status": "unhealthy", "checks": []}

        mock_health_checker.check_all = AsyncMock(return_value=mock_result)

        # Save current state
        original_checker = health_module._health_checker
        try:
            health_module._health_checker = mock_health_checker

            with pytest.raises(HTTPException) as exc_info:
                await api_readiness()

            assert exc_info.value.status_code == 503
            assert "not ready" in exc_info.value.detail.lower()
        finally:
            # Restore state
            health_module._health_checker = original_checker


class TestApiHealth:
    """Test api_health endpoint."""

    @pytest.mark.asyncio
    async def test_api_health_not_initialized(self) -> None:
        """Test health check when health checker not initialized."""
        from src.web.routers import health as health_module

        # Save current state
        original_checker = health_module._health_checker
        try:
            health_module._health_checker = None

            with pytest.raises(HTTPException) as exc_info:
                await api_health()

            assert exc_info.value.status_code == 503
            assert "not initialized" in exc_info.value.detail.lower()
        finally:
            # Restore state
            health_module._health_checker = original_checker

    @pytest.mark.asyncio
    async def test_api_health_healthy_with_services(self) -> None:
        """Test health check when healthy with service info."""
        from src.web.routers import health as health_module

        mock_health_checker = Mock()
        mock_result = Mock()
        mock_result.status = HealthStatus.HEALTHY
        mock_result.to_dict.return_value = {"status": "healthy", "checks": []}

        mock_health_checker.check_all = AsyncMock(return_value=mock_result)

        # Save current state
        original_checker = health_module._health_checker
        try:
            health_module._health_checker = mock_health_checker

            with patch("src.web.api.agent", new=Mock()), patch(
                "src.web.api.kg", new=Mock()
            ), patch("src.web.api.pipeline", new=None):
                result = await api_health()

                assert isinstance(result, JSONResponse)
                assert result.status_code == 200
                # Check that services info was added
                # (can't directly access body in JSONResponse without parsing)
                mock_health_checker.check_all.assert_called_once()
        finally:
            # Restore state
            health_module._health_checker = original_checker

    @pytest.mark.asyncio
    async def test_api_health_unhealthy(self) -> None:
        """Test health check when system is unhealthy."""
        from src.web.routers import health as health_module

        mock_health_checker = Mock()
        mock_result = Mock()
        mock_result.status = HealthStatus.UNHEALTHY
        mock_result.to_dict.return_value = {"status": "unhealthy", "checks": []}

        mock_health_checker.check_all = AsyncMock(return_value=mock_result)

        # Save current state
        original_checker = health_module._health_checker
        try:
            health_module._health_checker = mock_health_checker

            result = await api_health()

            assert isinstance(result, JSONResponse)
            assert result.status_code == 503
            mock_health_checker.check_all.assert_called_once()
        finally:
            # Restore state
            health_module._health_checker = original_checker

    @pytest.mark.asyncio
    async def test_api_health_services_exception(self) -> None:
        """Test health check when service info gathering fails."""
        from src.web.routers import health as health_module

        mock_health_checker = Mock()
        mock_result = Mock()
        mock_result.status = HealthStatus.HEALTHY
        mock_result.to_dict.return_value = {"status": "healthy", "checks": []}

        mock_health_checker.check_all = AsyncMock(return_value=mock_result)

        # Save current state
        original_checker = health_module._health_checker
        try:
            health_module._health_checker = mock_health_checker

            # Mock the api module to raise exception
            import sys
            import types

            fake_api_module = types.ModuleType("fake_api")

            def raise_error(*args: Any, **kwargs: Any) -> None:
                raise Exception("Service check failed")

            # This will cause the try block to fail when accessing attributes
            with patch.dict(sys.modules, {"src.web.api": fake_api_module}):
                # Set problematic attribute
                fake_api_module.agent = property(lambda self: raise_error())  # type: ignore

                result = await api_health()

                assert isinstance(result, JSONResponse)
                # Should still return 200 even if services info failed
                assert result.status_code == 200
        finally:
            # Restore state
            health_module._health_checker = original_checker
