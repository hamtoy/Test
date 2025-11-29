"""Tests for Self-Improving System."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.features.self_improvement import SelfImprovingSystem


@pytest.fixture
def temp_history_file(tmp_path: Path) -> Any:
    """Create a temporary history file with test data."""
    history_file = tmp_path / "data" / "performance_history.jsonl"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    # Create sample entries for testing (30 days of data)
    entries = []
    now = datetime.now()

    for i in range(30):
        entry = {
            "timestamp": (now - timedelta(days=i)).isoformat(),
            "quality": 90 - (i * 0.5),  # Declining quality
            "cost": 0.05 + (i * 0.01),  # Increasing cost
            "latency": 100 + (i * 5),  # Increasing latency
            "cache_hit_rate": 70 - (i * 0.5),  # Declining cache hit rate
        }
        entries.append(json.dumps(entry, ensure_ascii=False))

    history_file.write_text("\n".join(entries), encoding="utf-8")
    return history_file


@pytest.fixture
def minimal_history_file(tmp_path: Path) -> Any:
    """Create a history file with minimal data (less than 7 entries)."""
    history_file = tmp_path / "data" / "performance_history.jsonl"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    entries = []
    now = datetime.now()

    for i in range(3):  # Only 3 entries
        entry = {
            "timestamp": (now - timedelta(days=i)).isoformat(),
            "quality": 85,
            "cost": 0.05,
            "latency": 100,
            "cache_hit_rate": 70,
        }
        entries.append(json.dumps(entry, ensure_ascii=False))

    history_file.write_text("\n".join(entries), encoding="utf-8")
    return history_file


@pytest.fixture
def empty_history_file(tmp_path: Path) -> Any:
    """Create an empty history file."""
    history_file = tmp_path / "data" / "performance_history.jsonl"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.write_text("", encoding="utf-8")
    return history_file


def test_system_init() -> None:
    """Test system initialization with default paths."""
    system = SelfImprovingSystem()
    assert system.history_file == Path("data/performance_history.jsonl")
    assert system.suggestions_file == Path("reports/improvement_suggestions.json")


def test_system_init_custom_paths(tmp_path: Path) -> None:
    """Test system initialization with custom paths."""
    history = tmp_path / "history.jsonl"
    suggestions = tmp_path / "suggestions.json"
    system = SelfImprovingSystem(history_file=history, suggestions_file=suggestions)
    assert system.history_file == history
    assert system.suggestions_file == suggestions


def test_load_history_empty(empty_history_file: Any, tmp_path: Path) -> None:
    """Test loading from empty file."""
    system = SelfImprovingSystem(
        history_file=empty_history_file,
        suggestions_file=tmp_path / "suggestions.json",
    )
    history = system._load_history(30)
    assert history == []


def test_load_history_missing_file(tmp_path: Path) -> None:
    """Test loading from non-existent file."""
    missing_file = tmp_path / "missing.jsonl"
    system = SelfImprovingSystem(
        history_file=missing_file,
        suggestions_file=tmp_path / "suggestions.json",
    )
    history = system._load_history(30)
    assert history == []


def test_load_history_with_data(temp_history_file: Any, tmp_path: Path) -> None:
    """Test loading entries with data."""
    system = SelfImprovingSystem(
        history_file=temp_history_file,
        suggestions_file=tmp_path / "suggestions.json",
    )
    history = system._load_history(30)
    assert len(history) > 0


@pytest.mark.asyncio
async def test_analyze_insufficient_data(minimal_history_file: Any, tmp_path: Path) -> None:
    """Test analysis with insufficient data."""
    system = SelfImprovingSystem(
        history_file=minimal_history_file,
        suggestions_file=tmp_path / "suggestions.json",
    )
    result = await system.analyze_and_suggest()
    assert result["status"] == "insufficient_data"


@pytest.mark.asyncio
async def test_analyze_with_sufficient_data(temp_history_file: Any, tmp_path: Path) -> None:
    """Test analysis with sufficient data."""
    suggestions_file = tmp_path / "reports" / "suggestions.json"
    system = SelfImprovingSystem(
        history_file=temp_history_file,
        suggestions_file=suggestions_file,
    )
    result = await system.analyze_and_suggest()

    assert "timestamp" in result
    assert "analysis_period_days" in result
    assert "issues_found" in result
    assert "issues" in result
    assert "trends" in result

    # Check that suggestions file was created
    assert suggestions_file.exists()


def test_analyze_trends(temp_history_file: Any, tmp_path: Path) -> None:
    """Test trend analysis."""
    system = SelfImprovingSystem(
        history_file=temp_history_file,
        suggestions_file=tmp_path / "suggestions.json",
    )
    history = system._load_history(30)
    trends = system._analyze_trends(history)

    assert "quality_declining" in trends
    assert "quality_score" in trends
    assert "quality_change" in trends
    assert "cost_increasing" in trends
    assert "cost_increase_percent" in trends
    assert "latency_increasing" in trends
    assert "avg_latency_ms" in trends
    assert "cache_hit_rate" in trends


def test_analyze_trends_empty_history(tmp_path: Path) -> None:
    """Test trend analysis with empty history."""
    system = SelfImprovingSystem(
        history_file=tmp_path / "empty.jsonl",
        suggestions_file=tmp_path / "suggestions.json",
    )
    trends = system._analyze_trends([])
    assert trends["quality_score"] == 0
    assert trends["avg_latency_ms"] == 0
    assert trends["cache_hit_rate"] == 0


@pytest.mark.asyncio
async def test_apply_auto_fixes() -> None:
    """Test auto fix application."""
    system = SelfImprovingSystem()
    issues = [
        {
            "type": "cost_spike",
            "auto_fix_available": True,
            "auto_fix_action": "adjust_cache_ttl",
        },
        {
            "type": "quality_regression",
            "auto_fix_available": False,
        },
    ]
    # Should not raise any exceptions
    await system._apply_auto_fixes(issues)


@pytest.mark.asyncio
async def test_adjust_cache_ttl() -> None:
    """Test cache TTL adjustment placeholder."""
    system = SelfImprovingSystem()
    # Should not raise any exceptions
    await system._adjust_cache_ttl()


def test_send_slack_notification_no_high_severity() -> None:
    """Test Slack notification with no high severity issues."""
    system = SelfImprovingSystem()
    report = {
        "issues": [
            {"severity": "medium", "description": "Medium issue"},
            {"severity": "low", "description": "Low issue"},
        ]
    }
    # Should not raise any exceptions
    system.send_slack_notification(report)


def test_send_slack_notification_with_high_severity() -> None:
    """Test Slack notification with high severity issues."""
    system = SelfImprovingSystem()
    report = {
        "issues": [
            {"severity": "high", "description": "High severity issue"},
            {"severity": "medium", "description": "Medium issue"},
        ]
    }
    # Should not raise any exceptions (placeholder implementation)
    system.send_slack_notification(report)


def test_send_slack_notification_empty_issues() -> None:
    """Test Slack notification with empty issues."""
    from typing import Any

    system = SelfImprovingSystem()
    report: dict[str, Any] = {"issues": []}
    # Should not raise any exceptions
    system.send_slack_notification(report)
