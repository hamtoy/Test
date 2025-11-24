import json
from pathlib import Path

import pytest

from src import cache_analytics


def test_calculate_savings_zero_for_unknown_model():
    record = {"model": "unknown", "cache_hits": 5, "input_tokens": 1000}
    assert cache_analytics.calculate_savings(record) == 0.0


def test_calculate_savings_basic():
    record = {
        "model": "gemini-3-pro-preview",
        "cache_hits": 2,
        "input_tokens": 1_000_000,
    }
    val = cache_analytics.calculate_savings(record, cached_portion=0.5, discount=0.8)
    assert val > 0


def test_analyze_cache_stats_missing_file(tmp_path: Path):
    missing = tmp_path / "nope.jsonl"
    with pytest.raises(FileNotFoundError):
        cache_analytics.analyze_cache_stats(missing)


def test_analyze_cache_stats_reads_and_sums(tmp_path: Path):
    path = tmp_path / "stats.jsonl"
    lines = [
        {
            "cache_hits": 1,
            "cache_misses": 1,
            "input_tokens": 10,
            "model": "gemini-3-pro-preview",
        },
        {
            "cache_hits": 2,
            "cache_misses": 0,
            "input_tokens": 10,
            "model": "gemini-3-pro-preview",
        },
        "not json",
    ]
    with path.open("w", encoding="utf-8") as f:
        for obj in lines:
            f.write(json.dumps(obj) + "\n" if isinstance(obj, dict) else obj + "\n")

    summary = cache_analytics.analyze_cache_stats(path)
    assert summary["total_records"] == 2  # skips bad line
    assert summary["total_hits"] == 3
    assert summary["total_misses"] == 1
    assert summary["hit_rate"] > 0
