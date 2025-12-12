"""Extra tests for metrics router."""

from __future__ import annotations

import importlib
import sys
import types
from types import ModuleType

import pytest


def _import_metrics(monkeypatch: pytest.MonkeyPatch, enabled: str) -> ModuleType:
    monkeypatch.setenv("ENABLE_METRICS", enabled)
    sys.modules.pop("src.web.routers.metrics", None)
    return importlib.import_module("src.web.routers.metrics")


def test_metrics_disabled_no_extra_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    metrics = _import_metrics(monkeypatch, "false")
    assert metrics.ENABLE_METRICS is False
    assert not hasattr(metrics, "metrics_endpoint")
    assert not hasattr(metrics, "current_metrics")


@pytest.mark.asyncio
async def test_metrics_enabled_routes_work(monkeypatch: pytest.MonkeyPatch) -> None:
    metrics = _import_metrics(monkeypatch, "true")
    assert metrics.ENABLE_METRICS is True

    fake_metrics_mod = types.SimpleNamespace(get_metrics=lambda: "m")
    monkeypatch.setitem(sys.modules, "src.monitoring.metrics", fake_metrics_mod)
    resp = await metrics.metrics_endpoint()
    assert resp.body == b"m"

    class _FakeDashboard:
        def get_today_stats(self) -> dict[str, float | int]:
            return {"sessions": 1, "cost": 2.0, "cache_hit_rate": 0.5}

        def get_week_total_cost(self) -> float:
            return 3.0

        def get_week_avg_quality(self) -> float:
            return 0.9

    fake_dash_mod = types.SimpleNamespace(UsageDashboard=_FakeDashboard)
    monkeypatch.setitem(sys.modules, "src.analytics.dashboard", fake_dash_mod)
    current = await metrics.current_metrics()
    assert current["today"]["sessions"] == 1

    fake_tracker = types.SimpleNamespace(
        get_stats=lambda operation=None: {"op": {"count": 1.0}}
    )
    fake_tracker_mod = types.SimpleNamespace(get_tracker=lambda: fake_tracker)
    monkeypatch.setitem(sys.modules, "src.infra.performance_tracker", fake_tracker_mod)
    stats = await metrics.get_performance_metrics()
    assert stats["op"]["count"] == 1.0
