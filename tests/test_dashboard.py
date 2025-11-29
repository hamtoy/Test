from typing import Any
"""Tests for Usage Dashboard."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.analytics.dashboard import UsageDashboard


@pytest.fixture
def temp_stats_file(tmp_path: Path) -> Any:
    """Create a temporary stats file with test data."""
    stats_file = tmp_path / "cache_stats.jsonl"

    # Create sample entries for testing
    entries = []
    now = datetime.now()

    for i in range(10):
        entry = {
            "timestamp": (now - timedelta(days=i % 7, hours=i * 2)).isoformat(),
            "query_count": 5,
            "cost": 0.05,
            "cache_hits": 3,
            "cache_misses": 2,
            "tokens": 100,
            "quality": 85 + i,
            "feature": f"feature_{i % 3}",
        }
        entries.append(json.dumps(entry, ensure_ascii=False))

    stats_file.write_text("\n".join(entries), encoding="utf-8")
    return stats_file


@pytest.fixture
def empty_stats_file(tmp_path: Path) -> Any:
    """Create an empty stats file."""
    stats_file = tmp_path / "cache_stats.jsonl"
    stats_file.write_text("", encoding="utf-8")
    return stats_file


def test_dashboard_init() -> None:
    """Test dashboard initialization with default path."""
    dashboard = UsageDashboard()
    assert dashboard.stats_file == Path("cache_stats.jsonl")


def test_dashboard_init_custom_path(tmp_path: Path) -> None:
    """Test dashboard initialization with custom path."""
    custom_path = tmp_path / "custom_stats.jsonl"
    dashboard = UsageDashboard(stats_file=custom_path)
    assert dashboard.stats_file == custom_path


def test_load_last_n_days_empty(empty_stats_file: Any) -> None:
    """Test loading from empty file."""
    dashboard = UsageDashboard(stats_file=empty_stats_file)
    entries = dashboard._load_last_n_days(7)
    assert entries == []


def test_load_last_n_days_missing_file(tmp_path: Path) -> None:
    """Test loading from non-existent file."""
    missing_file = tmp_path / "missing.jsonl"
    dashboard = UsageDashboard(stats_file=missing_file)
    entries = dashboard._load_last_n_days(7)
    assert entries == []


def test_load_last_n_days_with_data(temp_stats_file: Any) -> None:
    """Test loading entries with data."""
    dashboard = UsageDashboard(stats_file=temp_stats_file)
    entries = dashboard._load_last_n_days(7)
    assert len(entries) > 0


def test_generate_weekly_report_no_data(empty_stats_file: Any, tmp_path: Path) -> None:
    """Test report generation with no data."""
    dashboard = UsageDashboard(stats_file=empty_stats_file)
    result = dashboard.generate_weekly_report()
    assert "error" in result
    assert result["error"] == "데이터 없음"


def test_generate_weekly_report_with_data(temp_stats_file: Any, tmp_path: Path) -> None:
    """Test report generation with data."""
    dashboard = UsageDashboard(stats_file=temp_stats_file)

    # Change to tmp_path to avoid creating files in actual project
    import os

    original_cwd = os.getcwd()
    os.chdir(tmp_path)

    try:
        result = dashboard.generate_weekly_report()
        assert "error" not in result
        assert "total_sessions" in result
        assert "total_cost_usd" in result
        assert "cache_hit_rate" in result
        assert "top_features" in result
        assert "hourly_distribution" in result

        # Check that HTML file was created
        html_path = tmp_path / "reports" / "weekly_dashboard.html"
        assert html_path.exists()
    finally:
        os.chdir(original_cwd)


def test_calc_cache_hit_rate(temp_stats_file: Any) -> None:
    """Test cache hit rate calculation."""
    dashboard = UsageDashboard(stats_file=temp_stats_file)
    entries = dashboard._load_last_n_days(7)
    hit_rate = dashboard._calc_cache_hit_rate(entries)
    # With 3 hits and 2 misses per entry: (3/(3+2)) * 100 = 60%
    assert hit_rate == 60.0


def test_calc_cache_hit_rate_no_data() -> None:
    """Test cache hit rate with no data."""
    dashboard = UsageDashboard()
    hit_rate = dashboard._calc_cache_hit_rate([])
    assert hit_rate == 0.0


def test_calc_avg_tokens(temp_stats_file: Any) -> None:
    """Test average tokens calculation."""
    dashboard = UsageDashboard(stats_file=temp_stats_file)
    entries = dashboard._load_last_n_days(7)
    avg_tokens = dashboard._calc_avg_tokens(entries)
    # Each entry has 100 tokens and 5 queries
    assert avg_tokens == 20.0


def test_calc_avg_tokens_no_queries() -> None:
    """Test average tokens with no queries."""
    dashboard = UsageDashboard()
    avg_tokens = dashboard._calc_avg_tokens([])
    assert avg_tokens == 0.0


def test_top_features(temp_stats_file: Any) -> None:
    """Test top features extraction."""
    dashboard = UsageDashboard(stats_file=temp_stats_file)
    entries = dashboard._load_last_n_days(7)
    top_features = dashboard._top_features(entries)
    assert isinstance(top_features, list)
    if top_features:
        assert isinstance(top_features[0], tuple)
        assert len(top_features[0]) == 2


def test_hourly_distribution(temp_stats_file: Any) -> None:
    """Test hourly distribution calculation."""
    dashboard = UsageDashboard(stats_file=temp_stats_file)
    entries = dashboard._load_last_n_days(7)
    distribution = dashboard._hourly_distribution(entries)
    assert isinstance(distribution, dict)
    assert len(distribution) == 24
    assert all(h in distribution for h in range(24))


def test_get_today_stats(temp_stats_file: Any) -> None:
    """Test getting today's stats."""
    dashboard = UsageDashboard(stats_file=temp_stats_file)
    today_stats = dashboard.get_today_stats()
    assert "sessions" in today_stats
    assert "cost" in today_stats
    assert "cache_hit_rate" in today_stats


def test_get_week_total_cost(temp_stats_file: Any) -> None:
    """Test getting week total cost."""
    dashboard = UsageDashboard(stats_file=temp_stats_file)
    total_cost = dashboard.get_week_total_cost()
    assert isinstance(total_cost, float)
    assert total_cost >= 0


def test_get_week_avg_quality(temp_stats_file: Any) -> None:
    """Test getting week average quality."""
    dashboard = UsageDashboard(stats_file=temp_stats_file)
    avg_quality = dashboard.get_week_avg_quality()
    assert isinstance(avg_quality, float)


def test_render_html() -> None:
    """Test HTML rendering."""
    dashboard = UsageDashboard()
    stats = {
        "total_sessions": 10,
        "total_cost_usd": 0.50,
        "cache_hit_rate": 60.0,
        "avg_tokens_per_query": 100,
        "cost_change_percent": 5.0,
        "top_features": [("feature_1", 5), ("feature_2", 3)],
        "hourly_distribution": {9: 5, 10: 3, 14: 2},
    }
    html = dashboard._render_html(stats)
    assert "<!DOCTYPE html>" in html
    assert "사용 현황 대시보드" in html
    assert "$0.50" in html


def test_calc_week_over_week_no_prev_data(temp_stats_file: Any) -> None:
    """Test week over week calculation with no previous data."""
    dashboard = UsageDashboard(stats_file=temp_stats_file)
    entries = dashboard._load_last_n_days(7)
    change = dashboard._calc_week_over_week(entries, "cost")
    assert isinstance(change, float)
