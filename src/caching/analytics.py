"""Cache analytics module for performance monitoring.

This module provides tools for analyzing cache performance including:
- Real-time hit rate tracking
- TTL efficiency analysis
- Memory usage monitoring
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table

from src.config.constants import PRICING_TIERS

logger = logging.getLogger(__name__)


@dataclass
class CacheMetrics:
    """Container for cache performance metrics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    memory_bytes: int = 0
    ttl_expirations: int = 0
    avg_ttl_seconds: float = 0.0
    ttl_efficiency: float = 0.0  # Percentage of entries used before expiration

    @property
    def hit_rate(self) -> float:
        """Calculate hit rate percentage."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0

    @property
    def total_requests(self) -> int:
        """Total number of cache requests."""
        return self.hits + self.misses


@dataclass
class RealTimeTracker:
    """Real-time cache hit rate tracker with sliding window."""

    window_size: int = 100  # Number of recent requests to track
    _requests: List[bool] = field(default_factory=list)  # True=hit, False=miss
    _timestamps: List[float] = field(default_factory=list)
    _ttl_usage: List[float] = field(default_factory=list)  # TTL usage ratios

    def record_hit(self) -> None:
        """Record a cache hit."""
        self._requests.append(True)
        self._timestamps.append(time.time())
        self._trim_window()

    def record_miss(self) -> None:
        """Record a cache miss."""
        self._requests.append(False)
        self._timestamps.append(time.time())
        self._trim_window()

    def record_ttl_usage(self, usage_ratio: float) -> None:
        """Record TTL usage ratio (0.0-1.0, how much of TTL was used before access)."""
        self._ttl_usage.append(max(0.0, min(1.0, usage_ratio)))
        if len(self._ttl_usage) > self.window_size:
            self._ttl_usage = self._ttl_usage[-self.window_size :]

    def _trim_window(self) -> None:
        """Keep only the most recent requests within window size."""
        if len(self._requests) > self.window_size:
            self._requests = self._requests[-self.window_size :]
            self._timestamps = self._timestamps[-self.window_size :]

    @property
    def current_hit_rate(self) -> float:
        """Get current hit rate from sliding window."""
        if not self._requests:
            return 0.0
        return sum(1 for r in self._requests if r) / len(self._requests) * 100

    @property
    def requests_per_second(self) -> float:
        """Calculate requests per second over the window."""
        if len(self._timestamps) < 2:
            return 0.0
        time_span = self._timestamps[-1] - self._timestamps[0]
        return len(self._timestamps) / time_span if time_span > 0 else 0.0

    @property
    def ttl_efficiency(self) -> float:
        """Calculate TTL efficiency (avg usage ratio before expiration)."""
        if not self._ttl_usage:
            return 0.0
        return sum(self._ttl_usage) / len(self._ttl_usage) * 100


@dataclass
class MemoryMonitor:
    """Monitor cache memory usage."""

    max_memory_bytes: int = 0
    current_memory_bytes: int = 0
    _samples: List[int] = field(default_factory=list)
    _sample_timestamps: List[float] = field(default_factory=list)

    def record_usage(self, bytes_used: int) -> None:
        """Record current memory usage."""
        self.current_memory_bytes = bytes_used
        if bytes_used > self.max_memory_bytes:
            self.max_memory_bytes = bytes_used
        self._samples.append(bytes_used)
        self._sample_timestamps.append(time.time())
        # Keep last 1000 samples
        if len(self._samples) > 1000:
            self._samples = self._samples[-1000:]
            self._sample_timestamps = self._sample_timestamps[-1000:]

    @property
    def avg_memory_bytes(self) -> float:
        """Average memory usage over samples."""
        return sum(self._samples) / len(self._samples) if self._samples else 0.0

    @property
    def memory_trend(self) -> str:
        """Analyze memory trend: increasing, stable, or decreasing."""
        if len(self._samples) < 10:
            return "insufficient_data"
        recent = sum(self._samples[-5:]) / 5
        older = sum(self._samples[:5]) / 5
        if recent > older * 1.1:
            return "increasing"
        elif recent < older * 0.9:
            return "decreasing"
        return "stable"


class CacheAnalytics:
    """Comprehensive cache analytics with real-time tracking."""

    def __init__(self, window_size: int = 100) -> None:
        """Initialize cache analytics.

        Args:
            window_size: Number of requests to track in sliding window
        """
        self.tracker = RealTimeTracker(window_size=window_size)
        self.memory_monitor = MemoryMonitor()
        self.metrics = CacheMetrics()
        self._start_time = time.time()

    def record_hit(self, ttl_usage_ratio: Optional[float] = None) -> None:
        """Record a cache hit.

        Args:
            ttl_usage_ratio: Optional ratio of TTL used before hit (0.0-1.0)
        """
        self.metrics.hits += 1
        self.tracker.record_hit()
        if ttl_usage_ratio is not None:
            self.tracker.record_ttl_usage(ttl_usage_ratio)

    def record_miss(self) -> None:
        """Record a cache miss."""
        self.metrics.misses += 1
        self.tracker.record_miss()

    def record_eviction(self) -> None:
        """Record a cache eviction."""
        self.metrics.evictions += 1

    def record_ttl_expiration(self) -> None:
        """Record a TTL expiration."""
        self.metrics.ttl_expirations += 1

    def update_memory(self, bytes_used: int) -> None:
        """Update memory usage metrics.

        Args:
            bytes_used: Current memory usage in bytes
        """
        self.memory_monitor.record_usage(bytes_used)
        self.metrics.memory_bytes = bytes_used

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive analytics summary."""
        uptime = time.time() - self._start_time
        return {
            "total_hits": self.metrics.hits,
            "total_misses": self.metrics.misses,
            "total_requests": self.metrics.total_requests,
            "overall_hit_rate": self.metrics.hit_rate,
            "realtime_hit_rate": self.tracker.current_hit_rate,
            "requests_per_second": self.tracker.requests_per_second,
            "evictions": self.metrics.evictions,
            "ttl_expirations": self.metrics.ttl_expirations,
            "ttl_efficiency": self.tracker.ttl_efficiency,
            "current_memory_bytes": self.memory_monitor.current_memory_bytes,
            "max_memory_bytes": self.memory_monitor.max_memory_bytes,
            "avg_memory_bytes": self.memory_monitor.avg_memory_bytes,
            "memory_trend": self.memory_monitor.memory_trend,
            "uptime_seconds": uptime,
        }

    def is_hit_rate_target_met(self, target: float = 70.0) -> bool:
        """Check if hit rate target is met.

        Args:
            target: Target hit rate percentage (default 70%)

        Returns:
            True if current hit rate meets or exceeds target
        """
        return self.tracker.current_hit_rate >= target


