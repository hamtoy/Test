from pathlib import Path
from typing import Any

from src.caching.analytics import analyze_cache_stats, calculate_savings


def test_calculate_savings_zero_when_no_hits() -> None:
    record: dict[str, Any] = {
        "model": "gemini-flash-latest",
        "cache_hits": 0,
        "input_tokens": 1000,
    }
    assert calculate_savings(record) == 0.0


def test_analyze_cache_stats(tmp_path: Path) -> None:
    path = tmp_path / "cache_stats.jsonl"
    path.write_text(
        "\n".join(
            [
                '{"model":"gemini-flash-latest","cache_hits":2,"cache_misses":1,"input_tokens":10000,"output_tokens":0}',
                '{"model":"gemini-flash-latest","cache_hits":0,"cache_misses":1,"input_tokens":5000,"output_tokens":0}',
            ]
        ),
        encoding="utf-8",
    )

    summary = analyze_cache_stats(path)
    assert summary["total_records"] == 2
    assert summary["total_hits"] == 2
    assert summary["total_misses"] == 2
    assert summary["hit_rate"] == 50.0
    assert summary["estimated_savings_usd"] > 0
