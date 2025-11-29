import json
from pathlib import Path

import pytest
from src.infra.utils import write_cache_stats


def test_write_cache_stats_trims_entries(tmp_path: Path) -> None:
    path = tmp_path / "cache" / "stats.jsonl"
    entries = [{"id": i, "cache_hits": i, "cache_misses": 0} for i in range(5)]
    for entry in entries:
        write_cache_stats(path, max_entries=3, entry=entry)

    assert path.exists()
    with open(path, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]

    # Only last 3 entries should remain
    assert len(lines) == 3
    assert [e["id"] for e in lines] == [2, 3, 4]