def calculate_savings(
    record: Dict[str, Any], cached_portion: float = 0.7, discount: float = 0.9
) -> float:
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
    hit_rate = (
        (total_hits / (total_hits + total_misses) * 100)
        if (total_hits + total_misses) > 0
        else 0.0
    )
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


def print_realtime_report(analytics: CacheAnalytics) -> None:
    """Pretty-print real-time cache analytics."""
    summary = analytics.get_summary()

    table = Table(title="Real-Time Cache Analytics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Status", style="yellow")

    # Hit rate metrics
    hit_rate = summary["realtime_hit_rate"]
    hit_status = "✓ Target Met" if hit_rate >= 70.0 else "⚠ Below Target"
    table.add_row("Real-time Hit Rate", f"{hit_rate:.2f}%", hit_status)
    table.add_row("Overall Hit Rate", f"{summary['overall_hit_rate']:.2f}%", "")

    # Request metrics
    table.add_row("Total Requests", str(summary["total_requests"]), "")
    table.add_row("Requests/sec", f"{summary['requests_per_second']:.2f}", "")

    # TTL metrics
    ttl_eff = summary["ttl_efficiency"]
    ttl_status = "✓ Efficient" if ttl_eff >= 50.0 else "⚠ Consider adjusting TTL"
    table.add_row("TTL Efficiency", f"{ttl_eff:.2f}%", ttl_status)
    table.add_row("TTL Expirations", str(summary["ttl_expirations"]), "")

    # Memory metrics
    mem_mb = summary["current_memory_bytes"] / (1024 * 1024)
    table.add_row("Memory Usage", f"{mem_mb:.2f} MB", summary["memory_trend"])
    table.add_row("Evictions", str(summary["evictions"]), "")

    Console().print(table)
