"""Real-time performance monitoring dashboard.

Provides live metrics aggregation and WebSocket support for
real-time monitoring of the QA system performance.

Features:
- API latency tracking (p50, p90, p99)
- Token usage monitoring
- Cost tracking per request
- Cache hit/miss rates
- Real-time WebSocket updates
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class RealtimeDashboard:
    """Real-time metrics aggregator for performance monitoring.

    Collects and aggregates metrics in memory for live dashboard display.
    Metrics are rolled up per minute and kept for the last 60 minutes.
    """

    def __init__(self, retention_minutes: int = 60) -> None:
        """Initialize dashboard.

        Args:
            retention_minutes: How long to keep metrics in memory
        """
        self.retention_minutes = retention_minutes
        self._metrics: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def record_request(
        self,
        endpoint: str,
        latency_ms: float,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
        cache_hit: bool = False,
    ) -> None:
        """Record a single request metric.

        Args:
            endpoint: API endpoint path
            latency_ms: Request latency in milliseconds
            tokens_used: Number of tokens consumed
            cost_usd: Estimated cost in USD
            cache_hit: Whether cache was hit
        """
        async with self._lock:
            timestamp = datetime.now()
            metric = {
                "timestamp": timestamp.isoformat(),
                "endpoint": endpoint,
                "latency_ms": latency_ms,
                "tokens": tokens_used,
                "cost": cost_usd,
                "cache_hit": cache_hit,
            }

            self._metrics[endpoint].append(metric)
            await self._cleanup_old_metrics()

    async def _cleanup_old_metrics(self) -> None:
        """Remove metrics older than retention period."""
        cutoff = datetime.now() - timedelta(minutes=self.retention_minutes)

        for endpoint in list(self._metrics.keys()):
            self._metrics[endpoint] = [
                m
                for m in self._metrics[endpoint]
                if datetime.fromisoformat(m["timestamp"]) > cutoff
            ]

            # Remove endpoint if no metrics left
            if not self._metrics[endpoint]:
                del self._metrics[endpoint]

    async def get_summary(self) -> Dict[str, Any]:
        """Get current metrics summary.

        Returns:
            Dictionary with aggregated metrics
        """
        async with self._lock:
            if not self._metrics:
                return {"endpoints": {}, "total_requests": 0}

            summary: Dict[str, Any] = {
                "total_requests": sum(len(m) for m in self._metrics.values()),
                "endpoints": {},
                "generated_at": datetime.now().isoformat(),
            }

            for endpoint, metrics in self._metrics.items():
                if not metrics:
                    continue

                latencies = [m["latency_ms"] for m in metrics]
                tokens = [m["tokens"] for m in metrics]
                costs = [m["cost"] for m in metrics]
                cache_hits = sum(1 for m in metrics if m["cache_hit"])

                summary["endpoints"][endpoint] = {
                    "request_count": len(metrics),
                    "latency": {
                        "p50": self._percentile(latencies, 50),
                        "p90": self._percentile(latencies, 90),
                        "p99": self._percentile(latencies, 99),
                        "avg": sum(latencies) / len(latencies) if latencies else 0,
                    },
                    "tokens": {
                        "total": sum(tokens),
                        "avg": sum(tokens) / len(tokens) if tokens else 0,
                    },
                    "cost": {
                        "total": sum(costs),
                        "avg": sum(costs) / len(costs) if costs else 0,
                    },
                    "cache_hit_rate": cache_hits / len(metrics) if metrics else 0,
                }

            return summary

    @staticmethod
    def _percentile(values: List[float], percentile: int) -> float:
        """Calculate percentile of values.

        Args:
            values: List of numeric values
            percentile: Percentile to calculate (0-100)

        Returns:
            Percentile value
        """
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]


# Global instance
_dashboard = RealtimeDashboard()


def get_dashboard() -> RealtimeDashboard:
    """Get global dashboard instance."""
    return _dashboard
