import json
from pathlib import Path
from typing import Dict, Any

from rich.console import Console
from rich.table import Table

from src.constants import PRICING_TIERS


def calculate_savings(record: Dict[str, Any], cached_portion: float = 0.7, discount: float = 0.9) -> float:
    """
    Estimate savings (USD) for a single record given cache hits.
    Assumptions:
      - cached_portion of input tokens are cacheable (system + OCR context)
      - cached tokens cost is discounted by `discount` factor (e.g., 0.9 = 90% off)
    """
    model = str(record.get("model", "gemini-3-pro-preview")).lower()
    tiers = PRICING_TIERS.get(model)
    if not tiers:
        return 0.0
    input_rate = tiers[0]["input_rate"]  # use lowest tier; conservative

    hits = int(record.get("cache_hits", 0))
    tokens = int(record.get("input_tokens", 0))
    if hits <= 0 or tokens <= 0:
        return 0.0

    tokens_per_hit = tokens * cached_portion
    savings_tokens = tokens_per_hit * discount
    savings_usd = (savings_tokens / 1_000_000) * input_rate
    return savings_usd * hits


def analyze_cache_stats(path: Path) -> Dict[str, Any]:
    """Read cache stats JSONL and return summary metrics."""
    if not path.exists():
        raise FileNotFoundError(f"Cache stats file not found: {path}")

    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    total_hits = sum(int(r.get("cache_hits", 0)) for r in records)
    total_misses = sum(int(r.get("cache_misses", 0)) for r in records)
    total_requests = len(records)
    hit_rate = (total_hits / (total_hits + total_misses) * 100) if (total_hits + total_misses) > 0 else 0.0
    savings = sum(calculate_savings(r) for r in records)

    return {
        "total_records": total_requests,
        "total_hits": total_hits,
        "total_misses": total_misses,
        "hit_rate": hit_rate,
        "estimated_savings_usd": savings,
    }


def print_cache_report(summary: Dict[str, Any]) -> None:
    """Pretty-print cache analytics summary."""
    table = Table(title="Cache Analytics Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Records", str(summary["total_records"]))
    table.add_row("Hit Rate", f"{summary['hit_rate']:.2f}%")
    table.add_row("Cache Hits", str(summary["total_hits"]))
    table.add_row("Cache Misses", str(summary["total_misses"]))
    table.add_row("Estimated Savings", f"${summary['estimated_savings_usd']:.4f}")
    Console().print(table)
