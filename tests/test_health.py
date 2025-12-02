"""Tests for extended health checker."""

import pytest

from src.infra.health import HealthChecker, HealthStatus


@pytest.mark.asyncio
async def test_health_checker_all_healthy() -> None:
    checker = HealthChecker(version="1.0.0")
    checker.register_check("test", lambda: {"ok": True})

    result = await checker.check_all()
    assert result.status == HealthStatus.HEALTHY
    assert "test" in result.components


@pytest.mark.asyncio
async def test_health_checker_degraded() -> None:
    checker = HealthChecker()
    checker.register_check("good", lambda: {"ok": True})

    async def bad_check() -> None:
        raise Exception("fail")

    checker.register_check("bad", bad_check)

    result = await checker.check_all()
    assert result.status == HealthStatus.DEGRADED
    assert "bad" in result.components
